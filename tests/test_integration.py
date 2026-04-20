"""Integration tests: exercise every subsystem end-to-end.

This goes beyond test_compiler.py — it tests:
  - All output formats (xml, md, txt, html, pdf)
  - Clipboard detection
  - Hardware doctor
  - Runner configuration detection (without actually calling cloud APIs)
  - Web server routes (start/stop)
  - CLI subcommands
  - File auto-save behavior
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_forge.compiler import PromptCompiler
from prompt_forge.db import init_db
from prompt_forge import exporter, doctor, runner as runners


PASS = "  ✓"
FAIL = "  ✗"
SKIP = "  ⊘"
WARN = "  ⚠"

results = {"pass": 0, "fail": 0, "skip": 0}


def test(name, fn):
    try:
        msg = fn()
        if msg == "SKIP":
            print(f"{SKIP} {name} (skipped)")
            results["skip"] += 1
        else:
            print(f"{PASS} {name}" + (f" — {msg}" if msg else ""))
            results["pass"] += 1
    except AssertionError as e:
        print(f"{FAIL} {name}: {e}")
        results["fail"] += 1
    except Exception as e:
        print(f"{FAIL} {name}: {type(e).__name__}: {e}")
        results["fail"] += 1


# =========================================================================
# Group 1: Output formats
# =========================================================================

def test_xml_export():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.xml"
        result = exporter.export_prompt("<test/>", path=str(path))
        assert result.exists()
        assert result.read_text() == "<test/>"
        return f"{result.stat().st_size}B"


def test_md_export_contains_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.md"
        result = exporter.export_prompt(
            "<prompt/>", path=str(path),
            raw_input="hola mundo",
            metadata={"level": 3, "domain": "code", "techniques": ["CoT"]},
        )
        content = result.read_text()
        assert "# Prompt Forge" in content
        assert "hola mundo" in content
        assert "**L3**" in content
        assert "CoT" in content
        return "metadata rendered"


def test_txt_export_has_header():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.txt"
        result = exporter.export_prompt(
            "prompt content", path=str(path),
            raw_input="test",
            metadata={"level": 2, "domain": "writing"},
        )
        content = result.read_text()
        assert "=" * 10 in content
        assert "Prompt Forge" in content
        assert "L2" in content
        return "header present"


def test_html_export_valid():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.html"
        result = exporter.export_prompt(
            "<xml>test</xml>", path=str(path),
            raw_input="test input",
            metadata={"level": 1, "domain": "other"},
        )
        content = result.read_text()
        assert "<!doctype html>" in content
        assert "&lt;xml&gt;" in content  # must escape
        return "HTML valid + XML escaped"


def test_html_escapes_user_input():
    """Security: raw_input should be escaped (prevents injection)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.html"
        result = exporter.export_prompt(
            "<safe/>", path=str(path),
            raw_input="<script>alert('xss')</script>",
            metadata={},
        )
        content = result.read_text()
        assert "<script>alert" not in content
        assert "&lt;script&gt;" in content
        return "XSS prevented"


def test_pdf_or_fallback():
    """PDF if reportlab is present; otherwise should fall back to HTML."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.pdf"
        exporter.export_prompt("<xml/>", path=str(path),
                               raw_input="pdf test", metadata={"level": 1})
        # Either the .pdf exists, or an .html sibling exists (fallback)
        html_fallback = path.with_suffix(".html")
        assert path.exists() or html_fallback.exists()
        return "PDF" if path.exists() else "HTML fallback"


def test_auto_filename():
    fn = exporter.auto_filename("hello world test", fmt="md")
    assert fn.suffix == ".md"
    assert "hello-world-test" in fn.name
    assert fn.parent.name == "prompt-forge-outputs"
    return fn.name


def test_invalid_format_rejected():
    try:
        exporter.export_prompt("x", fmt="xyz")
        raise AssertionError("should have rejected bad format")
    except ValueError:
        return "rejected"


def test_run_output_export():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "resp.md"
        result = exporter.export_run_output(
            "LLM said this.", raw_input="what?",
            metadata={"runner": "test", "model": "fake", "elapsed_s": 1.5},
            path=str(path),
        )
        content = result.read_text()
        assert "LLM said this" in content
        assert "test" in content
        return "response + meta saved"


def test_clipboard_callable():
    """Just test it doesn't crash — actual copy depends on OS tool."""
    ok = exporter.copy_to_clipboard("test")
    return f"returned {ok} (sandbox may lack clipboard)"


