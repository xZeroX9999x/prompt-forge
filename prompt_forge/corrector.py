"""Input corrector: cleans and normalizes raw user text before compilation."""
import re
from typing import Tuple, List


# Common typos → correction (intentionally conservative to avoid false positives)
COMMON_TYPOS = {
    r"\bteh\b": "the",
    r"\brecieve\b": "receive",
    r"\bfucntion\b": "function",
    r"\bneccessary\b": "necessary",
    r"\bbecuase\b": "because",
    r"\bseperate\b": "separate",
    r"\bdefinately\b": "definitely",
    r"\balot\b": "a lot",
    r"\bwanna\b": "want to",
    r"\bgonna\b": "going to",
    r"\bkinda\b": "kind of",
    # Spanish common ones (user is multilingual)
    r"\bnecesito\b": "necesito",
    r"\bhaser\b": "hacer",
    r"\bhaci\b": "así",
    r"\bporfavor\b": "por favor",
    r"\bporke\b": "porque",
}

# Filler phrases to trim (English + Spanish)
FILLER_PATTERNS = [
    r"^\s*(hey|hi|hola|ok|okay|so|pues|entonces|look|mira),?\s+",
    r"^\s*(please|porfa|plz)\s+",
    r"\s+(por favor|please|plz)\s*$",
    r"\s+thanks?\s*!?\s*$",
    r"\s+gracias\s*!?\s*$",
]


def correct(text: str) -> Tuple[str, List[str]]:
    """Clean and normalize raw text. Returns (cleaned, list_of_corrections_applied)."""
    corrections: List[str] = []
    original = text

    # 1. Collapse whitespace
    cleaned = re.sub(r"\s+", " ", text).strip()

    # 2. Fix common typos (case-insensitive, preserve case when possible)
    for pattern, fix in COMMON_TYPOS.items():
        before = cleaned
        cleaned = re.sub(pattern, fix, cleaned, flags=re.IGNORECASE)
        if cleaned != before:
            corrections.append(f"typo: {pattern.strip('\\b')} → {fix}")

    # 3. Strip conversational filler from edges (iterate until stable)
    trimmed_any = False
    changed = True
    while changed:
        changed = False
        for pattern in FILLER_PATTERNS:
            before = cleaned
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned != before:
                changed = True
                trimmed_any = True
    if trimmed_any:
        corrections.append("trimmed conversational filler")

    # 4. Ensure ends with punctuation (helps parsers downstream)
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
        corrections.append("added terminal punctuation")

    # 5. Capitalize first letter
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    # 6. De-duplicate repeated words ("the the", "que que")
    before = cleaned
    cleaned = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", cleaned, flags=re.IGNORECASE)
    if cleaned != before:
        corrections.append("removed duplicated words")

    if cleaned == original:
        return cleaned, []
    return cleaned, corrections
