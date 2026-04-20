"""The main compiler: orchestrates correction + classification + templating."""
from dataclasses import dataclass
from typing import List, Optional

from . import db
from .corrector import correct
from .classifier import detect_domain, detect_level, extract_entities
from .templates import build_xml


@dataclass
class CompileResult:
    xml: str
    level: int
    domain: str
    corrections: List[str]
    techniques: List[str]
    assumptions: List[str]
    compile_id: int


class PromptCompiler:
    """Turn raw natural-language text into a structured god-mode prompt."""

    def compile(
        self,
        raw_text: str,
        level_override: Optional[int] = None,
        domain_override: Optional[str] = None,
    ) -> CompileResult:
        # 1. Clean
        cleaned, corrections = correct(raw_text)

        # 2. Classify
        domain, _ = detect_domain(cleaned)
        if domain_override:
            domain = domain_override
        level = detect_level(cleaned, domain)
        if level_override:
            level = level_override

        # 3. Extract entities
        entities = extract_entities(cleaned)

        # 4. Build assumptions list from the entities (so the model sees them)
        assumptions = self._build_assumptions(entities, domain, level)

        # 5. Pull relevant learned techniques (top 3 by weight)
        candidate_techs = db.get_techniques_for(domain)
        # Pick techniques appropriate for this level
        selected_techs = self._select_techniques(candidate_techs, level, domain)

        # 6. Build the XML prompt
        xml = build_xml(
            raw_request=raw_text,
            cleaned_request=cleaned,
            domain=domain,
            level=level,
            entities=entities,
            techniques=selected_techs,
            assumptions=assumptions,
        )

        # 7. Persist
        tech_names = [t["name"] for t in selected_techs]
        compile_id = db.save_compilation(
            raw=raw_text, domain=domain, level=level, xml=xml,
            corrections=corrections, techniques=tech_names,
            assumptions=assumptions,
        )

        return CompileResult(
            xml=xml, level=level, domain=domain,
            corrections=corrections, techniques=tech_names,
            assumptions=assumptions, compile_id=compile_id,
        )

    def _build_assumptions(self, entities, domain, level):
        """Surface inferred context as explicit assumptions so the LLM can push back."""
        assumptions = []
        if not entities.get("audience"):
            if domain == "writing":
                assumptions.append("audience: professional peer (adjust if wrong)")
        if not entities.get("stakes") and level >= 3:
            assumptions.append("stakes: treated as real/production unless stated otherwise")
        if domain == "code" and not entities.get("tech_stack"):
            assumptions.append("tech stack: no specific constraint — pick what fits best")
        return assumptions

    def _select_techniques(self, candidates, level, domain):
        """Pick a sensible subset of techniques for this compilation."""
        # Never inject more than a few techniques — bloat hurts
        max_n = {1: 0, 2: 1, 3: 2, 4: 3}[level]
        if max_n == 0:
            return []

        # Prefer techniques tagged for this domain; fall back to universal
        domain_tagged = [t for t in candidates
                         if domain in (t.get("domains") or "") or "any" in (t.get("domains") or "")]
        pool = domain_tagged if domain_tagged else candidates
        return pool[:max_n]
