# Single EXE Solution for CraftML Studio

## Overview
This solution embeds the Python backend EXE as a resource within the Tauri frontend, then extracts it to a temp directory at runtime. This way, users only see **one EXE** (`craftml-frontend.exe`) in the installation directory.

## How It Works

### 1. **Build Time**
- PyInstaller creates `craftml-backend.exe` (606MB)
- Build script copies it to `apps/desktop/src-tauri/bin/` with platform-specific naming
- Tauri bundles it as a **resource** (not externalBin) in `tauri.conf.json`
- The backend EXE is embedded inside the frontend EXE

### 2. **Runtime**
- When the app starts, `backend_process.rs` extracts the backend from resources
- Backend is extracted to: `%TEMP%\craftml-studio\backend\` (Windows) or `/tmp/craftml-studio/backend/` (Linux/macOS)
- The extracted backend is executed from the temp directory
- Extraction only happens once (or when the embedded version is newer)

### 3. **User Experience**
- ✅ Users see only **one EXE** in `C:\Program Files\CraftML Studio\`
- ✅ Backend runs as a separate process (good isolation)
- ✅ No manual backend EXE visible to users
- ✅ Automatic cleanup on app update (newer embedded version overwrites extracted)

## Files Modified

### 1. `apps/desktop/src-tauri/tauri.conf.json`
```json
"resources": [
  "bin/craftml-backend-x86_64-pc-windows-msvc.exe",
  "bin/craftml-backend-x86_64-unknown-linux-gnu",
  // ... other platforms
],
"externalBin": []  // Changed from ["bin/craftml-backend"]
```

### 2. `apps/desktop/src-tauri/src/backend_process.rs`
- Added `extract_backend_from_resources()` method
- Extracts backend to temp directory on first run
- Sets executable permissions on Unix systems
- Only extracts if not already present or if embedded is newer

### 3. Build Scripts
- No changes needed - already copy backend to `bin/` directory
- Tauri automatically bundles resources from `bin/`

## Benefits

1. **Single EXE Appearance**: Users only see `craftml-frontend.exe`
2. **No Installation Changes**: Backend still runs as separate process
3. **Automatic Updates**: Newer embedded backend overwrites extracted version
4. **Cross-Platform**: Works on Windows, macOS, and Linux
5. **Security**: Backend runs from user temp directory (no admin rights needed)

## Testing

After building and installing:
1. Check installation directory - should only see `craftml-frontend.exe`
2. Check temp directory - backend should be extracted to:
   - Windows: `%TEMP%\craftml-studio\backend\`
   - Linux/macOS: `/tmp/craftml-studio/backend/`
3. Verify backend starts correctly
4. Verify API endpoints work

## Notes

- The backend EXE is still ~606MB (PyInstaller bundle)
- Total installer size remains the same (backend embedded in frontend)
- Backend extraction happens on first run (may add 1-2 seconds startup time)
- Extracted backend persists across sessions (no re-extraction needed)

