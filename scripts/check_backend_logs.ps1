# Quick script to check backend logs
# Usage: .\scripts\check_backend_logs.ps1

# Where the desktop app writes the backend's output (Tauri's per-user log directory)
$LogDir = Join-Path $env:LOCALAPPDATA "com.craftml.studio\logs"
$StdoutLog = Join-Path $LogDir "backend-stdout.log"
$StderrLog = Join-Path $LogDir "backend-stderr.log"

Write-Host "`n=== Backend Logs ===" -ForegroundColor Cyan
Write-Host "Log Directory: $LogDir`n" -ForegroundColor Gray

if (Test-Path $StdoutLog) {
    Write-Host "STDOUT Log ($StdoutLog):" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Gray
    Get-Content $StdoutLog -Tail 50
    Write-Host ("=" * 70) -ForegroundColor Gray
} else {
    Write-Host "WARNING: STDOUT log not found" -ForegroundColor Yellow
}

Write-Host "`n"

if (Test-Path $StderrLog) {
    Write-Host "ERROR: STDERR Log ($StderrLog):" -ForegroundColor Red
    Write-Host ("=" * 70) -ForegroundColor Gray
    Get-Content $StderrLog -Tail 50
    Write-Host ("=" * 70) -ForegroundColor Gray
} else {
    Write-Host "WARNING: STDERR log not found" -ForegroundColor Yellow
}

Write-Host "`n=== End of Logs ===" -ForegroundColor Cyan

