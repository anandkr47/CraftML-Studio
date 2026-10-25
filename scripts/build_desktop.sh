#!/bin/bash
# Build the CraftML Studio desktop app (macOS / Linux).
#
#   ./scripts/build_desktop.sh [--clean] [--updater]
#
# --updater also produces signed auto-update bundles; it needs TAURI_SIGNING_PRIVATE_KEY (and
# TAURI_SIGNING_PRIVATE_KEY_PASSWORD) for the key whose public half is in tauri.conf.json.
#
# 1. Installs the backend's locked dependencies into apps/backend/venv (same venv as setup.sh).
# 2. Packages the backend with PyInstaller (craftml-backend.spec, one-folder build).
# 3. Packs it into apps/desktop/src-tauri/bin/backend.tar.gz and runs `tauri build`.

set -euo pipefail

CLEAN=false
UPDATER=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--clean) CLEAN=true; shift ;;
    --updater) UPDATER=true; shift ;;
    *) echo "❌ Unknown option: $1"; echo "Usage: $0 [--clean|-c] [--updater]"; exit 1 ;;
  esac
done
if [ "$UPDATER" = true ] && [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  echo "❌ --updater needs TAURI_SIGNING_PRIVATE_KEY (see 'npx tauri signer generate')."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/backend"
VENV_DIR="$BACKEND_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "🏗️  Building CraftML Studio desktop app..."

# --- Python environment -------------------------------------------------------------------
if [ ! -x "$VENV_PYTHON" ]; then
  SYSTEM_PYTHON="$(command -v python3 || command -v python || true)"
  if [ -z "$SYSTEM_PYTHON" ]; then
    echo "❌ Python 3.11 or 3.12 is required (python3 not found on PATH)."
    exit 1
  fi
  echo "📦 Creating virtual environment in apps/backend/venv..."
  "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
fi

echo "📦 Installing backend dependencies (locked versions)..."
"$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
"$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -r "$BACKEND_DIR/requirements-build.txt" \
  -c "$BACKEND_DIR/requirements.lock.txt"

if [ "$(uname -s)" = "Darwin" ]; then
  LLAMA_INDEX="https://abetlen.github.io/llama-cpp-python/whl/metal"
else
  LLAMA_INDEX="https://abetlen.github.io/llama-cpp-python/whl/cpu"
fi
"$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements-gguf.txt" --prefer-binary --extra-index-url "$LLAMA_INDEX" \
  || echo "⚠️  Optional GGUF support (llama-cpp-python) not installed; the build will not include it."

# --- Backend sidecar (PyInstaller) --------------------------------------------------------
echo "🧩 Packaging the backend (PyInstaller)..."
cd "$ROOT_DIR"
PYI_ARGS=(--noconfirm --distpath "$ROOT_DIR/dist" --workpath "$ROOT_DIR/build/pyinstaller")
if [ "$CLEAN" = true ]; then
  PYI_ARGS+=(--clean)
fi
"$VENV_PYTHON" -m PyInstaller "${PYI_ARGS[@]}" craftml-backend.spec

# One archive, so symlinks and permissions survive Tauri's resource copy (see scripts/pack_sidecar.py).
SIDECAR_DST_DIR="$ROOT_DIR/apps/desktop/src-tauri/bin"
find "$SIDECAR_DST_DIR" -mindepth 1 -maxdepth 1 ! -name README.md -exec rm -rf {} +
"$VENV_PYTHON" "$ROOT_DIR/scripts/pack_sidecar.py" "$ROOT_DIR/dist/craftml-backend" "$SIDECAR_DST_DIR/backend.tar.gz"

# --- Desktop app --------------------------------------------------------------------------
cd "$ROOT_DIR/apps/desktop"
if [ ! -d node_modules ]; then
  echo "📦 Installing frontend dependencies..."
  npm ci
fi
echo "🔨 Building the Tauri application..."
if [ "$UPDATER" = true ]; then
  npm run tauri build -- --config '{"bundle":{"createUpdaterArtifacts":true}}'
else
  npm run tauri build
fi

echo "✅ Build complete. Installers: apps/desktop/src-tauri/target/release/bundle/"
