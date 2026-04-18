# Backend EXE Testing Checklist

## Quick Test (30 seconds)

### 1. Run the EXE
```powershell
.\dist\craftml-backend.exe
```

### 2. Check console output for:
- ✅ `First run detected. Copying resources...` (first time only)
- ✅ `Resources copied successfully!` (first time only)
- ✅ `INFO: Started server process`
- ✅ `INFO: Uvicorn running on http://127.0.0.1:5000`
- ❌ NO `ModuleNotFoundError`
- ❌ NO `ImportError`
- ❌ NO Python tracebacks

### 3. Open browser
```
http://127.0.0.1:5000/docs
```
- ✅ FastAPI docs page loads
- ❌ Connection refused = Server didn't start

---

## Automated Test (1 minute)

```powershell
# Install requests if needed
pip install requests

# Run test script
python test_backend_exe.py
```

**Expected output:**
```
======================================================================
CraftML Backend EXE Test
======================================================================

✓ Found backend EXE: E:\CraftML-Studio\dist\craftml-backend.exe
  Size: 41.23 MB

🚀 Starting backend server...
⏳ Waiting for server to start (max 30 seconds)...
✅ Server started successfully after 5 seconds!

🧪 Testing API endpoints...
   ✓ API Documentation: 200
   ✓ List Models: 200
   ✓ List Datasets: 200
   ✓ System Info: 200

📁 Checking production folders...
   ✓ C:\Users\...\AppData\Roaming\CraftML Studio\resources
   ✓ C:\Users\...\AppData\Roaming\CraftML Studio\resources\models
   ✓ C:\Users\...\AppData\Roaming\CraftML Studio\resources\datasets
   ✓ C:\Users\...\AppData\Roaming\CraftML Studio\logs

🛑 Stopping server...

======================================================================
Test Summary:
  API Tests Passed: 4/4
  Server Status: ✅ Working
======================================================================
```

---

## Manual API Tests

### Start server:
```powershell
.\dist\craftml-backend.exe
```

### In another terminal:

#### Test 1: Get API docs
```powershell
start http://127.0.0.1:5000/docs
```

#### Test 2: List models
```powershell
curl http://127.0.0.1:5000/api/playground/models
```

#### Test 3: List datasets
```powershell
curl http://127.0.0.1:5000/api/datasets
```

#### Test 4: System info
```powershell
curl http://127.0.0.1:5000/api/hardware/system
```

#### Test 5: Check health
```powershell
curl http://127.0.0.1:5000/
```

---

## Check Production Folders

```powershell
# Open user data directory
explorer "$env:APPDATA\CraftML Studio"
```

**Should see:**
```
CraftML Studio\
├── resources\
│   ├── templates\    ← Copied from EXE
│   ├── icons\        ← Copied from EXE
│   ├── models\       ← Empty (for trained models)
│   └── datasets\     ← Empty (for datasets)
├── logs\             ← Empty initially
│   └── backend.log   ← Created when server runs
└── craftml.db        ← Created when server runs
```

---

## Common Issues & Fixes

### ❌ `ModuleNotFoundError: No module named 'core'`
**Fix:** Core package not bundled. Check build script has:
```powershell
--hidden-import=core
--add-data "core;core"
```

### ❌ `ModuleNotFoundError: No module named 'uvicorn'`
**Fix:** Uvicorn not bundled. Check build script has:
```powershell
--hidden-import=uvicorn
--collect-all uvicorn
```

### ❌ Server starts but no folders created
**Fix:** Check `run_server.py` has the folder creation code in the `if getattr(sys, 'frozen', False):` block

### ❌ `craftml-backend.exe` is 600MB+
**Fix:** Check `src-tauri/bin/` only has ONE file: `craftml-backend-x86_64-pc-windows-msvc.exe`

---

## Performance Check

### EXE should be:
- ✅ **Size:** 40-50 MB (normal for PyTorch apps)
- ✅ **Startup:** 5-15 seconds first time
- ✅ **Startup:** 2-5 seconds subsequent runs
- ✅ **Memory:** 200-500 MB idle
- ✅ **CPU:** Low (<5%) when idle

### If EXE is 600MB+:
- ❌ Wrong file bundled by Tauri
- ❌ Multiple sidecar files in `bin/`
- ❌ Check you only have `craftml-backend-x86_64-pc-windows-msvc.exe`

---

## Success Criteria

✅ **All must pass:**
1. EXE starts without errors
2. Server listens on `http://127.0.0.1:5000`
3. API docs load at `/docs`
4. At least 2 API endpoints respond
5. Folders created in `%APPDATA%\CraftML Studio\`
6. Logs written to `%APPDATA%\CraftML Studio\logs\`
7. No `ModuleNotFoundError` or `ImportError`
8. EXE size is 40-50 MB (not 600MB)

---

## Next Steps After Success

1. ✅ Backend works → Build full Tauri app
2. ✅ Install MSI/EXE from `apps\desktop\src-tauri\target\release\bundle\`
3. ✅ Launch "CraftML Studio" from Start Menu
4. ✅ Verify frontend connects to backend
5. ✅ Train a test model
6. ✅ Check model saved to `%APPDATA%\CraftML Studio\resources\models\`

