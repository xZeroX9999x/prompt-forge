"""Internet learning: fetch prompt engineering techniques from curated sources.

This is NOT model training. It's a web scraper that grows a local corpus
of techniques, which the compiler then uses to enrich outputs.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import yaml
except ImportError:
    yaml = None

from . import db


DEFAULT_SOURCES_PATH = Path(__file__).parent.parent / "data" / "sources.yaml"


class KnowledgeFetcher:
    """Scrape curated prompt-engineering resources and extract techniques."""

    def __init__(self, sources_path: Optional[str] = None, timeout: int = 15):
        self.sources_path = Path(sources_path) if sources_path else DEFAULT_SOURCES_PATH
        self.timeout = timeout

    def run(self, verbose: bool = False) -> Dict[str, int]:
        if requests is None or BeautifulSoup is None or yaml is None:
            print("ERROR: missing dependencies.")
            print("Install them with:  pip install -r requirements.txt")
            return {"error": 1}

        if not self.sources_path.exists():
            print(f"ERROR: sources file not found: {self.sources_path}")
            return {"error": 1}

        with open(self.sources_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        sources = config.get("sources", [])

        if verbose:
            print(f"Fetching from {len(sources)} source(s)...\n")

        total_added = 0
        total_ok = 0
        total_fail = 0

        for src in sources:
            url = src["url"]
            domains = src.get("domains", ["any"])
            try:
                if verbose:
                    print(f"  → {urlparse(url).netloc}{urlparse(url).path[:50]}")
                techniques = self._fetch_and_parse(url, domains)
                n_added = 0
                for t in techniques:
                    if db.add_technique(**t):
                        n_added += 1
                db.log_fetch(url, "ok", n_added)
                total_added += n_added
                total_ok += 1
                if verbose:
                    print(f"    ✓ {len(techniques)} found, {n_added} new")
            except Exception as e:
                db.log_fetch(url, f"error: {type(e).__name__}", 0)
                total_fail += 1
                if verbose:
                    print(f"    ✗ failed: {e}")

        if verbose:
            print(f"\n✓ Fetched from {total_ok}/{len(sources)} sources")
            print(f"✓ {total_added} new technique(s) added")
            if total_fail:
                print(f"⚠ {total_fail} source(s) failed")

        return {"added": total_added, "ok": total_ok, "failed": total_fail}

    def _fetch_and_parse(self, url: str, domains: List[str]) -> List[Dict]:
        """Fetch one URL and extract technique-like items from it."""
        headers = {
            "User-Agent": "prompt-forge/1.0 (github.com/awz/prompt-forge)"
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            return self._parse_html(resp.text, url, domains)
        if "markdown" in content_type.lower() or url.endswith(".md"):
            return self._parse_markdown(resp.text, url, domains)
        # Fallback: treat as markdown-ish plain text
        return self._parse_markdown(resp.text, url, domains)

    def _parse_html(self, html: str, url: str, domains: List[str]) -> List[Dict]:
        """Extract techniques from an HTML page by walking headings."""
        soup = BeautifulSoup(html, "html.parser")

        # Strip nav/footer noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        techniques = []
        # Walk h2/h3 as technique names, grab following paragraphs as description
        for heading in soup.find_all(["h2", "h3"]):
            name = heading.get_text(strip=True)
            if not name or len(name) > 100:
                continue
            if not self._looks_like_technique(name):
                continue

            description = self._collect_following_text(heading, max_chars=500)
            if len(description) < 40:
                continue

            techniques.append({
                "name": self._normalize_name(name),
                "description": description,
                "when_to_use": self._guess_when_to_use(description),
                "snippet": "",
                "domains": domains,
                "source_url": url,
            })
        return techniques

    def _parse_markdown(self, md: str, url: str, domains: List[str]) -> List[Dict]:
        """Extract techniques from a markdown doc by walking ## / ### headings."""
        techniques = []
        # Split by heading lines
        blocks = re.split(r"\n(?=#{2,3}\s)", md)
        for block in blocks:
            m = re.match(r"^(#{2,3})\s+(.+?)\n([\s\S]*)", block)
            if not m:
                continue
            name = m.group(2).strip()
            body = m.group(3).strip()
            if not self._looks_like_technique(name):
                continue
            # Trim body to first 500 chars of content (strip code fences noise)
            description = re.sub(r"```[\s\S]*?```", "", body)
            description = description.strip()[:500]
            if len(description) < 40:
                continue
            techniques.append({
                "name": self._normalize_name(name),
                "description": description,
                "when_to_use": self._guess_when_to_use(description),
                "snippet": "",
                "domains": domains,
                "source_url": url,
            })
        return techniques

    def _looks_like_technique(self, name: str) -> bool:
        """Filter out headings that are clearly not techniques."""
        name_lower = name.lower()
        bad = [
            "table of contents", "references", "introduction", "conclusion",
            "overview", "about", "changelog", "license", "contact",
            "see also", "further reading", "index",
        ]
        if any(b in name_lower for b in bad):
            return False
        if len(name) < 4 or len(name) > 90:
            return False
        # Skip pure numeric or ALL-CAPS short headings
        if re.fullmatch(r"\d+(\.\d+)*\s*.*", name) and len(name) < 6:
            return False
        return True

    def _collect_following_text(self, heading, max_chars: int = 500) -> str:
        texts = []
        for sib in heading.find_next_siblings():
            if sib.name in ("h1", "h2", "h3", "h4"):
                break
            if sib.name in ("p", "li", "ul", "ol"):
                texts.append(sib.get_text(" ", strip=True))
            if sum(len(t) for t in texts) > max_chars:
                break
        combined = " ".join(texts).strip()
        return combined[:max_chars]

    def _guess_when_to_use(self, description: str) -> str:
        """Crude heuristic: first sentence that sounds like 'use when...'."""
        sentences = re.split(r"(?<=[.!?])\s+", description)
        for s in sentences:
            sl = s.lower()
            if any(k in sl for k in ["use when", "useful when", "apply when",
                                     "helpful for", "works well when",
                                     "ideal for"]):
                return s.strip()
        # Fallback: first short sentence
        return sentences[0][:200] if sentences else ""

    def _normalize_name(self, name: str) -> str:
        # Strip leading "X. " or "X) " enumeration
        name = re.sub(r"^\d+[.)\s]+", "", name).strip()
        return name
