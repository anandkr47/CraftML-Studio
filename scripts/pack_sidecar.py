"""
Pack the PyInstaller one-folder backend into a single archive for the desktop bundle.

    python scripts/pack_sidecar.py dist/craftml-backend apps/desktop/src-tauri/bin/backend.tar.gz

Why an archive: Tauri copies resources file by file and follows symlinks, but PyInstaller's macOS
build relies on them (``_internal/Python`` -> ``Python.framework/...``; libraries are found relative
to the link target). A tar archive keeps symlinks and permissions on every OS; the app unpacks it
once per build (apps/desktop/src-tauri/src/backend_process.rs).

Entries are sorted, owned by 0:0 and keep their mtimes, so repacking an unchanged build gives
the same contents.
"""

import os
import sys
import tarfile
from pathlib import Path


def _reset_owner(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def pack(src: Path, dest: Path) -> None:
    if not src.is_dir():
        raise SystemExit(f"{src} is not a directory (run PyInstaller first)")
    exe = "craftml-backend.exe" if os.name == "nt" else "craftml-backend"
    if not (src / exe).is_file():
        raise SystemExit(f"{src / exe} not found")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial")
    with tarfile.open(tmp, "w:gz", compresslevel=6, format=tarfile.PAX_FORMAT) as tar:
        for root, dirs, files in os.walk(src, followlinks=False):
            dirs.sort()
            for name in sorted(dirs) + sorted(files):
                path = Path(root) / name
                if path.is_dir() and not path.is_symlink():
                    continue  # directories are implied by their contents (and walked)
                tar.add(path, arcname=path.relative_to(src).as_posix(), recursive=False, filter=_reset_owner)
    os.replace(tmp, dest)
    print(f"packed {src} -> {dest} ({dest.stat().st_size / 1024 ** 2:.0f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pack(Path(sys.argv[1]), Path(sys.argv[2]))
