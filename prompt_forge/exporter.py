"""Export compiled prompts and run outputs to multiple formats."""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


SUPPORTED_FORMATS = {"txt", "md", "xml", "html", "pdf"}


def _default_out_dir() -> Path:
    """Where to save files by default. ~/prompt-forge-outputs/ so users find them."""
    d = Path.home() / "prompt-forge-outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _slugify(text: str, max_len: int = 40) -> str:
    """Turn raw input into a filesystem-safe slug."""
    import re
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower()).strip()
    slug = re.sub(r"\s+", "-", slug)
    return slug[:max_len] or "prompt"


def detect_format(path: str) -> str:
    """Get format from file extension."""
    ext = Path(path).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(
            f"unsupported format '.{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )
    return ext


def auto_filename(raw_input: str, fmt: str = "xml",
                  prefix: str = "prompt") -> Path:
    """Generate a sensible filename in the default output directory."""
    slug = _slugify(raw_input)
    name = f"{_timestamp()}-{prefix}-{slug}.{fmt}"
    return _default_out_dir() / name


def export_prompt(xml: str, path: Optional[str] = None,
                  fmt: Optional[str] = None,
                  raw_input: str = "",
                  metadata: Optional[dict] = None) -> Path:
    """Export a compiled XML prompt to a file.

    Args:
        xml: the compiled prompt XML
        path: output path (if None, auto-generated in ~/prompt-forge-outputs/)
        fmt: format override ('txt'|'md'|'xml'|'html'|'pdf'); inferred from path if None
        raw_input: original user request (used for auto-filenames + metadata)
        metadata: optional dict with keys like level, domain, techniques, etc.

    Returns:
        Path to the written file.
    """
    metadata = metadata or {}

    # Resolve format
    if path and fmt is None:
        fmt = detect_format(path)
    fmt = (fmt or "xml").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(
            f"unsupported format '{fmt}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    # Resolve path
    if path is None:
        out_path = auto_filename(raw_input or "prompt", fmt=fmt)
    else:
        out_path = Path(path).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build content per format
    if fmt == "xml":
        content = xml
        out_path.write_text(content, encoding="utf-8")

    elif fmt == "txt":
        # Plain text with a small header
        header = _text_header(raw_input, metadata)
        out_path.write_text(header + xml, encoding="utf-8")

    elif fmt == "md":
        content = _as_markdown(xml, raw_input, metadata)
        out_path.write_text(content, encoding="utf-8")

    elif fmt == "html":
        content = _as_html(xml, raw_input, metadata)
        out_path.write_text(content, encoding="utf-8")

    elif fmt == "pdf":
        _write_pdf(xml, out_path, raw_input, metadata)

    return out_path


def export_run_output(run_text: str, raw_input: str = "",
                      metadata: Optional[dict] = None,
                      path: Optional[str] = None,
                      fmt: Optional[str] = None) -> Path:
    """Export the response from `forge run` to a file."""
    metadata = metadata or {}

    if path and fmt is None:
        fmt = detect_format(path)
    fmt = (fmt or "md").lower()

    if path is None:
        path_obj = auto_filename(raw_input or "output", fmt=fmt, prefix="output")
    else:
        path_obj = Path(path).expanduser().resolve()
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "txt":
        path_obj.write_text(_text_header(raw_input, metadata) + run_text,
                            encoding="utf-8")
    elif fmt == "md":
        path_obj.write_text(_run_as_markdown(run_text, raw_input, metadata),
                            encoding="utf-8")
    elif fmt == "html":
        path_obj.write_text(_run_as_html(run_text, raw_input, metadata),
                            encoding="utf-8")
    elif fmt == "xml":
        # Just wrap the response with minimal context
        path_obj.write_text(
            f"<!-- Response from {metadata.get('runner','?')} · "
            f"{metadata.get('model','?')} -->\n\n{run_text}",
            encoding="utf-8",
        )
    elif fmt == "pdf":
        _write_pdf(run_text, path_obj, raw_input, metadata, is_run_output=True)
    else:
        raise ValueError(f"unsupported format '{fmt}'")

    return path_obj


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    try:
        if sys.platform.startswith("win"):
            # Use clip.exe which is built into Windows
            p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-16le"))
            return p.returncode == 0
        if sys.platform == "darwin":
            p = subprocess.Popen("pbcopy", stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        # Linux: try xclip then xsel then wl-copy
        for cmd in (["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"],
                    ["wl-copy"]):
            if shutil.which(cmd[0]):
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                p.communicate(input=text.encode("utf-8"))
                return p.returncode == 0
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _text_header(raw_input: str, metadata: dict) -> str:
    lines = ["=" * 60, "Prompt Forge", "=" * 60]
    if raw_input:
        lines.append(f"Original request : {raw_input[:200]}")
    if metadata.get("level") is not None:
        lines.append(f"Complexity       : L{metadata['level']}")
    if metadata.get("domain"):
        lines.append(f"Domain           : {metadata['domain']}")
    if metadata.get("techniques"):
        lines.append(f"Techniques       : {', '.join(metadata['techniques'])}")
    if metadata.get("runner"):
        lines.append(f"Runner           : {metadata['runner']}")
    if metadata.get("model"):
        lines.append(f"Model            : {metadata['model']}")
    lines.append(f"Generated        : {datetime.now().isoformat(timespec='seconds')}")
    lines.append("=" * 60)
    lines.append("")
    return "\n".join(lines) + "\n"


def _as_markdown(xml: str, raw_input: str, metadata: dict) -> str:
    md = ["# Prompt Forge — Compiled Prompt\n"]
    if raw_input:
        md.append(f"**Original request:** {raw_input[:300]}\n")
    if metadata:
        md.append("## Metadata\n")
        md.append(f"- Complexity: **L{metadata.get('level', '?')}**")
        md.append(f"- Domain: **{metadata.get('domain', '?')}**")
        if metadata.get("techniques"):
            md.append(f"- Techniques: {', '.join(metadata['techniques'])}")
        if metadata.get("assumptions"):
            md.append(f"- Assumptions: {'; '.join(metadata['assumptions'])}")
        md.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}\n")
    md.append("## Prompt\n")
    md.append("```xml")
    md.append(xml)
    md.append("```")
    md.append("")
    md.append("---")
    md.append("*Paste this into Claude, GPT, Gemini, or any LLM.*\n")
    return "\n".join(md)


def _run_as_markdown(run_text: str, raw_input: str, metadata: dict) -> str:
    md = ["# Prompt Forge — Response\n"]
    if raw_input:
        md.append(f"**Request:** {raw_input[:300]}\n")
    if metadata:
        md.append(f"*Runner: {metadata.get('runner', '?')} · "
                  f"Model: {metadata.get('model', '?')} · "
                  f"Elapsed: {metadata.get('elapsed_s', 0):.1f}s*\n")
    md.append("---\n")
    md.append(run_text)
    return "\n".join(md)


def _as_html(xml: str, raw_input: str, metadata: dict) -> str:
    import html
    meta_items = ""
    if metadata:
        meta_items = "".join([
            f"<li><strong>{k}:</strong> {html.escape(str(v))}</li>"
            for k, v in metadata.items() if v
        ])
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Prompt Forge — Compiled Prompt</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 860px;
       margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3rem; }}
