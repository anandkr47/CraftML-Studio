#!/bin/bash
# Development script for CraftML Studio

set -e

echo "🚀 Starting CraftML Studio in development mode..."

# Check if Python backend should be started separately
if [ "$1" == "--backend-only" ]; then
    echo "🐍 Starting backend only..."
    cd "$(dirname "$0")/../apps/backend"
    PY="${CRAFTML_PYTHON:-}"
    if [ -z "$PY" ]; then
        for c in venv/bin/python .venv/bin/python; do [ -x "$c" ] && PY="$c" && break; done
    fi
    if [ -z "$PY" ]; then
        echo "❌ No virtualenv found in apps/backend. Run ./scripts/setup.sh first (or set CRAFTML_PYTHON)."
        exit 1
    fi
    exec "$PY" run_server.py "${@:2}"
fi

# Check if frontend should be started separately
if [ "$1" == "--frontend-only" ]; then
    echo "⚛️  Starting frontend only..."
    cd "$(dirname "$0")/../apps/desktop"
    npm run tauri dev
    exit 0
fi

# Start both
echo "🔧 Starting full stack development environment..."
echo "📝 Backend will auto-start from Tauri"
cd "$(dirname "$0")/../apps/desktop"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

npm run tauri dev

