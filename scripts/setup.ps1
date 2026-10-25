# Setup script for CraftML Studio development environment (Windows)

Write-Host "CraftML Studio - Setup Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check Python: 3.11 or 3.12 (the versions the lock file and CI are tested with)
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pyExe = $null; $pyArgs = @()
$probe = 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 12) else 1)'
foreach ($v in @("3.12", "3.11")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py "-$v" -c $probe 2>$null
        if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyArgs = @("-$v"); break }
    }
}
if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c $probe 2>$null
    if ($LASTEXITCODE -eq 0) { $pyExe = "python" }
}
if (-not $pyExe) {
    Write-Host "ERROR: Python 3.11 or 3.12 is required. Install it from https://www.python.org/downloads/ (or: winget install Python.Python.3.12)" -ForegroundColor Red
    exit 1
}
& $pyExe @pyArgs --version

# Check Node.js (Vite 7 needs 20.19+)
Write-Host "Checking Node.js installation..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js is not installed. Please install Node.js 20.19 or newer (https://nodejs.org/)" -ForegroundColor Red
    exit 1
}
node -e "const [a,b]=process.versions.node.split('.').map(Number); process.exit(a>20||(a===20&&b>=19)?0:1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Node.js $(node --version) is too old; 20.19 or newer is required." -ForegroundColor Red
    exit 1
}
Write-Host "Node: $(node --version)  npm: $(npm --version)" -ForegroundColor Green

# Check Rust
Write-Host "Checking Rust installation..." -ForegroundColor Yellow
try {
    $rustVersion = rustc --version
    Write-Host $rustVersion -ForegroundColor Green
} catch {
    Write-Host "ERROR: Rust is not installed. Please install Rust from https://rustup.rs/" -ForegroundColor Red
    exit 1
}

# Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\apps\backend"

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $pyExe @pyArgs -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: could not create the virtual environment" -ForegroundColor Red; exit 1 }
}

# Use the venv's interpreter directly (no activation, so execution policy can't redirect pip).
$venvPy = Join-Path (Get-Location) "venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip

# PyPI's Windows torch wheels are CPU-only. With an NVIDIA driver present, install the CUDA build of
# the locked torch version first; the lock constraint (torch==X) accepts the +cu126 build.
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $torchPin = (Select-String -Path requirements.lock.txt -Pattern '^torch==(.+)$').Matches[0].Groups[1].Value
    Write-Host "NVIDIA GPU detected: installing torch $torchPin with CUDA 12.6..." -ForegroundColor Yellow
    & $venvPy -m pip install "torch==$torchPin" --index-url https://download.pytorch.org/whl/cu126
    if ($LASTEXITCODE -ne 0) { Write-Warning "CUDA build of torch could not be installed; falling back to the CPU build." }
}

& $venvPy -m pip install -r requirements.txt -r requirements-dev.txt -c requirements.lock.txt   # exact tested versions
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: installing the backend dependencies failed (see above)." -ForegroundColor Red
    exit 1
}

# Optional GGUF support (llama.cpp). Best effort: prebuilt wheels first, never fatal.
Write-Host "Installing optional GGUF support (llama-cpp-python)..." -ForegroundColor Yellow
& $venvPy -m pip install -r requirements-gguf.txt --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if ($LASTEXITCODE -ne 0) {
    Write-Warning "GGUF support could not be installed (needs Visual Studio Build Tools to build). Everything else works; install later with: venv\Scripts\python.exe -m pip install -r apps\backend\requirements-gguf.txt"
}

Write-Host ""
Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location ..\desktop
npm ci
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: npm ci failed" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start development:" -ForegroundColor Cyan
Write-Host "  .\scripts\dev.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To build the app:" -ForegroundColor Cyan
Write-Host "  .\scripts\build_desktop.ps1" -ForegroundColor White

