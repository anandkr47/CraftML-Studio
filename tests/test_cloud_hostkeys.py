"""App-owned SSH host-key store: trust on first use, pin, detect change."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cloud.hostkeys import HostKeyStore, fingerprint


def test_fingerprint_matches_openssh_format():
    fp = fingerprint(b"example key blob")
    assert fp.startswith("SHA256:") and "=" not in fp and len(fp) == 7 + 43


def test_unknown_then_trusted_then_changed(tmp_path):
    store = HostKeyStore(tmp_path / "known_hosts.json")
    fp = fingerprint(b"key-1")
    assert store.check("Box.Example.com", 22, "ssh-ed25519", fp) == "unknown"

    store.trust("Box.Example.com", 22, "ssh-ed25519", fp)
    assert store.check("box.example.com", 22, "ssh-ed25519", fp) == "trusted"  # host match is case-insensitive
    assert store.check("box.example.com", 22, "ssh-ed25519", fingerprint(b"key-2")) == "changed"
    assert store.check("box.example.com", 22, "ssh-rsa", fp) == "changed"  # key type switch is a change too
    assert store.check("box.example.com", 2222, "ssh-ed25519", fp) == "unknown"  # port is part of identity


def test_forget_and_persistence(tmp_path):
    path = tmp_path / "nested" / "known_hosts.json"
    HostKeyStore(path).trust("h", 22, "ssh-ed25519", "SHA256:x")
    reopened = HostKeyStore(path)
    assert reopened.get("h", 22) == {"type": "ssh-ed25519", "fingerprint": "SHA256:x"}
    assert reopened.forget("h", 22) is True and reopened.forget("h", 22) is False
    assert reopened.get("h", 22) is None


def test_corrupt_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "known_hosts.json"
    path.write_text("{not json", encoding="utf-8")
    assert HostKeyStore(path).check("h", 22, "ssh-ed25519", "SHA256:x") == "unknown"
