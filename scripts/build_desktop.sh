#!/bin/bash
# Build script for CraftML Studio desktop app

set -e

echo "🏗️  Building CraftML Studio Desktop App..."

# Resolve absolute path of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build backend sidecar (PyInstaller)
echo "🧩 Building backend sidecar (PyInstaller)..."
cd "$SCRIPT_DIR/../apps/backend"
PYTHON_EXE="python3"
if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
  PYTHON_EXE="python"
fi
"$PYTHON_EXE" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$PYTHON_EXE" -m pip install pyinstaller >/dev/null 2>&1 || true
"$PYTHON_EXE" -m PyInstaller --onefile --name craftml-backend run_server.py

# Copy sidecar into Tauri bin
SIDECAR_SRC="$(pwd)/dist/craftml-backend"
SIDECAR_DST_DIR="$SCRIPT_DIR/../apps/desktop/src-tauri/bin"
mkdir -p "$SIDECAR_DST_DIR"

# Determine host triple (requires rustc)
TRIPLE="$(rustc -vV 2>/dev/null | sed -n 's/^host: //p')"
if [ -z "$TRIPLE" ]; then
  # Fallbacks
  case "$(uname -s)" in
    Darwin) TRIPLE="$(uname -m)-apple-darwin" ;;
    Linux) TRIPLE="$(uname -m)-unknown-linux-gnu" ;;
    *) TRIPLE="unknown-unknown-unknown" ;;
  esac
fi

# Copy sidecar with expected tauri v2 suffix naming
if [ -f "$SIDECAR_SRC.exe" ]; then
  cp "$SIDECAR_SRC.exe" "$SIDECAR_DST_DIR/craftml-backend.exe-$TRIPLE.exe"
elif [ -f "$SIDECAR_SRC" ]; then
  cp "$SIDECAR_SRC" "$SIDECAR_DST_DIR/craftml-backend-$TRIPLE"
else
  echo "❌ Sidecar not found at $SIDECAR_SRC"
  exit 1
fi

# Navigate to desktop app directory
cd "$SCRIPT_DIR/../apps/desktop"

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

