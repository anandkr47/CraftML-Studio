# Development script for CraftML Studio (Windows)

Write-Host "🚀 Starting CraftML Studio in development mode..." -ForegroundColor Cyan

# Check if Python backend should be started separately
if ($args[0] -eq "--backend-only") {
    Write-Host "🐍 Starting backend only..." -ForegroundColor Yellow
    Set-Location "$PSScriptRoot\..\apps\backend"
    python main.py
    exit 0
}

# Check if frontend should be started separately
if ($args[0] -eq "--frontend-only") {
    Write-Host "⚛️  Starting frontend only..." -ForegroundColor Yellow
    Set-Location "$PSScriptRoot\..\apps\desktop"
    npm run tauri dev
    exit 0
}

# Start both
Write-Host "🔧 Starting full stack development environment..." -ForegroundColor Cyan
Write-Host "📝 Backend will auto-start from Tauri" -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\apps\desktop"

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
    npm install
}

npm run tauri dev