pre {{ background: #1e1e1e; color: #eee; padding: 1rem; border-radius: 6px;
       overflow-x: auto; font-size: 0.85rem; }}
.meta {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; }}
.meta ul {{ margin: 0.3rem 0; padding-left: 1.2rem; }}
footer {{ margin-top: 2rem; color: #888; font-size: 0.85rem; }}
</style></head>
<body>
<h1>🔨 Prompt Forge — Compiled Prompt</h1>
<p><strong>Original request:</strong> {html.escape(raw_input)}</p>
<div class="meta"><strong>Metadata</strong><ul>{meta_items}</ul></div>
<h2>Prompt (paste into any LLM)</h2>
<pre>{html.escape(xml)}</pre>
<footer>Generated {datetime.now().isoformat(timespec='seconds')} · prompt-forge</footer>
</body></html>"""


def _run_as_html(run_text: str, raw_input: str, metadata: dict) -> str:
    import html
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Prompt Forge — Response</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 860px;
       margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3rem; }}
.meta {{ color: #888; font-size: 0.9rem; }}
.response {{ white-space: pre-wrap; background: #fafafa; padding: 1.2rem;
             border-radius: 6px; border-left: 4px solid #555; }}
</style></head>
<body>
<h1>🔨 Prompt Forge — Response</h1>
<p><strong>Request:</strong> {html.escape(raw_input)}</p>
<p class="meta">Runner: {metadata.get('runner','?')} · Model: {metadata.get('model','?')}
   · Elapsed: {metadata.get('elapsed_s', 0):.1f}s
   · {datetime.now().isoformat(timespec='seconds')}</p>
<div class="response">{html.escape(run_text)}</div>
</body></html>"""


def _write_pdf(content: str, path: Path, raw_input: str,
               metadata: dict, is_run_output: bool = False) -> None:
    """Write a PDF. Tries reportlab; if missing, falls back to HTML with a hint."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                         Preformatted, Spacer)
        from reportlab.lib.colors import HexColor
    except ImportError:
        # Fallback: write HTML with the same name, inform user
        html_path = path.with_suffix(".html")
        if is_run_output:
            html_path.write_text(_run_as_html(content, raw_input, metadata),
                                 encoding="utf-8")
        else:
            html_path.write_text(_as_html(content, raw_input, metadata),
                                 encoding="utf-8")
        print(f"\n⚠ PDF export needs reportlab: pip install reportlab",
              file=sys.stderr)
        print(f"  Wrote HTML instead: {html_path}\n"
              f"  (Open in a browser and use 'Print → Save as PDF' to get a PDF.)",
              file=sys.stderr)
        # Replace the path so caller sees what was actually written
        if path.exists():
            path.unlink()
        return

    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    mono = ParagraphStyle("mono", parent=styles["Code"],
                          fontName="Courier", fontSize=8, leading=10)
    story = []
    title = "Prompt Forge — Response" if is_run_output else "Prompt Forge — Compiled Prompt"
    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    if raw_input:
        story.append(Paragraph(f"<b>Request:</b> {raw_input[:400]}", styles["Normal"]))
        story.append(Spacer(1, 6))
    if metadata:
        meta_text = " · ".join(f"<b>{k}:</b> {v}" for k, v in metadata.items()
                               if v not in (None, "", []))
        story.append(Paragraph(meta_text, styles["Normal"]))
        story.append(Spacer(1, 12))
    story.append(Preformatted(content, mono))
    doc.build(story)