# =========================================================================
# Group 2: Hardware doctor
# =========================================================================

def test_doctor_detects_ram():
    profile = doctor.detect()
    assert profile.ram_gb > 0, f"RAM not detected: {profile.ram_gb}"
    return f"{profile.ram_gb}GB"


def test_doctor_detects_cores():
    profile = doctor.detect()
    assert profile.cpu_cores >= 1
    return f"{profile.cpu_cores} cores"


def test_doctor_detects_disk():
    profile = doctor.detect()
    assert profile.free_disk_gb > 0
    return f"{profile.free_disk_gb}GB free"


def test_doctor_recommends():
    profile = doctor.detect()
    rec = doctor.recommend(profile)
    assert rec.runner in ("cloud", "ollama")
    assert rec.reason
    return f"→ {rec.runner}"


def test_doctor_low_ram_forces_cloud():
    """Simulated low-RAM machine should be pushed to cloud."""
    from prompt_forge.doctor import HardwareProfile, recommend
    fake = HardwareProfile(
        os="Windows", arch="x86_64", cpu_name="i3", cpu_cores=2,
        ram_gb=2.0, free_ram_gb=1.5, gpu_name=None, vram_gb=0.0,
        has_dedicated_gpu=False, free_disk_gb=10.0, has_internet=True,
    )
    rec = recommend(fake)
    assert rec.runner == "cloud"
    return "2GB RAM → cloud"


def test_doctor_offline_forces_local():
    """No internet → must pick a local model."""
    from prompt_forge.doctor import HardwareProfile, recommend
    fake = HardwareProfile(
        os="Windows", arch="x86_64", cpu_name="i7", cpu_cores=8,
        ram_gb=16.0, free_ram_gb=12.0, gpu_name=None, vram_gb=0.0,
        has_dedicated_gpu=False, free_disk_gb=50.0, has_internet=False,
    )
    rec = recommend(fake)
    assert rec.runner == "ollama"
    assert rec.ollama_model is not None
    return f"offline → {rec.ollama_model}"


def test_doctor_32gb_no_gpu_picks_right_model():
    """This user's actual setup: 32GB + integrated GPU + internet.
    Should prefer cloud, but suggest a 14B-class fallback."""
    from prompt_forge.doctor import HardwareProfile, recommend
    fake = HardwareProfile(
        os="Windows", arch="x86_64", cpu_name="i7", cpu_cores=8,
        ram_gb=32.0, free_ram_gb=22.0, gpu_name="Intel UHD", vram_gb=0.0,
        has_dedicated_gpu=False, free_disk_gb=100.0, has_internet=True,
    )
    rec = recommend(fake)
    assert rec.runner == "cloud"
    # Should still suggest a decent fallback model
    assert rec.ollama_model is not None
    assert any(m in rec.ollama_model for m in ["14b", "12b", "8b"])
    return f"cloud primary + {rec.ollama_model} fallback"


# =========================================================================
# Group 3: Runner subsystem (without actually calling cloud)
# =========================================================================

