# 🔨 Prompt Forge

> **Raw text → god-mode prompt.** No LLM API required to generate prompts. Optional: wire in free cloud APIs or local Ollama to also execute them.

A command-line tool that takes natural-language requests written like a normal human — typos, filler and all — and compiles them into structured, expert-level XML prompts. Paste them into any LLM, or let Prompt Forge execute them for you via free cloud APIs (Gemini / Groq / Cerebras) or local Ollama.

> 👉 **Para setup en Windows con hardware real, lee [QUICKSTART.md](./QUICKSTART.md) primero.**

> 🇪🇸 **Español más abajo** ⬇️

---

## What it is (and isn't)

### It IS
- A **prompt compiler**: raw text in → structured XML out.
- **Self-contained Python**: works offline, no paid APIs, no tokens spent.
- **Self-improving via web corpus**: `forge learn` scrapes public prompt-engineering guides and grows a local SQLite knowledge base of techniques that get injected into future compilations.
- **Feedback-driven**: `forge rate 1-5` adjusts technique weights over time so the patterns you like surface more often.
- **Domain-aware**: auto-detects whether your request is code / writing / analysis / creative / research / personal.
- **Complexity-aware**: L1 (trivial) to L4 (architecture/strategic) — short inputs don't get bloated with scaffolding; complex ones do.
- **Bilingual-aware**: recognizes English and Spanish signals.

### It ISN'T
- An AI. It doesn't reason or understand — it classifies and templates.
- A replacement for your LLM. The compiled prompt is **input** for Claude/GPT/etc.
- Self-learning in the machine-learning sense. "Learning" = growing corpus + adjusting heuristic weights, not fine-tuning weights of a neural net.

> If you want actual LLM reasoning in the compile step, wire up Ollama locally and call it from `compiler.py`. This is a clean next step — kept out of v1 to honor the "no API" constraint.

---

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/prompt-forge.git
cd prompt-forge

# Linux / macOS
./install.sh

# Windows
install.bat
```

Then activate the venv and use it:

```bash
source .venv/bin/activate                    # Linux/mac
# .venv\Scripts\activate.bat                 # Windows

forge compile "help me write an email to my boss declining a meeting"
```

You'll get back a full structured XML prompt. Copy it, paste it into your favorite LLM, done.

---

## Usage

### Compile raw text (just get the XML)

```bash
forge compile "your request in any natural language"
forge c "short alias works too"

# From a file
forge compile -f request.txt

# From stdin (pipe)
echo "explain why my docker build is slow" | forge compile

# Save to file
forge compile "write a blog post about BJJ training splits" -o prompt.xml

# Only output the XML (good for scripting)
forge compile "..." --raw | pbcopy           # mac
forge compile "..." --raw | xclip            # linux

# Force a specific level / domain if auto-detection is wrong
forge compile "..." --level 4 --domain code
```

### Compile AND execute (one command)

```bash
# Uses the first available runner: gemini → groq → cerebras → ollama
forge run "help me refactor this messy python script"

# Force a specific runner
forge run "..." --runner groq
forge run "..." --runner ollama

# See which runners are configured
forge runners
```

Configure runners via environment variables. See [QUICKSTART.md](./QUICKSTART.md) for detailed setup.

| Tier | Provider | How to get free access | Why use it |
|------|----------|------------------------|------------|
| 1 | **Gemini 2.5 Pro/Flash** | https://aistudio.google.com | Best quality, 100 RPD free |
| 2 | **Groq** (Llama 3.3 70B) | https://console.groq.com | Fastest inference, commercial OK |
| 3 | **Cerebras** | https://cloud.cerebras.ai | 1M tokens/day, commercial OK |
| 4 | **Ollama** (local) | https://ollama.com/download | Offline, private, free forever |

### Grow the knowledge base from the web

```bash
forge learn
```

Fetches public prompt-engineering guides listed in `data/sources.yaml`, parses them, and adds new techniques to your local SQLite DB. Run this whenever you want fresh patterns — weekly, monthly, whenever.

Add your own sources by editing `data/sources.yaml`:

```yaml
sources:
  - url: https://your-favorite-prompt-blog.com/techniques
    domains: [writing, any]
