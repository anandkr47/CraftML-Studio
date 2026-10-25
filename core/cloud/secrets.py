"""
Local secret storage.

Envelope scheme: the OS keychain holds only a small master key; the secrets themselves
(API tokens, SSH private keys, which can exceed per-entry keychain size limits such as
Windows Credential Manager's) live in one Fernet-encrypted file under the app data dir.

If no keychain is usable (headless Linux without Secret Service, locked/denied keychain),
the master key falls back to a permission-restricted file and ``storage_info()`` reports
``secure=False`` so the UI can say so.  Secrets are never returned by any API.

Frozen-build note: keyring's entry-point discovery doesn't work in frozen (PyInstaller) builds,
so the backend for the current platform is imported explicitly (see ``default_keyring``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.cloud.errors import SecretStoreError

logger = logging.getLogger(__name__)

SERVICE = "craftml-studio"
MASTER_USER = "master-key"
DATA_FILE = "secrets.enc"
MASTER_FILE = ".master-key"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9/_.\-]*$")
REDACTED = "***"
HF_TOKEN = "hf/token"  # shared by services.hf_auth and the cloud transports
HF_USERNAME = "hf/username"


# --------------------------------------------------------------------------- redaction

_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]{16,}"),
    re.compile(r"\brpa_[A-Za-z0-9]{20,}"),
    re.compile(r"\b(?:ak|as)-[A-Za-z0-9]{10,}"),
    re.compile(r"\br8_[A-Za-z0-9]{20,}"),
]


class Redactor:
    """Scrubs known secret values and common token shapes from text."""

    def __init__(self) -> None:
        self._values: set = set()
        self._lock = threading.Lock()

    def register(self, value: Optional[str]) -> None:
        if value and len(value) >= 6:
            with self._lock:
                self._values.add(value)

    def redact(self, text: str) -> str:
        if not text:
            return text
        with self._lock:
            values = sorted(self._values, key=len, reverse=True)
        for value in values:
            text = text.replace(value, REDACTED)
        for pattern in _PATTERNS:
            text = pattern.sub(REDACTED, text)
        return text


_redactor = Redactor()


def register_secret(value: Optional[str]) -> None:
    """Teach the redactor a secret that didn't come through a SecretStore (e.g. a header we were handed)."""
    _redactor.register(value)


def redact(text: str) -> str:
    """Scrub every secret the process has read or written, plus well-known token shapes."""
    return _redactor.redact(text)


# --------------------------------------------------------------------------- keychain

def default_keyring() -> Optional[Any]:
    """The keychain backend for this OS, imported explicitly; None if unavailable."""
    try:
        if sys.platform == "darwin":
            from keyring.backends.macOS import Keyring
        elif sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring as Keyring
        else:
            from keyring.backends.SecretService import Keyring
        backend = Keyring()
        return backend if backend.priority > 0 else None
    except Exception as exc:  # noqa: BLE001 - missing package, no DBus, unsupported OS…
        logger.info("No OS keychain available (%s); using file-based master key", exc)
        return None


_AUTO = object()


# --------------------------------------------------------------------------- store

