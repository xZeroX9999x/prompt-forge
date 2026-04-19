#!/usr/bin/env python3
"""
Prompt Forge — CLI for compiling raw natural-language requests
into expert-level ("god-mode") structured prompts.

No LLM API required. Pure Python + heuristics + a growing knowledge base.
"""
import argparse
import os
import sys
from pathlib import Path

from prompt_forge.compiler import PromptCompiler
from prompt_forge.fetcher import KnowledgeFetcher
from prompt_forge.analyzer import Analyzer
from prompt_forge.db import init_db, DB_PATH
from prompt_forge import runner as runners
from prompt_forge import exporter
from prompt_forge import doctor as doc


BANNER = r"""
  ____                            _      _____                    
 |  _ \ _ __ ___  _ __ ___  _ __ | |_   |  ___|__  _ __ __ _  ___ 
 | |_) | '__/ _ \| '_ ` _ \| '_ \| __|  | |_ / _ \| '__/ _` |/ _ \
 |  __/| | | (_) | | | | | | |_) | |_   |  _| (_) | | | (_| |  __/
 |_|   |_|  \___/|_| |_| |_| .__/ \__|  |_|  \___/|_|  \__, |\___|
                           |_|                         |___/      
    raw text  →  god-mode prompt   (no API needed)
"""


