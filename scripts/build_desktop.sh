#!/bin/bash
# Build script for CraftML Studio desktop app

set -e

echo "🏗️  Building CraftML Studio Desktop App..."

# Build backend sidecar (PyInstaller)
echo "🧩 Building backend sidecar (PyInstaller)..."
cd "$(dirname "$0")/../apps/backend"
python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install pyinstaller >/dev/null 2>&1 || true
python3 -m PyInstaller --onefile --name craftml-backend apps/backend/run_server.py

# Copy sidecar into Tauri bin
SIDECAR_SRC="$(pwd)/dist/craftml-backend"
SIDECAR_DST_DIR="$(dirname "$0")/../apps/desktop/src-tauri/bin"
mkdir -p "$SIDECAR_DST_DIR"
if [ -f "$SIDECAR_SRC.exe" ]; then
  cp "$SIDECAR_SRC.exe" "$SIDECAR_DST_DIR/"
elif [ -f "$SIDECAR_SRC" ]; then
  cp "$SIDECAR_SRC" "$SIDECAR_DST_DIR/"
fi

# Navigate to desktop app directory
cd "$(dirname "$0")/../apps/desktop"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Build the Tauri app
echo "🔨 Building Tauri application..."
npm run tauri build

echo "✅ Build complete!"
echo "📦 Installers can be found in: apps/desktop/src-tauri/target/release/bundle/"

