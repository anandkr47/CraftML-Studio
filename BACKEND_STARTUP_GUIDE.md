# Backend Startup Guide

## Current Implementation

We're using **Rust's `std::process::Command`** (not Tauri's shell API) to start the backend. This is the **recommended approach** because:

1. ✅ **More Secure**: No shell permissions needed
2. ✅ **Better Control**: Direct process management
3. ✅ **Cross-Platform**: Works consistently on all platforms
4. ✅ **No Shell Dependencies**: Doesn't require shell to be available

## How It Works

### 1. **Automatic Startup (Current)**
The backend automatically starts when the Tauri app launches:

```rust
// apps/desktop/src-tauri/src/lib.rs
.setup(|app| {
    let backend_state = app.state::<BackendProcess>();
    if let Ok(resource_dir) = app.path().resource_dir() {
        backend_state.start_with_resource_dir(resource_dir)?;
    }
    Ok(())
})
```

### 2. **Backend Process Flow**
```
App Launch
  ↓
Extract backend EXE from resources to %TEMP%\craftml-studio\backend\
  ↓
Execute: craftml-backend.exe --host 127.0.0.1 --port 5000
  ↓
Backend runs on http://127.0.0.1:5000
```

## Passing Arguments

### Backend Supports Arguments

The backend now accepts command-line arguments:

```python
# apps/backend/run_server.py
python craftml-backend.exe --host 127.0.0.1 --port 5000 --log-level info
```

**Available Arguments:**
- `--host`: Host to bind to (default: `127.0.0.1`)
- `--port`: Port number (default: `5000`)
- `--log-level`: Log level - `debug`, `info`, `warning`, `error` (default: `info`)

### Rust Code (Current Implementation)

```rust
// apps/desktop/src-tauri/src/backend_process.rs
pub fn start_with_args(
    &self,
    resource_dir: PathBuf,
    host: Option<String>,
    port: Option<u16>,
    log_level: Option<String>,
) -> Result<String, String> {
    let backend_path = self.extract_backend_from_resources(resource_dir)?;
    
    let mut cmd = Command::new(&backend_path);
    cmd.env("CRAFTML_ENV", "prod");
    
    if let Some(h) = host {
        cmd.arg("--host").arg(h);
    }
    if let Some(p) = port {
        cmd.arg("--port").arg(p.to_string());
    }
    if let Some(ll) = log_level {
        cmd.arg("--log-level").arg(ll);
    }
    
    let child = cmd.spawn()?;
    // ...
}
```

## Using Tauri Shell API (Not Recommended)

If you **really** want to use Tauri's shell API from the frontend, here's how:

### ❌ **Not Recommended Approach**

```typescript
// Frontend code (NOT recommended)
import { Command } from '@tauri-apps/api/shell';

// This requires shell permissions and is less secure
const command = new Command('craftml-backend', ['--port', '5000'], {
  cwd: '/path/to/backend',
  env: { CRAFTML_ENV: 'prod' }
});

const child = await command.execute();
```

**Why Not Recommended:**
- ❌ Requires shell permissions in `tauri.conf.json`
- ❌ Less secure (shell access)
- ❌ Platform-specific path handling
- ❌ More complex error handling

### ✅ **Current Approach (Recommended)**

The backend is already started automatically in Rust. If you need to restart it with different arguments, you can:

1. **Add a Tauri command** (already partially implemented):

```rust
// apps/desktop/src-tauri/src/backend_process.rs
#[tauri::command]
pub fn start_backend_with_args(
    state: State<BackendProcess>,
    host: Option<String>,
    port: Option<u16>,
    log_level: Option<String>,
) -> Result<String, String> {
    // Get resource directory from app
    // Then call start_with_args()
}
```

2. **Call from Frontend**:

```typescript
// Frontend code
import { invoke } from '@tauri-apps/api/core';

// Restart backend with custom port
await invoke('start_backend_with_args', {
  host: '127.0.0.1',
  port: 5000,
  logLevel: 'info'
});
```

## Current Status

✅ **Backend auto-starts** on app launch with defaults:
- Host: `127.0.0.1`
- Port: `5000`
- Log Level: `info`

✅ **Backend accepts arguments** via command-line

✅ **Rust manages process** (secure, cross-platform)

## Next Steps (If Needed)

If you need to:
- **Change port dynamically**: Add Tauri command to restart with new port
- **Change log level**: Add Tauri command to restart with new log level
- **Stop/restart backend**: Already implemented via `stop_backend` command

## Example: Restart Backend with Custom Port

```typescript
// Frontend
import { invoke } from '@tauri-apps/api/core';

async function restartBackendOnPort(port: number) {
  // Stop current backend
  await invoke('stop_backend');
  
  // Start with new port (would need to implement this command)
  await invoke('start_backend_with_args', {
    port: port
  });
}
```

---

**Summary**: The current Rust-based approach is **better** than using Tauri's shell API. The backend starts automatically, and if you need custom arguments, we can add a Tauri command to restart it with those arguments.