class SecretStore:
    """Encrypted name→value store. Thread-safe; writes are atomic."""

    def __init__(self, directory: Path, *, keyring_backend: Any = _AUTO, service: str = SERVICE):
        self.directory = Path(directory)
        self.service = service
        self._keyring = default_keyring() if keyring_backend is _AUTO else keyring_backend
        self._lock = threading.RLock()
        self._master: Optional[Tuple[bytes, str]] = None

    @property
    def data_path(self) -> Path:
        return self.directory / DATA_FILE

    @property
    def master_path(self) -> Path:
        return self.directory / MASTER_FILE

    # -- master key -------------------------------------------------------

    def _keychain_get(self) -> Optional[bytes]:
        if self._keyring is None:
            return None
        try:
            value = self._keyring.get_password(self.service, MASTER_USER)
            return value.encode() if value else None
        except Exception as exc:  # noqa: BLE001 - locked, denied, DBus gone…
            logger.warning("Keychain read failed: %s", exc)
            return None

    def _keychain_set(self, key: bytes) -> bool:
        if self._keyring is None:
            return False
        try:
            self._keyring.set_password(self.service, MASTER_USER, key.decode())
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Keychain write failed: %s", exc)
            return False

    def _resolve_master(self) -> Tuple[bytes, str]:
        if self._master:
            return self._master
        from cryptography.fernet import Fernet

        found = self._keychain_get()
        if found:
            self._master = (found, "keychain")
        elif self.master_path.exists():
            self._master = (self.master_path.read_bytes().strip(), "file")
        elif self.data_path.exists():
            raise SecretStoreError(
                "Saved credentials can't be decrypted because their encryption key is missing.",
                hint="Re-enter your credentials in Settings → Cloud GPUs.",
            )
        else:
            key = Fernet.generate_key()
            if self._keychain_set(key):
                self._master = (key, "keychain")
            else:
                self._atomic_write(self.master_path, key)
                self._master = (key, "file")
        return self._master

    def storage_info(self) -> Dict[str, Any]:
        with self._lock:
            _, where = self._resolve_master()
        return {
            "backend": where,
            "secure": where == "keychain",
            "detail": "OS keychain" if where == "keychain"
            else "Encryption key stored in a protected file (no usable OS keychain was found)",
        }

    # -- files --------------------------------------------------------------

    def _atomic_write(self, path: Path, data: bytes) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        _restrict(self.directory, directory=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.directory), prefix=path.name + ".")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            _restrict(Path(tmp))
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _read_all(self) -> Dict[str, str]:
        from cryptography.fernet import Fernet, InvalidToken

        if not self.data_path.exists():
            return {}
        key, _ = self._resolve_master()
        try:
            raw = Fernet(key).decrypt(self.data_path.read_bytes())
        except InvalidToken as exc:
            raise SecretStoreError(
                "Saved credentials can't be decrypted (the encryption key changed).",
                hint="Re-enter your credentials in Settings → Cloud GPUs.",
            ) from exc
        return json.loads(raw.decode("utf-8"))

    def _write_all(self, data: Dict[str, str]) -> None:
        from cryptography.fernet import Fernet

        key, _ = self._resolve_master()
        self._atomic_write(self.data_path, Fernet(key).encrypt(json.dumps(data).encode("utf-8")))

    # -- public API -----------------------------------------------------------

    @staticmethod
    def _check(name: str) -> None:
        if not NAME_PATTERN.match(name):
            raise ValueError(f"Invalid secret name: {name!r}")

    def get(self, name: str) -> Optional[str]:
        self._check(name)
        with self._lock:
            value = self._read_all().get(name)
        _redactor.register(value)
        return value

    def set(self, name: str, value: str) -> None:
        self._check(name)
        _redactor.register(value)
        with self._lock:
            data = self._read_all()
            data[name] = value
            self._write_all(data)

    def delete(self, name: str) -> bool:
        self._check(name)
        with self._lock:
            data = self._read_all()
            existed = data.pop(name, None) is not None
            if existed:
                self._write_all(data)
        return existed

    def exists(self, name: str) -> bool:
        self._check(name)
        with self._lock:
            return name in self._read_all()

    def names(self, prefix: str = "") -> List[str]:
        with self._lock:
            return sorted(n for n in self._read_all() if n.startswith(prefix))

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            data = self._read_all()
            doomed = [n for n in data if n.startswith(prefix)]
            for name in doomed:
                del data[name]
            if doomed:
                self._write_all(data)
        return len(doomed)


def _restrict(path: Path, directory: bool = False) -> None:
    """Best-effort owner-only permissions (POSIX chmod; Windows icacls)."""
    try:
        if sys.platform == "win32":
            user = os.environ.get("USERNAME")
            if user:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F" if directory else f"{user}:F"],
                    capture_output=True, check=False, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,  # no console flash from the desktop app
                )
        else:
            os.chmod(path, 0o700 if directory else 0o600)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not restrict permissions on %s: %s", path, exc)
