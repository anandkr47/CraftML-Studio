"""
Hugging Face token storage on top of the encrypted SecretStore.

Replaces the old ``~/.craftml/settings`` Fernet-file scheme (key stored next to the data, and an
endpoint that returned the token in plaintext).  ``migrate_legacy`` moves an existing token over
once and securely removes the old files.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.cloud.secrets import HF_TOKEN as TOKEN, HF_USERNAME as USERNAME, SecretStore

logger = logging.getLogger(__name__)

LEGACY_DIR = Path.home() / ".craftml" / "settings"


def _store() -> SecretStore:
    from services.cloud_service import secrets

    return secrets()


def get_hf_token() -> Optional[str]:
    """The saved token, or None. Internal use only: never expose through an API."""
    try:
        return _store().get(TOKEN)
    except Exception as exc:  # noqa: BLE001 - a broken secret store shouldn't break unrelated features
        logger.error("Could not read the Hugging Face token: %s", exc)
        return None


def apply_to_environment(token: Optional[str] = None) -> None:
    """
    Expose the saved token to huggingface_hub (it reads HF_TOKEN), so gated models download for
    fine-tuning, chat and embeddings.  This is a local, single-user process; the value is never logged.
    """
    token = token if token is not None else get_hf_token()
    if token:
        os.environ["HF_TOKEN"] = token
    else:
        os.environ.pop("HF_TOKEN", None)


def save_hf_token(token: str, username: Optional[str]) -> None:
    store = _store()
    store.set(TOKEN, token)
    if username:
        store.set(USERNAME, username)
    apply_to_environment(token)


def delete_hf_token() -> None:
    store = _store()
    store.delete(TOKEN)
    store.delete(USERNAME)
    apply_to_environment("")


def status() -> Dict[str, Any]:
    token = get_hf_token()
    if not token:
        return {"is_authenticated": False, "username": None, "token_preview": None}
    username = None
    try:
        username = _store().get(USERNAME)
    except Exception:  # noqa: BLE001
        pass
    return {"is_authenticated": True, "username": username, "token_preview": f"hf_…{token[-4:]}"}


def _shred(path: Path) -> None:
    try:
        path.write_bytes(b"\0" * max(path.stat().st_size, 1))
    except OSError:
        pass
    try:
        path.unlink()
    except OSError as exc:
        logger.warning("Could not delete legacy file %s: %s", path, exc)


def migrate_legacy(legacy_dir: Path = LEGACY_DIR, store: Optional[SecretStore] = None) -> bool:
    """Move a token from the old file scheme into the SecretStore. Returns True if one was migrated."""
    token_file, key_file, meta_file = legacy_dir / "hf_token.enc", legacy_dir / ".key", legacy_dir / "hf_metadata.json"
    if not (token_file.exists() and key_file.exists()):
        return False
    store = store or _store()
    try:
        from cryptography.fernet import Fernet

        token = Fernet(key_file.read_bytes()).decrypt(token_file.read_bytes()).decode()
        store.set(TOKEN, token)
        try:
            username = json.loads(meta_file.read_text(encoding="utf-8")).get("username")
            if username:
                store.set(USERNAME, username)
        except (OSError, ValueError):
            pass
    except Exception as exc:  # noqa: BLE001 - leave the legacy files in place if anything went wrong
        logger.warning("Could not migrate the legacy Hugging Face token: %s", exc)
        return False

    for path in (token_file, key_file, meta_file):
        if path.exists():
            _shred(path)
    logger.info("Migrated the Hugging Face token into the encrypted secret store")
    return True
