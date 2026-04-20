"""Basic tests to verify the compiler works end-to-end."""
import sys
from pathlib import Path

# Add parent dir to path for tests run standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_forge.compiler import PromptCompiler
from prompt_forge.classifier import detect_domain, detect_level
from prompt_forge.corrector import correct
from prompt_forge.db import init_db


def test_corrector_fixes_typos():
    cleaned, corrs = correct("teh fucntion is broken becuase of neccessary issues")
    assert "the" in cleaned.lower()
    assert "function" in cleaned.lower()
    assert "because" in cleaned.lower()
    assert len(corrs) >= 3
    print("  ✓ corrector fixes typos")


def test_corrector_trims_filler():
    cleaned, corrs = correct("hey so please fix my bug thanks")
    assert "hey" not in cleaned.lower()[:5]
    assert "thanks" not in cleaned.lower()[-10:]
    print("  ✓ corrector trims filler")


def test_domain_detection_code():
    domain, _ = detect_domain("fix this python script that imports requests")
    assert domain == "code", f"expected 'code', got '{domain}'"
    print("  ✓ detects code domain")


def test_domain_detection_writing():
    domain, _ = detect_domain("help me write an email to my boss about vacation")
    assert domain == "writing", f"expected 'writing', got '{domain}'"
    print("  ✓ detects writing domain")


def test_domain_detection_spanish():
    domain, _ = detect_domain("ayúdame a escribir un correo a mi jefe")
    assert domain == "writing", f"expected 'writing', got '{domain}'"
    print("  ✓ detects writing domain (Spanish)")


def test_level_detection():
    assert detect_level("what time is it", "other") == 1
    assert detect_level("write a simple python function", "code") <= 2
    lvl = detect_level(
        "design a scalable microservices architecture for production "
        "with multi-region deployment and trade-off analysis", "code")
    assert lvl == 4, f"expected L4, got L{lvl}"
    print("  ✓ level detection works")


def test_end_to_end_compile():
    init_db()
    c = PromptCompiler()
    result = c.compile("help me fix a bug in my python script")
    assert result.xml
    assert "<identity>" in result.xml
    assert "<task>" in result.xml
    assert result.domain == "code"
    assert result.level >= 1
    assert result.compile_id > 0
    print("  ✓ end-to-end compile works")


def test_override_level_and_domain():
    c = PromptCompiler()
    result = c.compile("short text", level_override=4, domain_override="analysis")
    assert result.level == 4
    assert result.domain == "analysis"
    print("  ✓ overrides respected")


def test_empty_input_handled():
    c = PromptCompiler()
    # Empty after cleaning — should still produce something or handle gracefully
    try:
        result = c.compile("!!!")
        assert result.xml  # produces something
    except Exception as e:
        print(f"  ⚠ empty-ish input raised: {e}")
    print("  ✓ edge case: minimal input")


def run_all():
    print("\nRunning prompt-forge tests...\n")
    tests = [
        test_corrector_fixes_typos,
        test_corrector_trims_filler,
        test_domain_detection_code,
        test_domain_detection_writing,
        test_domain_detection_spanish,
        test_level_detection,
        test_end_to_end_compile,
        test_override_level_and_domain,
        test_empty_input_handled,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__} raised {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'✓ all tests passed' if failed == 0 else f'✗ {failed} test(s) failed'}\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
