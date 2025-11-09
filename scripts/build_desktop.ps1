# Build script for CraftML Studio desktop app (Windows)

Write-Host "🏗️  Building CraftML Studio Desktop App..." -ForegroundColor Cyan

# Navigate to desktop app directory
Set-Location "$PSScriptRoot\..\apps\desktop"

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

# Build the Tauri app
Write-Host "🔨 Building Tauri application..." -ForegroundColor Yellow
npm run tauri build

Write-Host "✅ Build complete!" -ForegroundColor Green
Write-Host "📦 Installers can be found in: apps\desktop\src-tauri\target\release\bundle\" -ForegroundColor Green