def cmd_compile(args):
    # Resolve input
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Error: no input. Pass text, use -f FILE, or pipe via stdin.",
              file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("Error: empty input.", file=sys.stderr)
        sys.exit(1)

    compiler = PromptCompiler()
    result = compiler.compile(
        text,
        level_override=args.level,
        domain_override=args.domain,
    )

    if args.raw:
        sys.stdout.write(result.xml)
        return

    # Auto-save unless user explicitly says --no-save
    saved_path = None
    if not args.no_save or args.out or args.format:
        metadata = {
            "level": result.level,
            "domain": result.domain,
            "techniques": result.techniques,
            "assumptions": result.assumptions,
        }
        try:
            saved_path = exporter.export_prompt(
                xml=result.xml,
                path=args.out,
                fmt=args.format,
                raw_input=text,
                metadata=metadata,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Clipboard
    copied = False
    if args.copy:
        copied = exporter.copy_to_clipboard(result.xml)

    # Console output
    print(f"\n## 🧩 Compiled Prompt  [L{result.level} · {result.domain}]\n")
    print(result.xml)
    print("\n## 📊 Meta\n")
    if result.corrections:
        print(f"  Corrections applied : {', '.join(result.corrections)}")
    print(f"  Techniques injected : {', '.join(result.techniques) or '(base)'}")
    if result.assumptions:
        print(f"  Explicit assumptions: {'; '.join(result.assumptions)}")
    print(f"  Compile id          : #{result.compile_id}")
    if saved_path:
        print(f"\n✓ Saved to: {saved_path}")
    if args.copy:
        if copied:
            print("✓ Copied to clipboard")
        else:
            print("⚠ Could not copy to clipboard (no clipboard tool found)")
    print(f"\n  → Rate it:  forge rate <1-5>")


def cmd_learn(args):
    fetcher = KnowledgeFetcher(sources_path=args.sources)
    fetcher.run(verbose=True)


def cmd_stats(args):
    Analyzer().print_stats()


def cmd_rate(args):
    ok = Analyzer().rate_last(args.score, args.note or "")
    if ok:
        print(f"✓ Rated last compilation: {args.score}/5")
    else:
        print("No compilation found to rate.", file=sys.stderr)
        sys.exit(1)


def cmd_init(args):
    init_db(force=args.force)
    print(f"✓ Database initialized at {DB_PATH}")
    print("✓ Seed techniques loaded.")
    print("\nNext:")
    print("  forge learn            # fetch latest prompt techniques from the web")
    print('  forge compile "help me write an email to my boss"')


def cmd_version(args):
    from prompt_forge import __version__
    print(f"prompt-forge {__version__}")


def cmd_run(args):
    """Compile raw text AND execute the prompt through a configured runner."""
    # Resolve input
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Error: no input. Pass text, use -f FILE, or pipe via stdin.",
              file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("Error: empty input.", file=sys.stderr)
        sys.exit(1)

    # Compile
    compiler = PromptCompiler()
    result = compiler.compile(
        text,
        level_override=args.level,
        domain_override=args.domain,
    )
    print(f"\n[compiled · L{result.level} · {result.domain}]  running...\n")

    # Execute
    try:
        run_result = runners.run(result.xml, runner=args.runner)
    except runners.RunnerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(run_result.text)
    print(f"\n─── {run_result.runner} · {run_result.model} · "
          f"{run_result.elapsed_s:.1f}s ───")

    # Save response unless --no-save
    saved_path = None
    if not args.no_save or args.out or args.format:
        metadata = {
            "level": result.level,
            "domain": result.domain,
            "runner": run_result.runner,
            "model": run_result.model,
            "elapsed_s": run_result.elapsed_s,
        }
        try:
            saved_path = exporter.export_run_output(
                run_text=run_result.text,
                raw_input=text,
                metadata=metadata,
                path=args.out,
                fmt=args.format,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Clipboard
    if args.copy:
        if exporter.copy_to_clipboard(run_result.text):
            print("✓ Copied response to clipboard")

    if saved_path:
        print(f"✓ Saved to: {saved_path}")


def cmd_doctor(args):
    profile = doc.detect()
    rec = doc.recommend(profile)
    doc.print_report(profile, rec)


def cmd_web(args):
    from prompt_forge import web
    web.serve(host=args.host, port=args.port, open_browser=not args.no_browser)


def cmd_runners(args):
    """Show which runners are currently available/configured."""
    print("\n🔌 Available runners\n" + "─" * 40)

    gemini = bool(os.environ.get("GEMINI_API_KEY"))
    groq = bool(os.environ.get("GROQ_API_KEY"))
    cerebras = bool(os.environ.get("CEREBRAS_API_KEY"))
    ollama_ok = runners.ollama_installed()
    ollama_up = runners.ollama_running() if ollama_ok else False

    print(f"  Gemini    (cloud, free tier) : {'✓ configured' if gemini else '✗ GEMINI_API_KEY not set'}")
    print(f"  Groq      (cloud, fast)      : {'✓ configured' if groq else '✗ GROQ_API_KEY not set'}")
    print(f"  Cerebras  (cloud, 1M tok/day): {'✓ configured' if cerebras else '✗ CEREBRAS_API_KEY not set'}")
    print(f"  Ollama    (local)            : "
          f"{'✓ installed ' + ('+ running' if ollama_up else '(server not running)') if ollama_ok else '✗ not installed'}")

    any_ok = gemini or groq or cerebras or ollama_ok
    print()
    if not any_ok:
        print("⚠ No runners available. Set up at least one:")
        print("  Fastest path — free cloud APIs (no install):")
        print("    1. Gemini   : https://aistudio.google.com   → set GEMINI_API_KEY")
        print("    2. Groq     : https://console.groq.com      → set GROQ_API_KEY")
        print("    3. Cerebras : https://cloud.cerebras.ai     → set CEREBRAS_API_KEY")
        print()
        print("  Offline option — local Ollama:")
        print(f"    {runners.ollama_install_hint()}")
    else:
        print("Default selection order: gemini → groq → cerebras → ollama")
        print("Override with:  FORGE_RUNNER=gemini  (or groq/cerebras/ollama)")
    print()


def build_parser():
    p = argparse.ArgumentParser(
        prog="forge",
        description="Compile raw text into expert-level structured prompts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=BANNER,
    )
    subs = p.add_subparsers(dest="cmd", required=True)

    c = subs.add_parser("compile", aliases=["c"], help="Compile text → prompt")
    c.add_argument("text", nargs="*", help='Raw request (e.g. "help me fix this bug")')
    c.add_argument("-f", "--file", help="Read raw request from file")
    c.add_argument("-o", "--out",
                   help="Write compiled prompt to this exact path "
                        "(format inferred from extension)")
    c.add_argument("--format", choices=sorted(exporter.SUPPORTED_FORMATS),
                   help="Output format (auto-named in ~/prompt-forge-outputs/)")
    c.add_argument("--no-save", action="store_true",
                   help="Don't save a file, just print to terminal")
    c.add_argument("--copy", action="store_true",
                   help="Copy the compiled XML to the system clipboard")
    c.add_argument("--level", type=int, choices=[1, 2, 3, 4],
                   help="Force complexity level")
    c.add_argument("--domain",
                   choices=["code", "writing", "analysis", "creative",
                            "research", "personal", "other"],
                   help="Force domain")
    c.add_argument("--raw", action="store_true",
                   help="Output only the XML (for piping)")
    c.set_defaults(func=cmd_compile)

    l = subs.add_parser("learn",
                        help="Fetch new techniques from online prompt guides")
    l.add_argument("--sources", default=None,
                   help="Path to sources.yaml (default: data/sources.yaml)")
    l.set_defaults(func=cmd_learn)

    s = subs.add_parser("stats", help="Show compilation history and insights")
    s.set_defaults(func=cmd_stats)

    r = subs.add_parser("rate", help="Rate the last compilation (1-5)")
    r.add_argument("score", type=int, choices=[1, 2, 3, 4, 5])
    r.add_argument("--note", help="Optional note")
    r.set_defaults(func=cmd_rate)

    i = subs.add_parser("init", help="Initialize database + seed techniques")
    i.add_argument("--force", action="store_true", help="Reset existing DB")
    i.set_defaults(func=cmd_init)

    v = subs.add_parser("version", help="Show version")
    v.set_defaults(func=cmd_version)

    rn = subs.add_parser("run",
                         help="Compile AND execute the prompt via a configured runner")
    rn.add_argument("text", nargs="*", help="Raw request")
    rn.add_argument("-f", "--file", help="Read raw request from file")
    rn.add_argument("-o", "--out",
                    help="Write the response to this path (format from extension)")
    rn.add_argument("--format", choices=sorted(exporter.SUPPORTED_FORMATS),
                    help="Output format for the response")
    rn.add_argument("--no-save", action="store_true",
                    help="Don't save a file, just print to terminal")
    rn.add_argument("--copy", action="store_true",
                    help="Copy the response to the system clipboard")
    rn.add_argument("--level", type=int, choices=[1, 2, 3, 4])
    rn.add_argument("--domain",
                    choices=["code", "writing", "analysis", "creative",
                             "research", "personal", "other"])
    rn.add_argument("--runner",
                    choices=["auto", "gemini", "groq", "cerebras", "ollama"],
                    help="Force a specific runner (default: auto)")
    rn.set_defaults(func=cmd_run)

    rs = subs.add_parser("runners",
                         help="List available runners and configuration status")
    rs.set_defaults(func=cmd_runners)

    dr = subs.add_parser("doctor",
                         help="Detect hardware + recommend optimal runner/model")
    dr.set_defaults(func=cmd_doctor)

    w = subs.add_parser("web",
                        help="Launch a local web UI in your browser")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=7788)
    w.add_argument("--no-browser", action="store_true",
                   help="Don't auto-open browser")
    w.set_defaults(func=cmd_web)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    # Auto-init DB on first run
    if not DB_PATH.exists() and args.cmd != "init":
        init_db()
    args.func(args)


if __name__ == "__main__":
    main()
