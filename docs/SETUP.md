# Setup, development and packaging

CraftML Studio is a Tauri 2 desktop shell (Rust + React) that launches a local Python backend
(FastAPI + PyTorch) as a child process. It runs on macOS (Apple Silicon), Windows and Linux.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 or 3.12 | macOS: `brew install python@3.12` (the system `python3` is too old). Windows: python.org or `winget install Python.Python.3.12`. |
| Node.js | 20.19+ (or 22.12+) | Required by Vite 7. |
| Rust | stable | <https://rustup.rs> |
| Git | any | Used to fetch llama.cpp's GGUF converter on first use. |
| Tauri system libraries | | Linux: `libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf`. Windows: WebView2 (preinstalled on Windows 10/11) and the MSVC build tools. macOS: Xcode Command Line Tools. |

GPU acceleration is used automatically: CUDA on NVIDIA (Windows/Linux), Metal (MPS) on Apple Silicon,
otherwise CPU. On Windows the setup script installs the CUDA build of PyTorch when it finds
`nvidia-smi`; PyPI's Windows wheels are CPU-only.

## Install

```bash
./scripts/setup.sh          # macOS / Linux
```
```powershell
.\scripts\setup.ps1         # Windows (PowerShell)
```

Setup creates `apps/backend/venv`, installs the backend with the **exact tested versions**
(`requirements.txt` constrained by `requirements.lock.txt`) plus the test tools, and installs the
frontend with `npm ci`.

**GGUF support is optional.** `llama-cpp-python` (chatting with GGUF models, and quantization types
other than Q8_0/F16) is installed on a best-effort basis from prebuilt wheels, building from source
if needed. If that fails (no C/C++ toolchain), everything else works; install it later with:

```bash
apps/backend/venv/bin/python -m pip install -r apps/backend/requirements-gguf.txt
```

On macOS, if a source build fails with "fatal error: 'mutex' file not found", your Command Line
Tools are incomplete: run `xcode-select --install`, or build with
`SDKROOT=$(xcrun --show-sdk-path) CMAKE_ARGS="-DGGML_METAL=on"`.

### Updating dependencies

Edit the ranges in `apps/backend/requirements.txt`, install, run the tests, then regenerate the lock:

```bash
apps/backend/venv/bin/python -m pip freeze --exclude-editable > apps/backend/requirements.lock.txt
```

The remote GPU worker pins its own versions in `core/cloud/worker/requirements.txt`, and a test
keeps them in step with the lock.

## Run in development

```bash
./scripts/dev.sh                    # desktop app; it starts the backend itself
./scripts/dev.sh --backend-only     # just the API on http://127.0.0.1:17860 (docs at /docs)
```

(`.\scripts\dev.ps1` on Windows, same options.)

In development the shell runs `apps/backend/run_server.py` with the first interpreter it finds:
`$CRAFTML_PYTHON`, then `apps/backend/venv`, `apps/backend/.venv`, then `python3`/`python` on PATH.
If a CraftML backend is already listening on the port (for example one started with
`--backend-only`), the app uses it instead of starting another.

The backend listens on **127.0.0.1:17860** and accepts requests only from the app (loopback `Host`
plus an `Origin` allowlist). Port 5000, used by earlier versions, is taken by the AirPlay Receiver on
macOS.

### Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `CRAFTML_PYTHON` | shell | Interpreter for the development backend. |
| `CRAFTML_BACKEND_DIR` | shell | Run the backend from this source directory (also in release builds). |
| `CRAFTML_USER_DATA_DIR` | backend | Store data somewhere else (tests use this). |
| `CRAFTML_ENV` | backend | `prod` selects the per-user data directory below; otherwise `~/.craftml` is used. The shell sets it for packaged builds. |
| `CRAFTML_PORT` | backend | Port for a standalone backend (`run_server.py`). The desktop UI always uses 17860. |
| `CRAFTML_ALLOWED_ORIGINS` | backend | Extra comma-separated browser origins allowed to call the API. |
| `VITE_API_BASE` | frontend build | Backend URL baked into the UI (default `http://127.0.0.1:17860`). |
| `LLAMA_CPP_DIR` | backend | Use an existing llama.cpp checkout for GGUF conversion. |
| `HTTPS_PROXY` / `HTTP_PROXY` | backend | Standard proxy settings, honoured for Hugging Face and cloud providers. |

## Where things are stored

