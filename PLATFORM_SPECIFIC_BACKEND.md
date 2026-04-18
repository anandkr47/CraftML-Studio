# Platform-Specific Backend Resources

## Issue
Tauri requires all resources listed in `tauri.conf.json` to exist at build time. Since we only build the backend for the current platform, we need to update `tauri.conf.json` to only include the backend for the platform being built.

## Solution

### Windows Build
- `tauri.conf.json` includes: `bin/craftml-backend-x86_64-pc-windows-msvc.exe`
- Build script: `scripts/build_desktop.ps1`

### Linux/macOS Build
- `tauri.conf.json` needs to be updated to include the appropriate backend:
  - Linux x86_64: `bin/craftml-backend-x86_64-unknown-linux-gnu`
  - Linux ARM64: `bin/craftml-backend-aarch64-unknown-linux-gnu`
  - macOS x86_64: `bin/craftml-backend-x86_64-apple-darwin`
  - macOS ARM64: `bin/craftml-backend-aarch64-apple-darwin`

## Current Status
- ✅ Windows: Fixed - only includes Windows backend
- ⚠️ Linux/macOS: Build scripts should update `tauri.conf.json` before building

## Future Improvement
Consider using a build script that dynamically updates `tauri.conf.json` based on the target platform, or use Tauri's build hooks to conditionally include resources.

