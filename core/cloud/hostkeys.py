"""
App-owned SSH known-hosts store (trust-on-first-use with fingerprint pinning).

Deliberately independent of ``~/.ssh/known_hosts`` and OpenSSH so behaviour is identical on
Windows, macOS and Linux.  A first-seen key must be confirmed by the user; a later change is
a hard error (possible man-in-the-middle).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, Literal, Optional

HostKeyStatus = Literal["trusted", "unknown", "changed"]


def fingerprint(key_blob: bytes) -> str:
    """OpenSSH-style SHA256 fingerprint of a raw public-key blob."""
    digest = hashlib.sha256(key_blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class HostKeyStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    @staticmethod
    def _key(host: str, port: int) -> str:
        return f"{host.strip().lower()}:{port}"

    def _load(self) -> Dict[str, Dict[str, str]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def check(self, host: str, port: int, key_type: str, fp: str) -> HostKeyStatus:
        with self._lock:
            known = self._load().get(self._key(host, port))
        if known is None:
            return "unknown"
        return "trusted" if known["type"] == key_type and known["fingerprint"] == fp else "changed"

    def trust(self, host: str, port: int, key_type: str, fp: str) -> None:
        with self._lock:
            data = self._load()
            data[self._key(host, port)] = {"type": key_type, "fingerprint": fp}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=self.path.name + ".")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
            os.replace(tmp, self.path)

    def get(self, host: str, port: int) -> Optional[Dict[str, str]]:
        with self._lock:
            return self._load().get(self._key(host, port))

    def forget(self, host: str, port: int) -> bool:
        with self._lock:
            data = self._load()
            if data.pop(self._key(host, port), None) is None:
                return False
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
