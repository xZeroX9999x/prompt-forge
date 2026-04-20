"""Classifier: detects domain (code/writing/analysis/...) and complexity (L1-L4)."""
import re
from typing import Tuple, Dict, List


# --- Domain detection ------------------------------------------------------

# Weighted keyword/regex patterns per domain. Higher weight = stronger signal.
DOMAIN_SIGNALS: Dict[str, List[Tuple[str, float]]] = {
    "code": [
        (r"\b(code|script|function|bug|error|debug|compile|refactor)\b", 2.0),
        (r"\b(python|javascript|typescript|rust|go|java|c\+\+|ruby|php|bash|sql)\b", 2.5),
        (r"\b(react|vue|svelte|angular|next\.?js|django|flask|fastapi|express)\b", 2.5),
        (r"\b(api|endpoint|database|query|algorithm|regex|class|method)\b", 1.5),
        (r"\.(py|js|ts|rs|go|java|rb|php|sh|sql|tsx|jsx|html|css)\b", 3.0),
        (r"\b(prisma|sqlite|postgres|mongodb|redis|docker|kubernetes)\b", 2.0),
        (r"```|\bfunction\s*\(|\bclass\s+\w+|\bdef\s+\w+", 3.0),
        # Spanish
        (r"\b(código|programa|función|script|error)\b", 2.0),
    ],
    "writing": [
        (r"\b(write|draft|compose|letter|email|message|post|article|essay)\b", 2.0),
        (r"\b(blog|newsletter|caption|headline|tweet|thread|copy)\b", 2.0),
        (r"\b(to my (boss|friend|colleague|partner|mom|dad|team))\b", 2.5),
        (r"\b(resume|cover letter|cv|pitch|proposal)\b", 2.0),
        # Spanish
        (r"\b(escribir|redactar|carta|correo|mensaje|publicación|artículo)\b", 2.0),
        (r"\b(a mi (jefe|amigo|colega|pareja|mamá|papá|equipo))\b", 2.5),
    ],
    "analysis": [
        (r"\b(analyze|compare|evaluate|review|assess|critique|audit)\b", 2.0),
        (r"\b(pros and cons|trade-?offs?|which is better|should I (use|choose|pick))\b", 2.5),
        (r"\b(breakdown|deep ?dive|in-depth|examine)\b", 1.5),
        # Spanish
        (r"\b(analizar|comparar|evaluar|revisar|auditar)\b", 2.0),
        (r"\b(pros y contras|cuál es mejor|qué es mejor)\b", 2.5),
    ],
    "creative": [
        (r"\b(story|poem|novel|character|plot|scene|dialogue|fiction)\b", 2.5),
        (r"\b(song|lyrics|rhyme|imagine|fantasy|sci-?fi)\b", 2.0),
        (r"\b(creative|original|unique)\b.{0,30}\b(piece|work|text)\b", 2.0),
        # Spanish
        (r"\b(historia|cuento|poema|personaje|escena|diálogo)\b", 2.5),
    ],
    "research": [
        (r"\b(explain|how does|why does|what (is|are))\b", 1.5),
        (r"\b(research|study|find out|learn about|understand)\b", 2.0),
        (r"\b(latest|recent|current state of|state-of-the-art)\b", 2.0),
        # Spanish
        (r"\b(explica|cómo funciona|por qué|qué es|qué son)\b", 1.5),
        (r"\b(investigar|aprender sobre|entender)\b", 2.0),
    ],
    "personal": [
        (r"\b(advice|help me decide|should i|what would you do)\b", 2.0),
        (r"\b(my (friend|partner|relationship|family|boss))\b", 1.5),
        (r"\b(feeling|anxious|stressed|confused|overwhelmed)\b", 2.0),
        (r"\bhow (do|can|should) i (handle|deal with|approach|talk to)\b", 2.5),
        # Spanish
        (r"\b(consejo|qué harías|debería|cómo manejo|cómo lidio)\b", 2.0),
        (r"\b(mi (amigo|pareja|familia|jefe|relación))\b", 1.5),
    ],
}


