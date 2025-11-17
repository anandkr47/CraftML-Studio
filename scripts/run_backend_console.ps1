# Script to run backend EXE with visible console output
# This will show all logs directly in your terminal

Write-Host "Starting CraftML Studio Backend with console output..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server`n" -ForegroundColor Yellow

# Navigate to dist directory (Nuitka --standalone creates dist/main.dist/main.exe)
$distPath = Join-Path $PSScriptRoot "..\dist\main.dist\main.exe"
if (-not (Test-Path $distPath)) {
    Write-Error "Backend EXE not found at: $distPath"
    Write-Host "Please run .\scripts\build_desktop.ps1 first to build the backend." -ForegroundColor Yellow
    exit 1
}

# Stop any existing backend processes
$existing = Get-Process -Name "main" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing backend processes..." -ForegroundColor Yellow
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# Run the backend with console output
# This will show all output directly in the terminal
Set-Location (Split-Path $distPath)
& $distPath --console --host 127.0.0.1 --port 5000 --log-level debug