```

### Rate outputs to improve future compilations

```bash
forge rate 5 --note "this one was perfect"
forge rate 2 --note "too verbose for a simple question"
```

Rating adjusts the weights of the techniques injected into that compilation. Over time, the patterns that work for you rise to the top.

### See your stats

```bash
forge stats
```

Shows total compilations, average rating, breakdown by domain and complexity level, top-weighted techniques.

### Other

```bash
forge init            # initialize / reset the DB
forge init --force    # wipe and re-seed
forge version
```

---

## How it works

```
┌────────────────┐
│  raw text in   │   "ayudame a arreglar un bug en mi script de python"
└────────┬───────┘
         ▼
┌────────────────┐
│   Corrector    │   typo fix, filler trim, normalization
└────────┬───────┘
         ▼
┌────────────────┐
│   Classifier   │   detects: domain=code, level=L2, tech=python
└────────┬───────┘
         ▼
┌────────────────┐
│ Knowledge Base │   pulls top-weighted techniques for this domain
│   (SQLite)     │
└────────┬───────┘
         ▼
┌────────────────┐
│    Template    │   assembles UNIVERSAL PROMPT v1.0 in XML
└────────┬───────┘
         ▼
┌────────────────┐
│  prompt out    │   paste into Claude / GPT / Gemini
└────────────────┘
```

### Complexity levels

| Level | When it triggers | What you get |
|-------|------------------|--------------|
| **L1** | Trivial / factual / <8 words | Minimal: identity + task + basic constraints |
| **L2** | Standard task, <25 words | Adds context, one technique |
| **L3** | Multi-part task, complex verbs | Adds explicit reasoning block, up to 2 techniques |
| **L4** | Architecture / strategy / production | Adds self-critique block, escalation, up to 3 techniques |

### Domains

`code` · `writing` · `analysis` · `creative` · `research` · `personal` · `other`

Each domain has its own role assignment, domain-specific constraints, and success criteria.

---

## Project layout

```
prompt-forge/
├── forge.py                      # CLI entry point
├── prompt_forge/
│   ├── __init__.py
│   ├── compiler.py               # Main orchestrator
│   ├── corrector.py              # Typo + filler cleanup
│   ├── classifier.py             # Domain + complexity + entity detection
│   ├── templates.py              # XML prompt builder (UNIVERSAL PROMPT v1.0)
│   ├── fetcher.py                # Web scraper for technique corpus
│   ├── analyzer.py               # Stats + feedback
│   └── db.py                     # SQLite layer
├── data/
│   ├── techniques_seed.json      # 12 seed techniques (CoT, few-shot, etc.)
│   └── sources.yaml              # URLs to scrape via `forge learn`
├── tests/
│   └── test_compiler.py          # End-to-end test suite
├── requirements.txt
├── setup.py
├── install.sh / install.bat
├── LICENSE                        # MIT
└── README.md
```

Data (DB + logs) is stored in `~/.prompt-forge/forge.db` so it survives reinstalls.

---

## Extending

### Add a new domain

In `prompt_forge/classifier.py`, add to `DOMAIN_SIGNALS`:

```python
"legal": [
    (r"\b(contract|clause|liability|nda|terms)\b", 2.0),
    (r"\b(attorney|lawyer|legal)\b", 2.5),
],
```

Then add matching entries in `prompt_forge/templates.py`:
- `ROLES["legal"] = "..."`
- `DOMAIN_CONSTRAINTS["legal"] = [...]`

### Add a new technique manually

```python
from prompt_forge.db import add_technique
add_technique(
    name="Tree of Thoughts",
    description="Explore multiple reasoning branches in parallel, then pick the best.",
    when_to_use="Use for problems with multiple valid solution paths.",
    snippet="Generate 3 different approaches. Evaluate each. Pick the strongest.",
    domains=["analysis", "code", "any"],
)
```

### Add an Ollama fallback (optional, for local AI)

In `compiler.py`, before templating, optionally call a local Ollama instance to refine interpretation. I left a hook comment where this fits cleanly.

---

## Tests

```bash
python tests/test_compiler.py
```

Covers: corrector, domain detection (including Spanish), complexity scoring, end-to-end compile, level/domain overrides, edge cases.

---

## FAQ

**Does it cost anything to run?**
No. No API calls. Web fetching is to public pages only.

**Does it work offline?**
Yes, except for `forge learn` which needs internet to scrape sources.

**Can I use the compiled prompt with any LLM?**
Yes. The XML structure is model-agnostic, though it's especially tuned for Claude (which is heavily trained on XML).

**Is the "learning" real AI learning?**
No. It's corpus growth + heuristic weight adjustment. Be honest with yourself about this. For actual intelligence, plug in an LLM (via Ollama locally, or via API).

**Can I run it without installing?**
Yes — just `python forge.py compile "..."` after `pip install -r requirements.txt`. The install scripts are convenience wrappers.

---

## License

MIT. Do what you want.

---
---

# 🇪🇸 Prompt Forge (Español)

> **Texto crudo → prompt modo dios.** Sin API de LLM.

Herramienta de línea de comandos que transforma peticiones escritas como lo haría cualquier persona normal — con typos, relleno y todo — en prompts XML estructurados de nivel experto, listos para pegar en Claude, GPT, Gemini o cualquier LLM.

El script en sí **no hace inferencia AI** — es un compilador determinista basado en heurísticas, una base de conocimiento creciente de técnicas de prompt engineering, y un bucle de retroalimentación para mejorar con el uso.

## Qué es (y qué no es)

### Lo que SÍ es
- Un **compilador de prompts**: texto crudo entra → XML estructurado sale.
- **Python autosuficiente**: funciona offline, sin APIs de pago, sin gastar tokens.
- **Se auto-mejora vía corpus web**: `forge learn` scrapea guías públicas de prompting y crece una base SQLite local de técnicas que se inyectan en compilaciones futuras.
- **Aprende de tu feedback**: `forge rate 1-5` ajusta los pesos de las técnicas con el tiempo.
- **Consciente del dominio**: detecta si tu petición es código / escritura / análisis / creativo / investigación / personal.
- **Consciente de complejidad**: L1 (trivial) a L4 (arquitectura/estratégico).
- **Bilingüe**: reconoce señales en inglés y español.

### Lo que NO es
- Una IA. No razona ni entiende — clasifica y plantilla.
- Un reemplazo de tu LLM. El prompt compilado es **entrada** para Claude/GPT/etc.
- Self-learning en el sentido ML. "Aprender" = crecer corpus + ajustar pesos heurísticos, NO fine-tunear una red neuronal.

## Inicio rápido

```bash
git clone https://github.com/TU_USUARIO/prompt-forge.git
cd prompt-forge

