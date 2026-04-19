#!/usr/bin/env bash
# Run all Prompt Forge tests.
set -e
cd "$(dirname "$0")"

echo "════════════════════════════════════════"
echo "  Running all Prompt Forge tests"
echo "════════════════════════════════════════"

python3 tests/test_compiler.py
echo ""
python3 tests/test_integration.py
