# Backend Logging Guide

## Problem
Backend errors were not visible because stdout/stderr were redirected to null to hide the console window.

## Solution
Backend logs are now written to files in the temp directory, allowing you to see errors even without a console window.

## Log File Locations

### Windows
- **Stdout**: `%TEMP%\craftml-studio\logs\backend-stdout.log`
- **Stderr**: `%TEMP%\craftml-studio\logs\backend-stderr.log`

### macOS/Linux
- **Stdout**: `/tmp/craftml-studio/logs/backend-stdout.log`
- **Stderr**: `/tmp/craftml-studio/logs/backend-stderr.log`

## How to View Logs

### Method 1: Check Log Files Directly

**Windows:**
```powershell
# View stdout log
Get-Content "$env:TEMP\craftml-studio\logs\backend-stdout.log"

# View stderr log (errors)
Get-Content "$env:TEMP\craftml-studio\logs\backend-stderr.log"
```

**Linux/macOS:**
```bash
# View stdout log
cat /tmp/craftml-studio/logs/backend-stdout.log

# View stderr log (errors)
cat /tmp/craftml-studio/logs/backend-stderr.log
```

### Method 2: From Application (Future)

A Tauri command `get_backend_logs` is available to read logs from the frontend:
```typescript
import { invoke } from '@tauri-apps/api/core';

const logs = await invoke('get_backend_logs');
console.log('Stdout:', logs.stdout);
console.log('Stderr:', logs.stderr);
```

## What Gets Logged

- **stdout.log**: All standard output from the backend (startup messages, info logs)
- **stderr.log**: All error output (Python exceptions, tracebacks, errors)

## Debugging Backend Issues

1. **Check if backend process started:**
   - Look for "Starting backend server..." in stdout.log
   - Check for process spawn errors in stderr.log

2. **Check for import errors:**
   - Look for `ModuleNotFoundError` in stderr.log
   - Check if all modules are properly bundled

3. **Check for path errors:**
   - Look for `FileNotFoundError` or path-related errors
   - Verify resources are extracted correctly

4. **Check for port conflicts:**
   - Look for "Address already in use" errors
   - Check if port 5000 is available

## Common Issues

### Backend Not Starting
- Check stderr.log for Python exceptions
- Verify backend EXE exists in resources
- Check if extraction to temp directory succeeded

### Import Errors
- Verify PyInstaller bundled all modules
- Check `--hidden-import` flags in build script
- Ensure `core`, `plugins`, `resources` are included

### Path Errors
- Check if user data directory is writable
- Verify resource extraction paths
- Check temp directory permissions

## Log Rotation

Logs are appended to files (not overwritten). To clear logs:
- Delete the log files manually
- Or restart the application (logs will continue appending)

## Next Steps

Consider adding:
- Log rotation (max file size)
- Log level filtering
- UI component to view logs in-app
- Automatic log cleanup on app update

