#!/bin/bash
# Setup script for CraftML Studio development environment

set -e

echo "🎨 CraftML Studio - Setup Script"
echo "================================"

# Check Python: 3.11 or 3.12 (the versions the lock file and CI are tested with)
echo "🐍 Checking Python installation..."
PYTHON=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" &> /dev/null && "$candidate" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 12) else 1)'; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.11 or 3.12 is required (found: $(python3 --version 2>&1 || echo none))."
    echo "   macOS: brew install python@3.12   Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
"$PYTHON" --version

# Check Node.js (Vite 7 needs 20.19+)
echo "📦 Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20.19 or newer (https://nodejs.org/)"
    exit 1
fi
if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=19)?0:1)'; then
    echo "❌ Node.js $(node --version) is too old; 20.19 or newer is required."
    exit 1
fi
node --version
npm --version

# Check Rust
echo "🦀 Checking Rust installation..."
if ! command -v rustc &> /dev/null; then
    echo "❌ Rust is not installed. Please install Rust from https://rustup.rs/"
    exit 1
fi
rustc --version

# Install Python dependencies
echo ""
echo "📚 Installing Python dependencies..."
cd "$(dirname "$0")/../apps/backend"
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv venv
fi

VENV_PY="venv/bin/python"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r requirements.txt -r requirements-dev.txt -c requirements.lock.txt   # exact tested versions

# Optional GGUF support (llama.cpp). Best effort: prebuilt wheels first, never fatal.
echo ""
echo "🦙 Installing optional GGUF support (llama-cpp-python)..."
if [ "$(uname -s)" = "Darwin" ]; then LLAMA_INDEX="https://abetlen.github.io/llama-cpp-python/whl/metal"; else LLAMA_INDEX="https://abetlen.github.io/llama-cpp-python/whl/cpu"; fi
if ! "$VENV_PY" -m pip install -r requirements-gguf.txt --prefer-binary --extra-index-url "$LLAMA_INDEX"; then
    echo "⚠️  GGUF support could not be installed (needs a C/C++ toolchain to build). Everything else works;"
    echo "    install it later with: apps/backend/venv/bin/python -m pip install -r apps/backend/requirements-gguf.txt"
fi

echo ""
echo "📦 Installing frontend dependencies..."
cd ../desktop
npm ci

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start development:"
echo "  ./scripts/dev.sh"
echo ""
echo "To build the app:"
echo "  ./scripts/build_desktop.sh"

