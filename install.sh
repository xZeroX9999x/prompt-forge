#!/usr/bin/env bash
set -e

echo "═══════════════════════════════════════════"
echo "   Prompt Forge — install (Linux / macOS)"
echo "═══════════════════════════════════════════"

# Check python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VERSION detected"

# Create venv
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate
echo "✓ venv activated"

# Install
echo "→ Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet -e .
echo "✓ Dependencies installed"

# Init DB
echo "→ Initializing database..."
python3 forge.py init
echo ""
echo "═══════════════════════════════════════════"
echo "   ✓ Installation complete"
echo "═══════════════════════════════════════════"
echo ""
echo "Activate the environment before using:"
echo "  source .venv/bin/activate"
echo ""
echo "Then try:"
echo '  forge compile "help me write an email declining a meeting"'
echo '  forge learn       # fetch latest techniques from the web'
echo "  forge stats       # see your usage"
echo ""
