#!/bin/bash
# Development script for CraftML Studio

set -e

echo "🚀 Starting CraftML Studio in development mode..."

# Check if Python backend should be started separately
if [ "$1" == "--backend-only" ]; then
    echo "🐍 Starting backend only..."
    cd "$(dirname "$0")/../apps/backend"
    python main.py
    exit 0
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

