param(
    [switch]$Clean,
    [switch]$Updater
)

# Build the CraftML Studio desktop app (Windows).
#
#   .\scripts\build_desktop.ps1 [-Clean] [-Updater]
#
# -Updater also produces signed auto-update bundles; it needs TAURI_SIGNING_PRIVATE_KEY (and
# TAURI_SIGNING_PRIVATE_KEY_PASSWORD) for the key whose public half is in tauri.conf.json.
#
# 1. Installs the backend's locked dependencies into apps\backend\venv (same venv as setup.ps1).
# 2. Packages the backend with PyInstaller (craftml-backend.spec, one-folder build).
# 3. Packs it into apps\desktop\src-tauri\bin\backend.tar.gz and runs `tauri build`.

$ErrorActionPreference = "Stop"

if ($Updater -and -not $env:TAURI_SIGNING_PRIVATE_KEY) {
    Write-Host "ERROR: -Updater needs TAURI_SIGNING_PRIVATE_KEY (see 'npx tauri signer generate')." -ForegroundColor Red
    exit 1
}

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments, [string]$What)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $What failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Building CraftML Studio desktop app..." -ForegroundColor Cyan

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $rootDir "apps\backend"
$venvDir = Join-Path $backendDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

# --- Python environment -------------------------------------------------------------------
if (-not (Test-Path $venvPython)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $pyExe = $python.Source; $pyArgs = @()
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $pyExe = "py"; $pyArgs = @("-3")
    } else {
        Write-Host "ERROR: Python 3.11 or 3.12 is required (python / py not found on PATH)." -ForegroundColor Red
        exit 1
    }
    Write-Host "Creating virtual environment in apps\backend\venv..." -ForegroundColor Yellow
    Invoke-Checked $pyExe ($pyArgs + @("-m", "venv", $venvDir)) "Creating the virtual environment"
}

Write-Host "Installing backend dependencies (locked versions)..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip | Out-Null
# PyPI's Windows torch wheels are CPU-only; on a machine with an NVIDIA driver, bundle the CUDA build
# of the locked torch version (it still runs on machines without a GPU).
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $lockFile = Join-Path $backendDir "requirements.lock.txt"
    $torchPin = (Select-String -Path $lockFile -Pattern '^torch==(.+)$').Matches[0].Groups[1].Value
    & $venvPython -m pip install "torch==$torchPin" --index-url https://download.pytorch.org/whl/cu126
    if ($LASTEXITCODE -ne 0) { Write-Warning "CUDA build of torch could not be installed; using the CPU build." }
}
Invoke-Checked $venvPython @(
    "-m", "pip", "install",
    "-r", (Join-Path $backendDir "requirements.txt"),
    "-r", (Join-Path $backendDir "requirements-build.txt"),
    "-c", (Join-Path $backendDir "requirements.lock.txt")
) "Installing backend dependencies"

& $venvPython -m pip install -r (Join-Path $backendDir "requirements-gguf.txt") --prefer-binary `
    --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/cpu"
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Optional GGUF support (llama-cpp-python) not installed; the build will not include it."
}

# --- Backend sidecar (PyInstaller) --------------------------------------------------------
Write-Host "Packaging the backend (PyInstaller)..." -ForegroundColor Yellow
Set-Location $rootDir

# A running backend keeps its files locked.
Get-Process -Name "craftml-backend" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$pyiArgs = @("-m", "PyInstaller", "--noconfirm",
    "--distpath", (Join-Path $rootDir "dist"),
    "--workpath", (Join-Path $rootDir "build\pyinstaller"))
if ($Clean) { $pyiArgs += "--clean" }
Invoke-Checked $venvPython ($pyiArgs + @("craftml-backend.spec")) "PyInstaller"

# One archive, so symlinks and permissions survive Tauri's resource copy (see scripts\pack_sidecar.py).
$sidecarDstDir = Join-Path $rootDir "apps\desktop\src-tauri\bin"
New-Item -ItemType Directory -Force -Path $sidecarDstDir | Out-Null
Get-ChildItem -Path $sidecarDstDir -Force | Where-Object { $_.Name -ne "README.md" } | Remove-Item -Recurse -Force
Invoke-Checked $venvPython @((Join-Path $rootDir "scripts\pack_sidecar.py"), (Join-Path $rootDir "dist\craftml-backend"), (Join-Path $sidecarDstDir "backend.tar.gz")) "Packing the backend"

# --- Desktop app --------------------------------------------------------------------------
Set-Location (Join-Path $rootDir "apps\desktop")
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Invoke-Checked "npm" @("ci") "npm ci"
}
Write-Host "Building the Tauri application..." -ForegroundColor Yellow
if ($Updater) {
    # PowerShell would strip the inner quotes of an inline JSON argument; pass a config file instead.
    $updaterConfig = Join-Path $env:TEMP "craftml-updater.json"
    Set-Content -Path $updaterConfig -Value '{"bundle":{"createUpdaterArtifacts":true}}' -Encoding ascii
    Invoke-Checked "npm" @("run", "tauri", "build", "--", "--config", $updaterConfig) "tauri build"
} else {
    Invoke-Checked "npm" @("run", "tauri", "build") "tauri build"
}

Write-Host "Build complete. Installers: apps\desktop\src-tauri\target\release\bundle\" -ForegroundColor Green
