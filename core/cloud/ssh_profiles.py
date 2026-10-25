"""
SSH host profiles.  Non-secret settings live in a JSON file; the private key and optional
passphrase live in the SecretStore (``cloud/ssh/<name>/private_key`` / ``passphrase``).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

from core.cloud.errors import ConfigError
from core.cloud.schemas import SshProfile
from core.cloud.secrets import SecretStore


def key_secret(name: str) -> str:
    return f"cloud/ssh/{name}/private_key"


def passphrase_secret(name: str) -> str:
    return f"cloud/ssh/{name}/passphrase"


class SshProfileStore:
    def __init__(self, path: Path, secrets: SecretStore):
        self.path = Path(path)
        self.secrets = secrets
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=self.path.name + ".")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def list(self) -> List[SshProfile]:
        with self._lock:
            return [SshProfile(**v) for _, v in sorted(self._load().items())]

    def get(self, name: str) -> SshProfile:
        with self._lock:
            raw = self._load().get(name)
        if raw is None:
            raise ConfigError(f"SSH host '{name}' isn't set up.", hint="Add it in Settings → Cloud GPUs.")
        return SshProfile(**raw)

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._load()

    def save(self, profile: SshProfile, private_key: Optional[str], passphrase: Optional[str]) -> None:
        """Create or update a profile. A blank key on update keeps the stored one."""
        if private_key is not None and private_key.strip():
            if "PRIVATE KEY" not in private_key:
                raise ConfigError("That doesn't look like a private key.", hint="Paste the full key, including the BEGIN/END lines.")
            self.secrets.set(key_secret(profile.name), private_key.replace("\r\n", "\n").strip() + "\n")
        elif not self.secrets.exists(key_secret(profile.name)):
            raise ConfigError("A private key is required.")
        if passphrase:
            self.secrets.set(passphrase_secret(profile.name), passphrase)
        with self._lock:
            data = self._load()
            data[profile.name] = profile.model_dump()
            self._save(data)

    def delete(self, name: str) -> bool:
        with self._lock:
            data = self._load()
            existed = data.pop(name, None) is not None
            if existed:
                self._save(data)
        self.secrets.delete(key_secret(name))
        self.secrets.delete(passphrase_secret(name))
        return existed
