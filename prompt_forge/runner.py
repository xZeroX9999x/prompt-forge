"""Runners: execute compiled prompts via local Ollama or free cloud APIs.

Based on research (April 2026), Prompt Forge supports a tiered fallback:
  Tier 1: Gemini 2.5 Pro / Flash   (quality default, 100 RPD on Pro free)
  Tier 2: Groq Llama 3.3 70B       (fast + commercial-safe)
  Tier 3: Cerebras GPT-OSS 120B    (1M tokens/day, 8K context)
  Tier 4: Ollama local Qwen3-14B   (offline / privacy fallback)

Configure via environment variables:
  GEMINI_API_KEY       (https://aistudio.google.com)
  GROQ_API_KEY         (https://console.groq.com)
  CEREBRAS_API_KEY     (https://cloud.cerebras.ai)
  FORGE_RUNNER         one of: auto, gemini, groq, cerebras, ollama
  FORGE_OLLAMA_MODEL   default: qwen3:14b
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


@dataclass
class RunResult:
    text: str
    runner: str
    model: str
    elapsed_s: float


class RunnerError(Exception):
    pass


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only — no extra deps)
# ---------------------------------------------------------------------------

def _http_post(url: str, headers: dict, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RunnerError(f"HTTP {e.code}: {body[:300]}") from e
    except urllib.error.URLError as e:
        raise RunnerError(f"network error: {e}") from e


# ---------------------------------------------------------------------------
# Cloud runners (OpenAI-compatible where possible)
# ---------------------------------------------------------------------------

def run_gemini(prompt: str, model: str = "gemini-2.5-flash") -> RunResult:
    """Google Gemini via AI Studio REST. Free tier: 100 RPD (Pro), 250 RPD (Flash)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RunnerError("GEMINI_API_KEY not set")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0},
    }
    t0 = time.time()
    resp = _http_post(url, {"Content-Type": "application/json"}, payload)
    try:
        text = resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RunnerError(f"unexpected Gemini response: {resp}") from e
    return RunResult(text=text, runner="gemini", model=model,
                     elapsed_s=time.time() - t0)


def run_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> RunResult:
    """Groq — fastest inference on the planet. Commercial use OK, no training on inputs."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RunnerError("GROQ_API_KEY not set")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    t0 = time.time()
    resp = _http_post(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
    )
    try:
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RunnerError(f"unexpected Groq response: {resp}") from e
    return RunResult(text=text, runner="groq", model=model,
                     elapsed_s=time.time() - t0)


def run_cerebras(prompt: str, model: str = "llama3.1-70b") -> RunResult:
    """Cerebras — 1M tokens/day free, 8K context cap. Commercial OK, no training."""
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        raise RunnerError("CEREBRAS_API_KEY not set")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    t0 = time.time()
    resp = _http_post(
        "https://api.cerebras.ai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
    )
    try:
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RunnerError(f"unexpected Cerebras response: {resp}") from e
    return RunResult(text=text, runner="cerebras", model=model,
                     elapsed_s=time.time() - t0)


# ---------------------------------------------------------------------------
# Local Ollama runner
# ---------------------------------------------------------------------------

OLLAMA_DEFAULT_MODEL = "qwen3:14b"
OLLAMA_API = "http://localhost:11434/api/generate"


def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def ollama_running() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def ollama_has_model(model: str) -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        return any(m.get("name", "").startswith(model.split(":")[0])
                   for m in data.get("models", []))
    except Exception:
        return False


def ollama_install_hint() -> str:
    if sys.platform.startswith("win"):
        return ("Ollama not found. Install with:\n"
                '  winget install -e --id Ollama.Ollama\n'
                "Or download from: https://ollama.com/download/windows")
    if sys.platform == "darwin":
        return ("Ollama not found. Install with:\n"
                "  brew install ollama\n"
                "Or download from: https://ollama.com/download/mac")
    return ("Ollama not found. Install with:\n"
            "  curl -fsSL https://ollama.com/install.sh | sh")


def ollama_start_server() -> None:
    """Spawn 'ollama serve' in the background if not already running."""
    if ollama_running():
        return
    kwargs = {}
    if sys.platform.startswith("win"):
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = CREATE_NO_WINDOW
    subprocess.Popen(["ollama", "serve"],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **kwargs)
    # Wait up to 10s for server to come up
    for _ in range(20):
        time.sleep(0.5)
        if ollama_running():
            return
    raise RunnerError("failed to start 'ollama serve'")


def ollama_pull(model: str) -> None:
    print(f"→ Pulling {model} (first time only, this may take several minutes)...")
    subprocess.check_call(["ollama", "pull", model])


def run_ollama(prompt: str, model: Optional[str] = None) -> RunResult:
    model = model or os.environ.get("FORGE_OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
    if not ollama_installed():
        raise RunnerError(ollama_install_hint())
    if not ollama_running():
        ollama_start_server()
    if not ollama_has_model(model):
        ollama_pull(model)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    t0 = time.time()
    resp = _http_post(OLLAMA_API, {"Content-Type": "application/json"},
                      payload, timeout=600)
    text = resp.get("response", "")
    if not text:
        raise RunnerError(f"empty Ollama response: {resp}")
    return RunResult(text=text, runner="ollama", model=model,
                     elapsed_s=time.time() - t0)


# ---------------------------------------------------------------------------
# Auto-selection with fallback
# ---------------------------------------------------------------------------

def run_auto(prompt: str) -> RunResult:
    """Try providers in order of preference, fall through on failure."""
    errors = []
    attempts = []

    # Tier 1: Gemini (best quality free)
    if os.environ.get("GEMINI_API_KEY"):
        attempts.append(("gemini", run_gemini))
    # Tier 2: Groq (fastest cloud)
    if os.environ.get("GROQ_API_KEY"):
        attempts.append(("groq", run_groq))
    # Tier 3: Cerebras (highest daily budget)
    if os.environ.get("CEREBRAS_API_KEY"):
        attempts.append(("cerebras", run_cerebras))
    # Tier 4: Local Ollama
    if ollama_installed():
        attempts.append(("ollama", run_ollama))

    if not attempts:
        raise RunnerError(
            "No runner available. Configure at least one:\n"
            "  - set GEMINI_API_KEY   (https://aistudio.google.com)\n"
            "  - set GROQ_API_KEY     (https://console.groq.com)\n"
            "  - set CEREBRAS_API_KEY (https://cloud.cerebras.ai)\n"
            "  - or install Ollama    (https://ollama.com/download)"
        )

    for name, fn in attempts:
        try:
            return fn(prompt)
        except RunnerError as e:
            errors.append(f"{name}: {e}")
            continue

    raise RunnerError("all runners failed:\n  " + "\n  ".join(errors))


def run(prompt: str, runner: Optional[str] = None) -> RunResult:
    """Main entry point. Runner selection: env FORGE_RUNNER, or arg, or auto."""
    runner = runner or os.environ.get("FORGE_RUNNER", "auto").lower()
    if runner == "auto":
        return run_auto(prompt)
    if runner == "gemini":
        return run_gemini(prompt)
    if runner == "groq":
        return run_groq(prompt)
    if runner == "cerebras":
        return run_cerebras(prompt)
    if runner == "ollama":
        return run_ollama(prompt)
    raise RunnerError(f"unknown runner: {runner}")