# Linux / macOS
./install.sh

# Windows
install.bat

# Luego:
source .venv/bin/activate
forge compile "ayudame a escribir un correo a mi jefe"
```

## Uso básico

```bash
# Compilar
forge compile "tu petición en cualquier idioma"

# Desde archivo
forge compile -f peticion.txt

# Solo XML (para pipear)
forge compile "..." --raw

# Forzar nivel/dominio
forge compile "..." --level 4 --domain code

# Crecer la base de conocimiento desde internet
forge learn

# Calificar el último prompt (mejora las compilaciones futuras)
forge rate 5 --note "perfecto"

# Ver estadísticas
forge stats
```

## Arquitectura

Ver diagrama en la sección en inglés arriba.

**Niveles de complejidad**:

| Nivel | Cuándo | Qué genera |
|-------|--------|------------|
| **L1** | Trivial / <8 palabras | Prompt mínimo |
| **L2** | Tarea estándar | + contexto, 1 técnica |
| **L3** | Multi-parte | + razonamiento explícito, 2 técnicas |
| **L4** | Arquitectura / estrategia | + auto-crítica, escalation, 3 técnicas |

**Dominios**: `code` · `writing` · `analysis` · `creative` · `research` · `personal` · `other`

## Extender

Añadir un dominio nuevo: editar `prompt_forge/classifier.py` (patrones) + `prompt_forge/templates.py` (rol + constraints).

Añadir una técnica manualmente:
```python
from prompt_forge.db import add_technique
add_technique(name="...", description="...", domains=["any"])
```

## Tests

```bash
python tests/test_compiler.py
```

## Licencia

MIT.
