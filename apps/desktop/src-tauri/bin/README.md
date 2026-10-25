`scripts/build_desktop.sh` / `build_desktop.ps1` put the packaged backend here as `backend.tar.gz`
(the PyInstaller one-folder build, packed by `scripts/pack_sidecar.py`), and Tauri bundles it as a
resource. The app unpacks it once per build into a per-user directory and runs it from there.

It is an archive because Tauri copies resources file by file and follows symlinks, which breaks the
PyInstaller build on macOS.

This file keeps the directory, and the `bin/` resource entry in `tauri.conf.json`, valid before the
first build. Development runs (`npm run tauri dev`) use `apps/backend/run_server.py` instead.