def test_runner_no_keys_fails_cleanly():
    """With no API keys and no Ollama, run_auto should give a helpful error."""
    # Save state, clear env
    saved = {k: os.environ.pop(k, None)
             for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY")}
    try:
        try:
            runners.run_auto("test prompt")
            raise AssertionError("should have raised")
        except runners.RunnerError as e:
            msg = str(e)
            # Should mention how to fix it
            assert "GEMINI" in msg or "GROQ" in msg or "Ollama" in msg
            return "clean error message"
    finally:
        for k, v in saved.items():
            if v:
                os.environ[k] = v


def test_runner_unknown_name_rejected():
    try:
        runners.run("x", runner="fakebot")
        raise AssertionError("should reject unknown runner")
    except runners.RunnerError:
        return "rejected"


def test_runner_ollama_detection():
    """Check the detection helpers don't crash even when Ollama is absent."""
    installed = runners.ollama_installed()
    running = runners.ollama_running()
    assert isinstance(installed, bool)
    assert isinstance(running, bool)
    return f"installed={installed}, running={running}"


def test_runner_install_hint_per_os():
    hint = runners.ollama_install_hint()
    assert "ollama" in hint.lower()
    # At least one install method mentioned
    assert any(s in hint for s in ["winget", "brew", "curl", "install.sh"])
    return "hint generated"


# =========================================================================
# Group 4: Web server
# =========================================================================

def test_web_server_starts_and_serves():
    """Start the server in a thread, hit its endpoints, shut it down."""
    from prompt_forge import web
    from http.server import ThreadingHTTPServer

    web.ForgeHandler.compiler = PromptCompiler()
    server = ThreadingHTTPServer(("127.0.0.1", 0), web.ForgeHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Test index page
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/",
                                    timeout=3) as r:
            assert r.status == 200
            html = r.read().decode()
            assert "Prompt Forge" in html
            assert "<textarea" in html

        # Test hardware endpoint
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/hardware",
                                    timeout=3) as r:
            data = json.loads(r.read())
            assert "profile" in data
            assert "recommendation" in data

        # Test compile POST endpoint
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/compile",
            data=json.dumps({
                "text": "test via web",
                "execute": False,
                "format": "none",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            assert "xml" in data
            assert "level" in data
            assert data["level"] >= 1

        # Test error path: empty text
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/compile",
            data=json.dumps({"text": ""}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            raise AssertionError("should have returned 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400

        # Test 404
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/nonexistent", timeout=3)
            raise AssertionError("should have 404'd")
        except urllib.error.HTTPError as e:
            assert e.code == 404

        return f"all 4 endpoints OK"
    finally:
        server.shutdown()
        server.server_close()


# =========================================================================
# Group 5: CLI subcommands (subprocess-based = truest test)
# =========================================================================

FORGE_PY = str(Path(__file__).parent.parent / "forge.py")


def _run_cli(args, input_text=None, timeout=30):
    """Run 'python forge.py ...' and capture output."""
    proc = subprocess.run(
        [sys.executable, FORGE_PY] + args,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc


def test_cli_version():
    p = _run_cli(["version"])
    assert p.returncode == 0
    assert "prompt-forge" in p.stdout
    return p.stdout.strip()


def test_cli_help_lists_all_commands():
    p = _run_cli(["--help"])
    assert p.returncode == 0
    expected = ["compile", "run", "learn", "stats", "rate", "init",
                "doctor", "web", "runners", "version"]
    missing = [c for c in expected if c not in p.stdout]
    assert not missing, f"missing commands: {missing}"
    return f"{len(expected)} commands listed"


def test_cli_compile_basic():
    p = _run_cli(["compile", "hello world", "--no-save"])
    assert p.returncode == 0
    assert "<identity>" in p.stdout
    assert "<task>" in p.stdout
    return "XML produced"


def test_cli_compile_raw_mode():
    p = _run_cli(["compile", "hello world", "--raw"])
    assert p.returncode == 0
    # --raw should output ONLY the XML, no meta section
    assert "Meta" not in p.stdout
    assert "<identity>" in p.stdout
    return "raw XML only"


def test_cli_compile_saves_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.md"
        p = _run_cli(["compile", "test", "-o", str(out)])
        assert p.returncode == 0
        assert out.exists()
        assert "Prompt Forge" in out.read_text()
        return f"{out.stat().st_size}B"


def test_cli_compile_all_formats():
    formats_ok = []
    with tempfile.TemporaryDirectory() as tmp:
        for fmt in ["xml", "md", "txt", "html"]:
            out = Path(tmp) / f"test.{fmt}"
            p = _run_cli(["compile", f"test {fmt}", "-o", str(out)])
            if p.returncode == 0 and out.exists():
                formats_ok.append(fmt)
    assert len(formats_ok) == 4
    return f"xml, md, txt, html all work"


def test_cli_doctor():
    p = _run_cli(["doctor"])
    assert p.returncode == 0
    assert "RAM" in p.stdout
    assert "Recommendation" in p.stdout
    return "report rendered"


def test_cli_runners():
    p = _run_cli(["runners"])
    assert p.returncode == 0
    assert "Gemini" in p.stdout
    assert "Ollama" in p.stdout
    return "runner list OK"


def test_cli_stats():
    p = _run_cli(["stats"])
    assert p.returncode == 0
    assert "compilations" in p.stdout.lower() or "Techniques" in p.stdout
    return "stats render"


def test_cli_stdin_input():
    p = _run_cli(["compile", "--no-save", "--raw"],
                 input_text="input via stdin")
    assert p.returncode == 0
    assert "<identity>" in p.stdout
    return "stdin accepted"


def test_cli_rejects_empty_input():
    p = _run_cli(["compile", "--no-save"], input_text="")
    # Should fail cleanly (nonzero exit, error to stderr)
    assert p.returncode != 0
    return f"exit {p.returncode}"


def test_cli_run_without_keys_fails_cleanly():
    """With no API keys, 'forge run' should error — but cleanly."""
    env_backup = {}
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY"):
        if k in os.environ:
            env_backup[k] = os.environ.pop(k)
    try:
        p = _run_cli(["run", "test", "--no-save"])
        # Should exit with error, not crash
        assert p.returncode != 0
        # Error message should help user
        combined = p.stdout + p.stderr
        assert any(k in combined for k in
                   ["GEMINI", "GROQ", "Ollama", "No runner"])
        return "graceful failure"
    finally:
        for k, v in env_backup.items():
            os.environ[k] = v


# =========================================================================
# Group 6: Idempotency / side-effect safety
# =========================================================================

def test_db_init_is_idempotent():
    init_db()
    init_db()  # second call should not error or duplicate seed
    from prompt_forge import db
    techs = db.get_techniques_for("any")
    # Should be a reasonable count, not doubled
    assert 10 <= len(techs) <= 100
    return f"{len(techs)} techniques, no duplication"


def test_compilation_saves_to_db():
    from prompt_forge import db
    before = db.get_stats()["total_compilations"]
    PromptCompiler().compile("test db save")
    after = db.get_stats()["total_compilations"]
    assert after == before + 1
    return f"{before} → {after}"


# =========================================================================
# Run all
# =========================================================================

def main():
    print("\n" + "=" * 60)
    print("  Prompt Forge — full integration test suite")
    print("=" * 60)

    init_db()

    sections = [
        ("Output formats", [
            ("xml export", test_xml_export),
            ("md export renders metadata", test_md_export_contains_metadata),
            ("txt export has header", test_txt_export_has_header),
            ("html export valid", test_html_export_valid),
            ("html escapes user input (XSS)", test_html_escapes_user_input),
            ("pdf or HTML fallback", test_pdf_or_fallback),
            ("auto-filename generation", test_auto_filename),
            ("invalid format rejected", test_invalid_format_rejected),
            ("run output export", test_run_output_export),
            ("clipboard function callable", test_clipboard_callable),
        ]),
        ("Hardware doctor", [
            ("detects RAM", test_doctor_detects_ram),
            ("detects CPU cores", test_doctor_detects_cores),
            ("detects disk space", test_doctor_detects_disk),
            ("produces a recommendation", test_doctor_recommends),
            ("low RAM → cloud", test_doctor_low_ram_forces_cloud),
            ("offline → local Ollama", test_doctor_offline_forces_local),
            ("32GB+IGP+online (your setup)", test_doctor_32gb_no_gpu_picks_right_model),
        ]),
        ("Runner subsystem", [
            ("no-keys fails cleanly", test_runner_no_keys_fails_cleanly),
            ("unknown runner rejected", test_runner_unknown_name_rejected),
            ("Ollama detection works", test_runner_ollama_detection),
            ("install hint per OS", test_runner_install_hint_per_os),
        ]),
        ("Web server", [
            ("starts + all endpoints respond", test_web_server_starts_and_serves),
        ]),
        ("CLI subcommands", [
            ("version", test_cli_version),
            ("help lists all commands", test_cli_help_lists_all_commands),
            ("compile basic", test_cli_compile_basic),
            ("compile --raw", test_cli_compile_raw_mode),
            ("compile saves file", test_cli_compile_saves_file),
            ("all 4 text formats", test_cli_compile_all_formats),
            ("doctor", test_cli_doctor),
            ("runners", test_cli_runners),
            ("stats", test_cli_stats),
            ("stdin input", test_cli_stdin_input),
            ("rejects empty input", test_cli_rejects_empty_input),
            ("run without keys fails cleanly", test_cli_run_without_keys_fails_cleanly),
        ]),
        ("Idempotency / DB", [
            ("init_db idempotent", test_db_init_is_idempotent),
            ("compile persists to DB", test_compilation_saves_to_db),
        ]),
    ]

    for section_name, tests_list in sections:
        print(f"\n── {section_name} ──")
        for name, fn in tests_list:
            test(name, fn)

    print("\n" + "=" * 60)
    total = results["pass"] + results["fail"] + results["skip"]
    print(f"  Total: {total}   "
          f"Passed: {results['pass']}   "
          f"Failed: {results['fail']}   "
          f"Skipped: {results['skip']}")
    print("=" * 60 + "\n")

    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
