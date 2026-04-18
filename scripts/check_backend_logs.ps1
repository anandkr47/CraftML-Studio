# Quick script to check backend logs
# Usage: .\scripts\check_backend_logs.ps1

$LogDir = "$env:TEMP\craftml-studio\logs"
$StdoutLog = Join-Path $LogDir "backend-stdout.log"
$StderrLog = Join-Path $LogDir "backend-stderr.log"

Write-Host "`n=== Backend Logs ===" -ForegroundColor Cyan
Write-Host "Log Directory: $LogDir`n" -ForegroundColor Gray

if (Test-Path $StdoutLog) {
    Write-Host "📄 STDOUT Log ($StdoutLog):" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Gray
    Get-Content $StdoutLog -Tail 50
    Write-Host ("=" * 70) -ForegroundColor Gray
} else {
    Write-Host "⚠️  STDOUT log not found" -ForegroundColor Yellow
}

Write-Host "`n"

if (Test-Path $StderrLog) {
    Write-Host "❌ STDERR Log ($StderrLog):" -ForegroundColor Red
    Write-Host ("=" * 70) -ForegroundColor Gray
    Get-Content $StderrLog -Tail 50
    Write-Host ("=" * 70) -ForegroundColor Gray
} else {
    Write-Host "⚠️  STDERR log not found" -ForegroundColor Yellow
}

Write-Host "`n=== End of Logs ===" -ForegroundColor Cyan

