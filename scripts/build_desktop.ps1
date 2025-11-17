# Build script for CraftML Studio desktop app (Windows)

Write-Host "Building CraftML Studio Desktop App..." -ForegroundColor Cyan

# Resolve key directories
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Resolve-Path (Join-Path $scriptDir "..")).Path

# Ensure venv exists and is active for Python builds
$venvDir = Join-Path $rootDir "apps\backend\.venv"
$venvActivate = Join-Path $venvDir "Scripts\Activate.ps1"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    # Choose Python executable: prefer 'python', then 'py -3.10'
    $pythonCmd = $null
    $pythonArgsBase = @()
    if ($cmd = Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd.Source
    } elseif ($cmd = Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd.Source
        $pythonArgsBase += '-3.10'
    } else {
        Write-Error "No suitable Python runtime found. Please install Python 3.10+ and ensure 'python' or 'py' is on PATH."
        exit 1
    }
    
    $venvArgs = $pythonArgsBase + @('-m', 'venv', $venvDir)
    $venvProcess = Start-Process -FilePath $pythonCmd -ArgumentList $venvArgs -NoNewWindow -Wait -PassThru
    if ($venvProcess.ExitCode -ne 0) {
        Write-Error "Failed to create virtual environment (exit code $($venvProcess.ExitCode))."
        exit 1
    }
}

if (Test-Path $venvActivate) {
    Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
    . $venvActivate
}

# Install backend dependencies
$requirementsFile = Join-Path $rootDir "apps\backend\requirements.txt"
if (Test-Path $requirementsFile) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    $pipArgs = @('-m', 'pip', 'install', '--upgrade', 'pip')
    $pipProcess = Start-Process -FilePath $venvPython -ArgumentList $pipArgs -NoNewWindow -Wait -PassThru
    if ($pipProcess.ExitCode -ne 0) {
        Write-Warning "Failed to upgrade pip, continuing anyway..."
    }
    
    $pipArgs = @('-m', 'pip', 'install', '-r', $requirementsFile)
    $pipProcess = Start-Process -FilePath $venvPython -ArgumentList $pipArgs -NoNewWindow -Wait -PassThru
    if ($pipProcess.ExitCode -ne 0) {
        Write-Error "Failed to install backend dependencies (exit code $($pipProcess.ExitCode))."
        exit 1
    }
} else {
    Write-Warning "requirements.txt not found at $requirementsFile. Some dependencies may be missing."
}

# Build backend sidecar (Nuitka)
Write-Host "Building backend sidecar (Nuitka)..." -ForegroundColor Yellow
Set-Location $rootDir

# Use venv Python if available, otherwise fall back to system Python
$pythonCmd = $venvPython
$pythonArgsBase = @()
if (-not (Test-Path $pythonCmd)) {
    # Fallback to system Python
    if ($cmd = Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd.Source
    } elseif ($cmd = Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd.Source
        $pythonArgsBase += '-3.10'
    } else {
        Write-Error "No suitable Python runtime found. Please install Python 3.10+ and ensure 'python' or 'py' is on PATH."
        exit 1
    }
}

# Ensure Nuitka is available in the venv
Write-Host "Ensuring Nuitka is installed..." -ForegroundColor Yellow
$pipArgs = @('-m', 'pip', 'install', 'nuitka')
$pipProcess = Start-Process -FilePath $pythonCmd -ArgumentList $pipArgs -NoNewWindow -Wait -PassThru
if ($pipProcess.ExitCode -ne 0) {
    Write-Error "Failed to install Nuitka (exit code $($pipProcess.ExitCode))."
    exit 1
}

