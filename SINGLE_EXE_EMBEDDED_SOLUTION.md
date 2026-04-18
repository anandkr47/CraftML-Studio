# Single EXE Solution - Embedded Backend

## Problem
After installation, users were seeing two EXEs:
- `craftml-frontend.exe` (in root)
- `craftml-backend.exe` (in `bin/` folder)

## Solution
Embed the backend binary **directly into the Rust code** using `include_bytes!` macro. This way:
- ✅ Backend is compiled into the frontend EXE
- ✅ No separate backend file in installation directory
- ✅ Only one EXE visible to users
- ✅ Backend extracted to temp directory at runtime

## Implementation

### 1. **Embed Backend in Rust Code** (`apps/desktop/src-tauri/src/backend_process.rs`)

```rust
// Load embedded backend binary (compiled into the Rust binary)
#[cfg(target_os = "windows")]
let backend_bytes = include_bytes!("../../bin/craftml-backend-x86_64-pc-windows-msvc.exe");

// Platform-specific includes for other platforms...
```

The `include_bytes!` macro embeds the binary file directly into the compiled Rust binary at compile time.

### 2. **Extract at Runtime**

```rust
fn extract_backend_from_embedded(&self) -> Result<PathBuf, String> {
    // Extract to temp directory
    let temp_dir = std::env::temp_dir().join("craftml-studio").join("backend");
    let extracted_path = temp_dir.join(backend_filename);
    
    if should_extract {
        // Write embedded bytes to temp file
        fs::write(&extracted_path, backend_bytes)?;
    }
    
    Ok(extracted_path)
}
```

### 3. **Build Script Verification** (`apps/desktop/src-tauri/build.rs`)

```rust
// Verify backend exists before compilation
let backend_path = Path::new("bin/craftml-backend-x86_64-pc-windows-msvc.exe");
if !backend_path.exists() {
    panic!("Backend binary not found. Please run build script first.");
}
```

### 4. **Removed from Tauri Config** (`apps/desktop/src-tauri/tauri.conf.json`)

```json
{
  "bundle": {
    "resources": [],  // No longer needed - embedded in Rust code
    "externalBin": []
  }
}
```

## How It Works

### Build Time:
1. PyInstaller creates `craftml-backend.exe`
2. Build script copies it to `apps/desktop/src-tauri/bin/`
3. Rust compiler embeds it using `include_bytes!`
4. Backend becomes part of the frontend EXE binary

### Runtime:
1. User runs `craftml-frontend.exe` (only EXE visible!)
2. App extracts backend from embedded bytes to `%TEMP%\craftml-studio\backend\`
3. Backend runs from temp directory
4. No separate backend EXE in installation directory

## Result

**Before:**
```
C:\Program Files\CraftML Studio\
├── craftml-frontend.exe
└── bin\
    └── craftml-backend.exe  ❌ Visible to user
```

**After:**
```
C:\Program Files\CraftML Studio\
└── craftml-frontend.exe  ✅ Only one EXE!
```

Backend is embedded inside `craftml-frontend.exe` and extracted to temp directory at runtime.

## Benefits

1. ✅ **True Single EXE**: Backend is compiled into frontend binary
2. ✅ **No Separate Files**: No backend EXE in installation directory
3. ✅ **Automatic Extraction**: Backend extracted to temp on first run
4. ✅ **Cross-Platform**: Works on Windows, macOS, Linux
5. ✅ **User-Friendly**: Users only see one EXE file

## Notes

- Backend is embedded at **compile time** (increases frontend EXE size by ~606MB)
- Backend is extracted to **temp directory** at runtime
- Extraction happens **once** (cached for subsequent runs)
- Total installer size remains the same (backend still included, just embedded differently)

