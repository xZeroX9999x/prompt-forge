"""Template engine: builds the final XML 'god-mode' prompt."""
from typing import List, Dict
from textwrap import indent


# Role mapping per domain
ROLES = {
    "code": "a senior software engineer with deep, battle-tested expertise"
            " in the relevant stack, who prioritizes correctness, simplicity,"
            " and maintainability over cleverness",
    "writing": "a professional writer/editor with expertise across tones"
               " and formats, who cuts filler ruthlessly and writes with"
               " concrete specificity rather than abstract generalities",
    "analysis": "a rigorous analyst who separates facts from opinions,"
                " quantifies confidence, and exposes trade-offs explicitly",
    "creative": "an accomplished creative artist who values specificity,"
                " surprise, and emotional truth over safe generalities",
    "research": "an expert researcher who synthesizes sources faithfully,"
                " distinguishes established consensus from speculation,"
                " and cites its reasoning",
    "personal": "a thoughtful, direct advisor who prioritizes the user's"
                " long-term wellbeing over comfort, without moralizing",
    "other":   "the most relevant expert for the task — pick the role"
               " that maximizes usefulness, not prestige",
}

# Domain-specific constraints injected into the prompt
DOMAIN_CONSTRAINTS = {
    "code": [
        "Produce runnable code, not pseudocode (unless explicitly asked)",
        "Handle errors and edge cases explicitly",
        "Comment the 'why', not the 'what'",
        "Prefer standard library / minimal deps unless otherwise justified",
        "Call out any assumptions about the environment (OS, versions)",
    ],
    "writing": [
        "Active voice by default",
        "Zero filler phrases ('it is important to note', 'needless to say')",
        "Concrete nouns and verbs over abstractions",
        "One idea per sentence; let the reader breathe",
    ],
    "analysis": [
        "Separate facts from inferences from opinions; tag them",
        "State the confidence level of each non-trivial claim",
        "Show the reasoning path, not just the conclusion",
        "Name the strongest counter-argument before dismissing it",
    ],
    "creative": [
        "Surprise, don't fulfill the obvious",
        "Specific > generic (one vivid image beats three adjectives)",
        "Show, don't tell; trust the reader",
    ],
    "research": [
        "Cite sources or flag [uncited] when stating facts",
        "Distinguish established consensus from minority positions",
        "Admit gaps: say 'I don't have reliable data on X'",
    ],
    "personal": [
        "Direct and kind, never saccharine or moralizing",
        "Acknowledge the emotion before offering advice",
        "Name trade-offs instead of pretending there are none",
        "If the situation needs a professional (medical/legal/mental health), say so",
    ],
    "other": [],
}