# Clean up any existing build artifacts that might be locked
# Nuitka creates dist/main.dist/ directory (or dist/main.build/ for build cache)
$distDir = Join-Path $rootDir "dist\main.dist"
$buildDir = Join-Path $rootDir "dist\main.build"
$distExe = Join-Path $distDir "main.exe"
if (Test-Path $distExe) {
    Write-Host "Cleaning up existing build artifacts..." -ForegroundColor Yellow

    # Try to kill any running instances of main.exe
    $processes = Get-Process -Name "main" -ErrorAction SilentlyContinue
    if ($processes) {
        Write-Host "Found running main.exe processes. Stopping them..." -ForegroundColor Yellow
        $processes | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    # Try to remove the directories with retries
    $maxRetries = 3
    $retryCount = 0
    $removed = $false

    while ($retryCount -lt $maxRetries -and -not $removed) {
        try {
            if (Test-Path $distDir) {
                Remove-Item $distDir -Recurse -Force -ErrorAction Stop
            }
            if (Test-Path $buildDir) {
                Remove-Item $buildDir -Recurse -Force -ErrorAction Stop
            }
            $removed = $true
            Write-Host "Removed existing build directories" -ForegroundColor Green
        } catch {
            $retryCount++
            if ($retryCount -lt $maxRetries) {
                Write-Host "Failed to remove build directories (attempt $retryCount/$maxRetries). Retrying..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            } else {
                Write-Warning "Could not remove $distDir or $buildDir. It may be locked by another process."
                Write-Warning "Please close any applications using main.exe and try again."
                Write-Warning "Continuing build anyway - Nuitka will attempt to overwrite it..."
            }
        }
    }
}

# Build EXE from project root so core/plugins/resources are accessible
Write-Host "Running Nuitka..." -ForegroundColor Yellow
$nuitkaArgs = $pythonArgsBase + @(
    '-m', 'nuitka',
    'apps/backend/run_server.py',

    # Fast build mode
    '--standalone',
    '--remove-output',

    # Note: Removed --clang flag as it requires Clang to be installed in Visual Studio
    # MSVC (default) works fine and is already available with Visual Studio BuildTools
    '--jobs=0',            # all CPU cores
    '--nofollow-import-to=torch',
    '--nofollow-import-to=transformers',
    '--plugin-disable=transformers',

    # Tauri-friendly
    '--windows-disable-console',
    '--output-dir=dist',
    '--output-filename=main',

    # Include backend folders
    '--include-data-dir=apps/backend/api=api',
    '--include-data-dir=apps/backend/services=services',
    '--include-data-dir=apps/backend/db=db',
    '--include-data-dir=apps/backend/models=models',
    '--include-data-dir=apps/backend/tasks=tasks',
    '--include-data-dir=core=core',
    '--include-data-dir=plugins=plugins',
    '--include-data-dir=resources=resources',

    # Required packages
    '--include-package=uvicorn',
    '--include-package=fastapi',
    '--include-package=starlette', 
    '--include-package=pydantic'
)
try {
    $pyProcess = Start-Process -FilePath $pythonCmd -ArgumentList $nuitkaArgs -NoNewWindow -Wait -PassThru
    if ($pyProcess.ExitCode -ne 0) {
        Write-Error "Nuitka failed with exit code $($pyProcess.ExitCode)"
        exit 1
    }
} catch {
    Write-Error "Nuitka execution failed: $_"
    Write-Host "`nTroubleshooting tips:" -ForegroundColor Yellow
    Write-Host "1. Make sure main.exe is not running (check Task Manager)" -ForegroundColor Yellow
    Write-Host "2. Close any file explorers or antivirus that might be scanning main.dist\" -ForegroundColor Yellow
    Write-Host "3. Try running this script as Administrator" -ForegroundColor Yellow
    Write-Host "4. Manually delete main.dist\ and main.build\ directories and try again" -ForegroundColor Yellow
    exit 1
}

# Copy entire backend directory into Tauri bin (--standalone includes all dependencies)
# Nuitka creates dist/main.dist/ with main.exe + all DLLs, .pyd files, etc.
$sidecarSrcDir = Join-Path $rootDir "dist\main.dist"
$sidecarDstDir = Join-Path $rootDir "apps\desktop\src-tauri\bin"
New-Item -ItemType Directory -Force -Path $sidecarDstDir | Out-Null

# Clean old sidecar files/directories to avoid duplicates
if (Test-Path $sidecarDstDir) {
    Get-ChildItem -Path $sidecarDstDir -Filter "main*" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

if (Test-Path $sidecarSrcDir) {
    # Copy all files from dist/main.dist/ to bin/ (includes main.exe + all dependencies)
    Copy-Item -Path "$sidecarSrcDir\*" -Destination $sidecarDstDir -Recurse -Force
    
    # Rename main.exe to main-x86_64-pc-windows-msvc.exe for Tauri v2 naming
    $targetTriple = "x86_64-pc-windows-msvc"
    $originalExe = Join-Path $sidecarDstDir "main.exe"
    $renamedExe = Join-Path $sidecarDstDir ("main-$targetTriple.exe")
    
    if (Test-Path $originalExe) {
        if (Test-Path $renamedExe) {
            Remove-Item $renamedExe -Force
        }
        Rename-Item -Path $originalExe -NewName ("main-$targetTriple.exe")
        Write-Host "Backend directory copied and EXE renamed to: main-$targetTriple.exe" -ForegroundColor Green
    } else {
        Write-Error "Backend EXE not found at $originalExe. Ensure Nuitka succeeded."
        exit 1
    }
} else {
    Write-Error "Backend directory not found at $sidecarSrcDir. Ensure Nuitka succeeded."
    exit 1
}

# Navigate to desktop app directory
Set-Location (Join-Path $rootDir "apps\desktop")

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
