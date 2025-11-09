#!/bin/bash
# Build script for CraftML Studio desktop app

set -e

echo "🏗️  Building CraftML Studio Desktop App..."

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