def build_xml(
    raw_request: str,
    cleaned_request: str,
    domain: str,
    level: int,
    entities: Dict,
    techniques: List[Dict],
    assumptions: List[str],
) -> str:
    """Build the full XML prompt using UNIVERSAL PROMPT v1.0 structure."""
    role = ROLES.get(domain, ROLES["other"])
    constraints = DOMAIN_CONSTRAINTS.get(domain, [])

    # Success criteria are generated from domain + level
    success_criteria = _generate_success_criteria(domain, level, cleaned_request)

    # Assemble context inferences
    audience = ", ".join(entities.get("audience", [])) or "inferred from request"
    stakes = ", ".join(entities.get("stakes", [])) or "not specified"
    tech = ", ".join(entities.get("tech_stack", [])) or "n/a"

    parts = []
    parts.append('<!-- ================================================ -->')
    parts.append(f'<!-- PROMPT FORGE · Level L{level} · domain: {domain} -->')
    parts.append('<!-- ================================================ -->')
    parts.append("")
    parts.append("<identity>")
    parts.append(f"  <role>You are {role}.</role>")
    parts.append("  <principles priority_order=\"true\">")
    parts.append("    <p>Correctness over completeness</p>")
    parts.append("    <p>Clarity over sophistication</p>")
    parts.append("    <p>Honesty over the appearance of certainty</p>")
    parts.append("    <p>Concrete action over abstract theory</p>")
    parts.append("  </principles>")
    parts.append("</identity>")
    parts.append("")

    parts.append("<task>")
    parts.append("  <raw_request>")
    parts.append(indent(cleaned_request, "    "))
    parts.append("  </raw_request>")

    if level >= 2:
        parts.append("  <interpretation>")
        parts.append("    <what_user_wants>")
        parts.append(f"      {_infer_intent(cleaned_request, domain)}")
        parts.append("    </what_user_wants>")
        if assumptions:
            parts.append("    <explicit_assumptions>")
            for a in assumptions:
                parts.append(f"      <assume>{a}</assume>")
            parts.append("    </explicit_assumptions>")
        parts.append("  </interpretation>")

    parts.append("  <success_criteria>")
    for i, c in enumerate(success_criteria, 1):
        parts.append(f'    <criterion id="{i}">{c}</criterion>')
    parts.append("  </success_criteria>")
    parts.append("</task>")
    parts.append("")

    if level >= 2:
        parts.append("<context>")
        parts.append(f"  <domain>{domain}</domain>")
        parts.append(f"  <audience>{audience}</audience>")
        parts.append(f"  <stakes>{stakes}</stakes>")
        if tech != "n/a":
            parts.append(f"  <tech_stack>{tech}</tech_stack>")
        parts.append("</context>")
        parts.append("")

    if level >= 3:
        parts.append("<reasoning>")
        parts.append("  <step_1>Decompose the request into independent sub-problems.</step_1>")
        parts.append("  <step_2>Identify implicit assumptions; mark them.</step_2>")
        parts.append("  <step_3>Solve each sub-problem; integrate; check coherence.</step_3>")
        if level >= 4:
            parts.append("  <self_critique>")
            parts.append("    <adversarial>What would a hostile reviewer say?</adversarial>")
            parts.append("    <missing>Which edge case did I overlook?</missing>")
            parts.append("    <alternative>Is there a 10x better approach I ignored?</alternative>")
            parts.append("  </self_critique>")
        parts.append("</reasoning>")
        parts.append("")

    parts.append("<constraints>")
    parts.append("  <universal>")
    parts.append("    <rule>Do not fabricate facts, numbers, APIs, sources, or citations.</rule>")
    parts.append("    <rule>If critical info is missing, ASK — do not silently assume.</rule>")
    parts.append("    <rule>Mark assumptions explicitly as [assume: X].</rule>")
    parts.append('    <rule>Say "I don\'t know" when you don\'t know.</rule>')
    parts.append("  </universal>")
    if constraints:
        parts.append(f'  <domain_specific type="{domain}">')
        for c in constraints:
            parts.append(f"    <rule>{c}</rule>")
        parts.append("  </domain_specific>")
    parts.append("</constraints>")
    parts.append("")

    # Inject learned techniques
    if techniques:
        parts.append("<techniques_to_apply>")
        for t in techniques:
            parts.append(f'  <technique name="{t["name"]}">')
            parts.append(f'    <why>{t["when_to_use"] or t["description"]}</why>')
            if t.get("snippet"):
                parts.append("    <how>")
                parts.append(indent(t["snippet"], "      "))
                parts.append("    </how>")
            parts.append("  </technique>")
        parts.append("</techniques_to_apply>")
        parts.append("")

    parts.append("<output>")
    parts.append(f"  <format>{_format_for_level(level, domain)}</format>")
    parts.append(f"  <length>{_length_for_level(level)}</length>")
    parts.append("  <anti_patterns>")
    parts.append('    <bad>Preambles like "Sure, here you go..." / "Claro, aquí tienes..."</bad>')
    parts.append("    <bad>Unnecessary disclaimers</bad>")
    parts.append("    <bad>Summarizing at the end what you just said</bad>")
    parts.append('    <bad>Generic closing offers ("let me know if you need anything else")</bad>')
    parts.append("    <bad>Excessive hedging when evidence is clear</bad>")
    parts.append("  </anti_patterns>")
    if level >= 3:
        parts.append("  <confidence_tags>")
        parts.append("    Tag non-trivial claims: [fact] [inference] [opinion] [assume]")
        parts.append("  </confidence_tags>")
    parts.append("</output>")
    parts.append("")

    parts.append("<uncertainty_policy>")
    parts.append("  - If you don't know: say so. Don't invent sources, figures, or citations.")
    parts.append("  - If the task is impossible as posed: explain why + propose an alternative.")
    parts.append("  - Prefer an incomplete honest answer over a complete false one.")
    parts.append("</uncertainty_policy>")

    if level >= 3:
        parts.append("")
        parts.append("<escalation>")
        parts.append("  <stop_if>The task needs info you don't have and can't safely infer.</stop_if>")
        parts.append("  <stop_if>Ambiguity between two paths with very different consequences.</stop_if>")
        parts.append("</escalation>")

    return "\n".join(parts)


# --- Helpers ---------------------------------------------------------------

def _generate_success_criteria(domain: str, level: int, text: str) -> List[str]:
    base = {
        "code": [
            "Code runs without errors on a clean environment",
            "Edge cases and error paths are handled",
            "Any external assumptions (versions, OS) are stated upfront",
        ],
        "writing": [
            "Tone matches the stated/inferred audience",
            "Every sentence earns its place (zero filler)",
            "Reader can act on it without re-reading",
        ],
        "analysis": [
            "Claims are separated by type (fact / inference / opinion)",
            "Strongest counter-argument is acknowledged",
            "Conclusion is traceable to stated evidence",
        ],
        "creative": [
            "Avoids the obvious or clichéd interpretation",
            "Concrete sensory detail over vague description",
            "Has a recognizable voice, not generic AI prose",
        ],
        "research": [
            "Distinguishes established facts from speculation",
            "Flags gaps in available evidence",
            "Uses precise, non-inflated language",
        ],
        "personal": [
            "Acknowledges the emotional reality before advising",
            "Offers concrete next steps, not platitudes",
            "Respects user's autonomy; no moralizing",
        ],
        "other": [
            "Directly addresses the user's actual question",
            "Is verifiable or honest about uncertainty",
        ],
    }.get(domain, [])

    if level >= 3:
        base.append("Trade-offs and alternatives are named, not hidden")
    if level >= 4:
        base.append("Includes 'Key assumptions' and 'Next steps' sections")
    return base


def _infer_intent(text: str, domain: str) -> str:
    """Best-effort one-liner describing what the user really wants."""
    t = text.strip().rstrip(".!?")
    # Short text: just echo it
    if len(t.split()) < 12:
        return f"The user wants to: {t.lower()}"
    return (f"The user is asking for help with a {domain} task. "
            f"Re-read the raw_request carefully and identify the CORE deliverable "
            f"(not surface wording).")


def _format_for_level(level: int, domain: str) -> str:
    if level == 1:
        return "direct answer, no preamble, no structure"
    if level == 2:
        return "clean prose or code block with minimal scaffolding"
    if level == 3:
        return "structured response with clear sections; separate analysis from recommendation"
    # level 4
    return ("structured document: executive summary at the top,"
            " then reasoning, then recommendation, then next steps")


def _length_for_level(level: int) -> str:
    return {
        1: "as short as possible (1-3 sentences ideally)",
        2: "concise — minimum length that satisfies all criteria",
        3: "thorough but compressed — no filler",
        4: "comprehensive but ruthlessly pruned — every paragraph earns its place",
    }[level]
