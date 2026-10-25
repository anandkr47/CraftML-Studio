"""SecretStore: envelope encryption, keychain/file fallback, atomic writes, redaction."""

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

pytest.importorskip("cryptography")

from core.cloud.errors import SecretStoreError
from core.cloud.secrets import MASTER_FILE, SecretStore, redact


class FakeKeyring:
    priority = 5

    def __init__(self, fail_get=False, fail_set=False):
        self.items, self.fail_get, self.fail_set = {}, fail_get, fail_set

    def get_password(self, service, user):
        if self.fail_get:
            raise RuntimeError("keychain locked")
        return self.items.get((service, user))

    def set_password(self, service, user, value):
        if self.fail_set:
            raise RuntimeError("keychain denied")
        self.items[(service, user)] = value


def test_roundtrip_with_keychain_holding_only_the_master_key(tmp_path):
    keyring = FakeKeyring()
    store = SecretStore(tmp_path, keyring_backend=keyring)
    store.set("cloud/runpod/api_key", "rpa_supersecretvalue123")

    assert store.get("cloud/runpod/api_key") == "rpa_supersecretvalue123"
    assert store.exists("cloud/runpod/api_key") and not store.exists("cloud/modal/token_id")
    assert store.storage_info() == {"backend": "keychain", "secure": True, "detail": "OS keychain"}
    assert not (tmp_path / MASTER_FILE).exists()
    assert b"rpa_supersecretvalue123" not in store.data_path.read_bytes()  # ciphertext only
    assert len(next(iter(keyring.items.values()))) < 100  # keychain holds just the small master key


def test_large_ssh_key_roundtrip_exceeds_credential_manager_limit(tmp_path):
    key = "-----BEGIN OPENSSH PRIVATE KEY-----\n" + ("A" * 70 + "\n") * 60 + "-----END OPENSSH PRIVATE KEY-----\n"
    assert len(key) > 4000  # larger than Windows Credential Manager's ~2.5 KB per entry
    keyring = FakeKeyring()
    store = SecretStore(tmp_path, keyring_backend=keyring)
    store.set("cloud/ssh/gpu-box/private_key", key)
    assert SecretStore(tmp_path, keyring_backend=keyring).get("cloud/ssh/gpu-box/private_key") == key


def test_unicode_values_and_listing(tmp_path):
    store = SecretStore(tmp_path, keyring_backend=FakeKeyring())
    store.set("cloud/ssh/p/passphrase", "pässwörd-日本語")
    store.set("cloud/ssh/q/passphrase", "x" * 8)
    store.set("cloud/modal/token_id", "ak-abcdefghijk")
    assert store.get("cloud/ssh/p/passphrase") == "pässwörd-日本語"
    assert store.names("cloud/ssh/") == ["cloud/ssh/p/passphrase", "cloud/ssh/q/passphrase"]
    assert store.delete_prefix("cloud/ssh/") == 2 and store.names() == ["cloud/modal/token_id"]
    assert store.delete("cloud/modal/token_id") is True and store.delete("cloud/modal/token_id") is False


def test_falls_back_to_a_protected_file_when_the_keychain_is_unusable(tmp_path):
    store = SecretStore(tmp_path, keyring_backend=FakeKeyring(fail_get=True, fail_set=True))
    store.set("cloud/together/api_key", "tok_abcdefghijkl")
    info = store.storage_info()
    assert info["backend"] == "file" and info["secure"] is False
    assert (tmp_path / MASTER_FILE).exists()
    if sys.platform != "win32":
        assert (tmp_path / MASTER_FILE).stat().st_mode & 0o777 == 0o600
        assert store.data_path.stat().st_mode & 0o777 == 0o600
    assert SecretStore(tmp_path, keyring_backend=None).get("cloud/together/api_key") == "tok_abcdefghijkl"


def test_no_keyring_package_at_all(tmp_path):
    store = SecretStore(tmp_path, keyring_backend=None)
    store.set("a", "value-123456")
    assert store.get("a") == "value-123456" and store.storage_info()["backend"] == "file"


def test_locked_keychain_later_falls_through_to_the_existing_master_file(tmp_path):
    first = SecretStore(tmp_path, keyring_backend=None)
    first.set("a", "value-123456")
    assert SecretStore(tmp_path, keyring_backend=FakeKeyring(fail_get=True)).get("a") == "value-123456"


def test_missing_master_key_with_existing_data_is_a_clear_error(tmp_path):
    SecretStore(tmp_path, keyring_backend=FakeKeyring()).set("a", "value-123456")  # master lives only in that fake keychain
    with pytest.raises(SecretStoreError) as err:
        SecretStore(tmp_path, keyring_backend=FakeKeyring()).get("a")
    assert "Re-enter" in err.value.user_message()


def test_wrong_master_key_is_a_clear_error_not_a_wipe(tmp_path):
    SecretStore(tmp_path, keyring_backend=FakeKeyring()).set("a", "value-123456")
    other = FakeKeyring()
    SecretStore(tmp_path / "elsewhere", keyring_backend=other).set("b", "another-value")  # creates a different master
    with pytest.raises(SecretStoreError):
        SecretStore(tmp_path, keyring_backend=other).get("a")
    assert (tmp_path / "secrets.enc").exists()  # nothing was deleted


def test_failed_write_leaves_the_previous_file_intact_and_no_temp_files(tmp_path, monkeypatch):
    store = SecretStore(tmp_path, keyring_backend=FakeKeyring())
    store.set("a", "first-value-1")
    before = store.data_path.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.set("b", "second-value")
    monkeypatch.undo()

    assert store.data_path.read_bytes() == before and store.get("a") == "first-value-1"
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("secrets.enc.")] == []


def test_concurrent_writers_do_not_lose_updates(tmp_path):
    store = SecretStore(tmp_path, keyring_backend=FakeKeyring())
    threads = [threading.Thread(target=store.set, args=(f"k{i}", f"value-{i:04d}")) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert store.names() == sorted(f"k{i}" for i in range(20))


@pytest.mark.parametrize("bad", ["", "UPPER", "has space", "../escape", "-lead"])
def test_invalid_names_are_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        SecretStore(tmp_path, keyring_backend=FakeKeyring()).get(bad)


def test_values_become_redacted_in_logs(tmp_path):
    store = SecretStore(tmp_path, keyring_backend=FakeKeyring())
    store.set("cloud/x/token", "plainsecret-9876")
    assert "plainsecret-9876" not in redact("connecting with plainsecret-9876 now")
    assert redact("Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123") == "Authorization: ***"