def detect_domain(text: str) -> Tuple[str, Dict[str, float]]:
    """Returns (best_domain, scores_dict)."""
    t = text.lower()
    scores: Dict[str, float] = {k: 0.0 for k in DOMAIN_SIGNALS}
    for domain, patterns in DOMAIN_SIGNALS.items():
        for pattern, weight in patterns:
            matches = len(re.findall(pattern, t, flags=re.IGNORECASE))
            scores[domain] += matches * weight

    best = max(scores, key=scores.get)
    if scores[best] < 1.0:
        return "other", scores
    return best, scores


# --- Complexity detection --------------------------------------------------

# Signals that push a task toward higher complexity
COMPLEXITY_SIGNALS = [
    (r"\b(architect|architecture|design\s+(a|the)\s+system)\b", 3),
    (r"\b(strategy|roadmap|long[- ]term|multi[- ]phase)\b", 2),
    (r"\b(trade[- ]offs?|considerations?|implications?)\b", 1),
    (r"\b(comprehensive|thorough|detailed|in[- ]depth)\b", 1),
    (r"\b(and|also|plus|además|también)\b", 0.3),  # conjunctions = multi-task
    (r"[,;]", 0.1),  # more punctuation = more clauses
    (r"\b(step by step|paso a paso)\b", 1),
    (r"\b(production|enterprise|scale|scalab)", 2),
]

L4_MARKERS = [
    r"\b(architecture|architect|system design|migration plan)\b",
    r"\b(strategic|long[- ]term plan|roadmap)\b",
    r"\b(enterprise|production[- ]grade|mission[- ]critical)\b",
]


def detect_level(text: str, domain: str) -> int:
    """Return complexity 1-4."""
    t = text.lower()
    words = len(t.split())

    # Hard L4 markers
    for p in L4_MARKERS:
        if re.search(p, t):
            return 4

    # Base level by length
    if words <= 8:
        base = 1
    elif words <= 25:
        base = 2
    elif words <= 60:
        base = 3
    else:
        base = 3  # never default to 4 without markers

    # Add complexity signals
    extra = 0.0
    for pattern, weight in COMPLEXITY_SIGNALS:
        extra += len(re.findall(pattern, t)) * weight

    if extra >= 5:
        base = min(4, base + 2)
    elif extra >= 2:
        base = min(4, base + 1)

    # Questions vs tasks: pure factual questions tend to be L1/L2
    if re.match(r"^(what|who|when|where|qué|quién|cuándo|dónde)\b", t) and words < 15:
        base = min(base, 2)

    return max(1, min(4, base))


# --- Entity extraction -----------------------------------------------------

TECH_STACK_PATTERN = re.compile(
    r"\b(python|javascript|typescript|rust|go|java|c\+\+|ruby|php|bash|sql|"
    r"react|vue|svelte|angular|next\.?js|django|flask|fastapi|express|"
    r"prisma|sqlite|postgres|mongodb|redis|docker|kubernetes|"
    r"discord\.?js|tailwind|stripe)\b",
    re.IGNORECASE,
)

AUDIENCE_HINTS = {
    r"\b(my boss|jefe)\b": "boss / superior",
    r"\b(my team|equipo)\b": "team",
    r"\b(client|cliente)\b": "client",
    r"\b(my (mom|dad|mamá|papá|parents|padres))\b": "family",
    r"\b(friend|amigo)\b": "friend",
    r"\b(beginner|novice|novato|principiante)\b": "beginner",
    r"\b(expert|experto|senior)\b": "expert audience",
}

STAKES_HINTS = {
    r"\b(production|prod|producción|live)\b": "production",
    r"\b(prototype|poc|test|prueba)\b": "prototype",
    r"\b(critical|urgent|crítico|urgente|asap)\b": "critical",
    r"\b(learning|study|aprendiendo|estudiando)\b": "learning",
}


def extract_entities(text: str) -> Dict[str, List[str]]:
    tech = list(set(m.lower() for m in TECH_STACK_PATTERN.findall(text)))

    audiences = []
    for pat, label in AUDIENCE_HINTS.items():
        if re.search(pat, text, re.IGNORECASE):
            audiences.append(label)

    stakes = []
    for pat, label in STAKES_HINTS.items():
        if re.search(pat, text, re.IGNORECASE):
            stakes.append(label)

    return {
        "tech_stack": tech,
        "audience": audiences,
        "stakes": stakes,
    }
