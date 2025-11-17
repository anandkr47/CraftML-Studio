#!/bin/bash
# Build script for CraftML Studio desktop app

set -e

echo "🏗️  Building CraftML Studio Desktop App..."

# Resolve absolute path of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build backend sidecar (Nuitka)
echo "🧩 Building backend sidecar (Nuitka)..."
cd "$SCRIPT_DIR/.."
PYTHON_EXE="python3"
if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
  PYTHON_EXE="python"
fi
"$PYTHON_EXE" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$PYTHON_EXE" -m pip install nuitka >/dev/null 2>&1 || true
"$PYTHON_EXE" -m nuitka --standalone \
  --remove-output \
  --output-dir=dist \
  --output-filename=main \
  --include-data-file=apps/backend/main.py=main.py \
  --include-data-dir=apps/backend/api=api \
  --include-data-dir=apps/backend/services=services \
  --include-data-dir=apps/backend/db=db \
  --include-data-dir=apps/backend/models=models \
  --include-data-dir=apps/backend/tasks=tasks \
  --include-data-dir=core=core \
  --include-data-dir=plugins=plugins \
  --include-data-dir=resources=resources \
  --include-package=uvicorn \
  --include-package=uvicorn.logging \
  --include-package=uvicorn.loops \
  --include-package=uvicorn.protocols \
  --include-package=uvicorn.lifespan \
  --include-package=click \
  --include-package=celery \
  --include-package=kombu \
  --include-package=redis \
  --include-package=core \
  --include-package=plugins \
  --include-package=fastapi \
  --include-package=pydantic \
  --include-package=starlette \
  --plugin-disable=transformers \
  --nofollow-import-to=transformers \
  --nofollow-import-to=torch \
  apps/backend/run_server.py

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

