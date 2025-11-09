# Build script for CraftML Studio desktop app (Windows)

Write-Host "Building CraftML Studio Desktop App..." -ForegroundColor Cyan

# Ensure venv is active for Python builds if present
if (Test-Path "$PSScriptRoot\..\apps\backend\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
    . "$PSScriptRoot\..\apps\backend\.venv\Scripts\Activate.ps1"
}

# Build backend sidecar (PyInstaller)
Write-Host "Building backend sidecar (PyInstaller)..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\apps\backend"

# Choose Python executable: prefer 'python', then 'py -3.10'
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3.10"
} else {
    Write-Error "No suitable Python runtime found. Please install Python 3.10+ and ensure 'python' or 'py' is on PATH."
    exit 1
}

# Install PyInstaller for current user to avoid permission issues
Invoke-Expression "$pythonCmd -m pip install --user pyinstaller" | Out-Null

# Build EXE (use local entry script path)
Invoke-Expression "$pythonCmd -m PyInstaller --onefile --name craftml-backend run_server.py"

# Copy sidecar into Tauri bin
$SidecarSrc = "$PSScriptRoot\..\apps\backend\dist\craftml-backend.exe"
$SidecarDstDir = "$PSScriptRoot\..\apps\desktop\src-tauri\bin"
New-Item -ItemType Directory -Force -Path $SidecarDstDir | Out-Null
if (Test-Path $SidecarSrc) {
    Copy-Item $SidecarSrc $SidecarDstDir -Force
    # Also create target-triple suffixed copy for Tauri v2 sidecar lookup on Windows
    $TargetTriple = "x86_64-pc-windows-msvc"
    $SuffixedPath = Join-Path $SidecarDstDir ("craftml-backend.exe-$TargetTriple.exe")
    Copy-Item $SidecarSrc $SuffixedPath -Force
} else {
    Write-Error "Backend EXE not found at $SidecarSrc. Ensure Python 3.10+ is installed and PyInstaller succeeded."
    exit 1
}

# Navigate to desktop app directory
Set-Location "$PSScriptRoot\..\apps\desktop"

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

# Build the Tauri app
Write-Host "Building Tauri application..." -ForegroundColor Yellow
npm run tauri build

Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Installers can be found in: apps\desktop\src-tauri\target\release\bundle\" -ForegroundColor Green