| What | macOS | Windows | Linux |
|---|---|---|---|
| Data: models, datasets, chats, knowledge base, encrypted secrets (packaged app) | `~/Library/Application Support/CraftML Studio` | `%APPDATA%\CraftML Studio` | `~/.local/share/CraftML Studio` |
| Data (running from source) | `~/.craftml` | `%USERPROFILE%\.craftml` | `~/.craftml` |
| Backend output captured by the app (`backend-stdout.log`, `backend-stderr.log`) | `~/Library/Logs/com.craftml.studio` | `%LOCALAPPDATA%\com.craftml.studio\logs` | `~/.local/share/com.craftml.studio/logs` |
| Backend service logs | `<data>/logs` | `<data>\logs` | `<data>/logs` |
| Unpacked backend (packaged app) | `~/Library/Application Support/com.craftml.studio/backend` | `%LOCALAPPDATA%\com.craftml.studio\backend` | `~/.local/share/com.craftml.studio/backend` |

Downloaded Hugging Face models also use the standard Hugging Face cache (`~/.cache/huggingface`, or
`$HF_HOME`). Models that are already cached load without the network.

`./scripts/check_backend_logs.sh` (or `.ps1`) prints the last lines of the captured backend output. If
the backend can't start, the loading screen shows the error, the end of the log and a **Retry** button.

## Tests

```bash
cd <repo>
apps/backend/venv/bin/python -m pytest tests -q                      # backend (no network, no GPU)
(cd apps/desktop/src-tauri && cargo test)                            # desktop shell / backend launcher
(cd apps/desktop && npx tsc --noEmit && npm run build)               # frontend typecheck + build
```

`tests/test_cloud_ssh_integration.py` runs only when `CRAFTML_TEST_SSH_*` points at a real SSH
server; CI runs it against a throwaway `sshd`. CI (`.github/workflows/ci.yml`) covers Linux, macOS
(Apple Silicon) and Windows: backend/cloud tests, the SSH integration test, the launcher tests,
shellcheck and PowerShell parsing of the scripts, and the frontend build.

## Build the desktop app

```bash
./scripts/build_desktop.sh [--clean]      # macOS / Linux
```
```powershell
.\scripts\build_desktop.ps1 [-Clean]      # Windows
```

The build script:

1. installs the locked backend dependencies and PyInstaller into `apps/backend/venv`;
2. packages the backend with PyInstaller (`craftml-backend.spec`, a one-folder build that includes
   PyTorch, so expect about 1 GB; one folder rather than one file because a one-file build would
   unpack all of that on every launch);
3. packs it into `apps/desktop/src-tauri/bin/backend.tar.gz` (`scripts/pack_sidecar.py`; about
   330 MB) and runs `tauri build`. It is an archive because Tauri's resource copy follows symlinks,
   which the PyInstaller build needs on macOS.

Installers end up in `apps/desktop/src-tauri/target/release/bundle/`. Set `CRAFTML_TORCH=cpu` to bundle the CPU-only PyTorch build (the release workflow
does): on Linux, PyPI's PyTorch includes about 3 GB of CUDA libraries, which would push each installer
past GitHub's 2 GiB limit for release files. Installers built that way run models on the CPU (Apple
Silicon builds still use Metal); NVIDIA GPU use needs a source install or a locally built CUDA bundle. Build on each target OS (no
cross-compiling). On Windows, a build machine with an NVIDIA driver bundles CUDA PyTorch (unless
`CRAFTML_TORCH=cpu`), which also runs on machines without a GPU.

At first launch (and after each update) the app unpacks the bundled backend into the per-user
directory above and runs it from there. That first start can take a few minutes while the OS
security scan (Gatekeeper/XProtect, Windows Defender) checks the new libraries; later starts take
seconds. If the app crashes or is killed, the backend notices within
a few seconds and exits.

For distribution, sign and notarize the macOS app and sign the Windows installer as usual for Tauri
apps; the bundled backend must be signed too, since it is an executable inside the bundle.

## Troubleshooting

* **"Port 17860 is in use by another application"**: something else owns the port. Find it with
  `lsof -nP -iTCP:17860` (macOS/Linux) or `netstat -ano | findstr 17860` (Windows).
* **"A CraftML backend from version X is still running"**: an older app instance is still open;
  quit it (or end its `craftml-backend` process) and press Retry.
* **Downloads stall but the browser works**: usually broken IPv6. The backend detects this at
  startup and prefers IPv4; a proxy can be set with `HTTPS_PROXY`.
* **A GGUF model won't load**: llama.cpp is checked in a separate process first, so an
  unsupported model gives an error message instead of crashing the backend.
