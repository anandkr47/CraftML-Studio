#!/bin/bash
# Setup script for CraftML Studio development environment

set -e

echo "🎨 CraftML Studio - Setup Script"
echo "================================"

# Check Python
echo "🐍 Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+"
    exit 1
fi
python3 --version

# Check Node.js
echo "📦 Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+"
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
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "📦 Installing frontend dependencies..."
cd ../desktop
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start development:"
echo "  ./scripts/dev.sh"
echo ""
echo "To build the app:"
echo "  ./scripts/build_desktop.sh"

