# Setup script for CraftML Studio development environment (Windows)

Write-Host "🎨 CraftML Studio - Setup Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check Python
Write-Host "🐍 Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed. Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Check Node.js
Write-Host "📦 Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    $npmVersion = npm --version
    Write-Host "Node: $nodeVersion" -ForegroundColor Green
    Write-Host "npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js is not installed. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# Check Rust
Write-Host "🦀 Checking Rust installation..." -ForegroundColor Yellow
try {
    $rustVersion = rustc --version
    Write-Host $rustVersion -ForegroundColor Green
} catch {
    Write-Host "❌ Rust is not installed. Please install Rust from https://rustup.rs/" -ForegroundColor Red
    exit 1
}

# Install Python dependencies
Write-Host ""
Write-Host "📚 Installing Python dependencies..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\apps\backend"

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location ..\desktop
npm install

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start development:" -ForegroundColor Cyan
Write-Host "  .\scripts\dev.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To build the app:" -ForegroundColor Cyan
Write-Host "  .\scripts\build_desktop.ps1" -ForegroundColor White

