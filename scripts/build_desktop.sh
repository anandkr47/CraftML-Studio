#!/bin/bash
# Build script for CraftML Studio desktop app

set -e

CLEAN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--clean)
      CLEAN=true
      shift
      ;;
    *)
      echo "❌ Unknown option: $1"
      echo "Usage: $0 [--clean|-c]"
      exit 1
      ;;
  esac
done

echo "🏗️  Building CraftML Studio Desktop App..."

# Resolve absolute path of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

# Ensure venv exists and is active for Python builds
VENV_DIR="$ROOT_DIR/apps/backend/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "📦 Creating Python virtual environment..."
  # Choose Python executable: prefer python3, then python
  SYSTEM_PYTHON="python3"
  if ! command -v "$SYSTEM_PYTHON" >/dev/null 2>&1; then
    SYSTEM_PYTHON="python"
  fi
  if ! command -v "$SYSTEM_PYTHON" >/dev/null 2>&1; then
    echo "❌ No suitable Python runtime found. Please install Python 3.10+ and ensure 'python3' or 'python' is on PATH."
    exit 1
  fi
  
  "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
  if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment."
    exit 1
  fi
fi

# Activate virtual environment
if [ -f "$VENV_DIR/bin/activate" ]; then
  echo "🔌 Activating Python virtual environment..."
  source "$VENV_DIR/bin/activate"
fi

# Install backend dependencies
REQUIREMENTS_FILE="$ROOT_DIR/apps/backend/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
  echo "📦 Installing backend dependencies..."
  "$VENV_PYTHON" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
  if [ $? -ne 0 ]; then
    echo "❌ Failed to install backend dependencies."
    exit 1
  fi
else
  echo "⚠️  requirements.txt not found at $REQUIREMENTS_FILE. Some dependencies may be missing."
fi

# Build backend sidecar (Nuitka)
echo "🧩 Building backend sidecar (Nuitka)..."
cd "$ROOT_DIR"

DIST_DIR="$ROOT_DIR/dist/main.dist"
BUILD_DIR="$ROOT_DIR/dist/main.build"
if [ "$CLEAN" = true ]; then
  echo "🧹 Clean mode: removing previous Nuitka outputs..."
  rm -rf "$DIST_DIR" "$BUILD_DIR"
else
  echo "⚡ Incremental mode: keeping Nuitka build cache (run with --clean to force a full rebuild)."
fi

# Use venv Python if available, otherwise fall back to system Python
PYTHON_EXE="$VENV_PYTHON"
if [ ! -f "$PYTHON_EXE" ]; then
  # Fallback to system Python
  PYTHON_EXE="python3"
  if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
    PYTHON_EXE="python"
  fi
  if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
    echo "❌ No suitable Python runtime found. Please install Python 3.10+ and ensure 'python3' or 'python' is on PATH."
    exit 1
  fi
fi

# Ensure Nuitka is available in the venv
echo "📦 Ensuring Nuitka is installed..."
"$PYTHON_EXE" -m pip install nuitka >/dev/null 2>&1 || true
if [ $? -ne 0 ]; then
  echo "❌ Failed to install Nuitka."
  exit 1
fi

USE_CLANG=false
CLANG_BIN=""
if command -v clang >/dev/null 2>&1; then
  USE_CLANG=true
  CLANG_BIN="$(command -v clang)"
elif command -v clang-cl >/dev/null 2>&1; then
  USE_CLANG=true
  CLANG_BIN="$(command -v clang-cl)"
fi

if [ "$USE_CLANG" = true ]; then
  echo "🟢 Clang detected at $CLANG_BIN. Enabling --clang for Nuitka."
else
  echo "⚠️  Clang not detected. Using default compiler toolchain."
fi

NUITKA_ARGS=(
  -m nuitka
  --standalone
  --jobs=0
  --output-dir=dist
  --output-filename=main
  --include-package=api
  --include-package=services
  --include-package=db
  --include-package=models
  --include-package=core
  --include-data-dir=resources=resources
  --include-package=uvicorn
  --include-package=fastapi
  --include-package=starlette
  --include-package=pydantic
  --enable-plugin=dill-compat
  --plugin-disable=transformers
  --nofollow-import-to=transformers
  --nofollow-import-to=torch
  apps/backend/run_server.py
)

if [ "$CLEAN" = true ]; then
  NUITKA_ARGS+=(--remove-output)
fi

if [ "$USE_CLANG" = true ]; then
  NUITKA_ARGS+=(--clang)
fi

"$PYTHON_EXE" "${NUITKA_ARGS[@]}"
  --remove-output \
  --jobs=0 \
  --output-dir=dist \
  --output-filename=main \
  --include-package=api \
  --include-package=services \
  --include-package=db \
  --include-package=models \
  --include-package=core \
  --include-data-dir=resources=resources \
# Copy entire backend directory into Tauri bin (--standalone includes all dependencies)
# Nuitka creates dist/main.dist/ with main + all .so, .dylib files, etc.
SIDECAR_SRC_DIR="$(pwd)/dist/main.dist"
SIDECAR_DST_DIR="$SCRIPT_DIR/../apps/desktop/src-tauri/bin"
mkdir -p "$SIDECAR_DST_DIR"

# Clean old sidecar files to avoid duplicates
rm -rf "$SIDECAR_DST_DIR"/main*

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

# Copy all files from dist/main.dist/ to bin/ (includes main + all dependencies)
if [ -d "$SIDECAR_SRC_DIR" ]; then
  cp -r "$SIDECAR_SRC_DIR"/* "$SIDECAR_DST_DIR/"
  
  # Rename main to main-TRIPLE for Tauri v2 naming
  if [ -f "$SIDECAR_DST_DIR/main.exe" ]; then
    mv "$SIDECAR_DST_DIR/main.exe" "$SIDECAR_DST_DIR/main-$TRIPLE.exe"
    echo "✅ Backend directory copied and EXE renamed to: main-$TRIPLE.exe"
  elif [ -f "$SIDECAR_DST_DIR/main" ]; then
    mv "$SIDECAR_DST_DIR/main" "$SIDECAR_DST_DIR/main-$TRIPLE"
    chmod +x "$SIDECAR_DST_DIR/main-$TRIPLE"
    echo "✅ Backend directory copied and executable renamed to: main-$TRIPLE"
  else
    echo "❌ Backend executable not found in $SIDECAR_SRC_DIR"
    exit 1
  fi
else
  echo "❌ Backend directory not found at $SIDECAR_SRC_DIR"
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

