"""
Tests for the runtime helpers: cache-first model loading, the broken-IPv6 workaround, the
out-of-process GGUF load check and run_server's script/module runner. No ML libraries needed.
"""

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ.setdefault("CRAFTML_USER_DATA_DIR", tempfile.mkdtemp(prefix="craftml-test-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

from core.utils import hub, net
from services.inference import gguf_check


# --- cached_first ------------------------------------------------------------------------

class Loader:
    def __init__(self, cached: bool):
        self.cached = cached
        self.calls = []

    def __call__(self, name, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("local_files_only") and not self.cached:
            raise OSError("not in cache")
        return ("model", name)


def test_cached_first_uses_the_cache_when_possible():
    load = Loader(cached=True)
    assert hub.cached_first(load, "org/model", dtype="f16") == ("model", "org/model")
    assert load.calls == [{"local_files_only": True, "dtype": "f16"}]


def test_cached_first_goes_online_when_not_cached():
    load = Loader(cached=False)
    assert hub.cached_first(load, "org/model") == ("model", "org/model")
    assert load.calls == [{"local_files_only": True}, {}]


def test_cached_first_loads_local_directories_directly(tmp_path):
    load = Loader(cached=False)
    hub.cached_first(load, str(tmp_path))
    assert load.calls == [{}]


def test_cached_first_reraises_real_errors():
    def load(name, **kwargs):
        raise OSError("repository not found")

    with pytest.raises(OSError, match="repository not found"):
        hub.cached_first(load, "org/missing")


# --- broken IPv6 -------------------------------------------------------------------------

V6 = (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0))
V4 = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))


@pytest.fixture
def fake_dns(monkeypatch):
    monkeypatch.setattr(net, "_installed", False)
    original = socket.getaddrinfo
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [V6, V4, V6])
    yield
    socket.getaddrinfo = original


def test_prefer_ipv4_reorders_stably(fake_dns):
    net.prefer_ipv4()
    assert socket.getaddrinfo("example.org", 443) == [V4, V6, V6]
    net.prefer_ipv4()  # idempotent: no double wrapping
    assert socket.getaddrinfo.__wrapped__("example.org", 443) == [V6, V4, V6]


@pytest.mark.parametrize(
    "v6_ok, v4_ok, broken",
    [(False, True, True), (True, True, False), (False, False, False), (True, False, False)],
)
def test_ipv6_broken_only_when_v6_fails_and_v4_works(fake_dns, monkeypatch, v6_ok, v4_ok, broken):
    monkeypatch.setattr(net, "_can_connect", lambda fam, *a: v6_ok if fam == socket.AF_INET6 else v4_ok)
    assert net.ipv6_broken("example.org") is broken


def test_ipv6_probe_leaves_single_family_hosts_alone(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [V4])
    monkeypatch.setattr(net, "_can_connect", lambda *a: pytest.fail("no probe needed"))
    assert net.ipv6_broken("example.org") is False


def test_ipv6_probe_offline(monkeypatch):
    def offline(*a, **k):
        raise socket.gaierror("no network")

    monkeypatch.setattr(socket, "getaddrinfo", offline)
    assert net.ipv6_broken("example.org") is False


# --- GGUF load check ---------------------------------------------------------------------

@pytest.fixture
def gguf_file(tmp_path, monkeypatch):
    monkeypatch.setattr(gguf_check, "_cache_file", lambda: tmp_path / "cache" / "gguf_checks.json")
    path = tmp_path / "model.gguf"
    path.write_bytes(b"GGUF")
    return path


def _child(code):
    return lambda path, n_ctx: [sys.executable, "-c", code]


def test_gguf_check_success_is_cached(gguf_file, monkeypatch):
    monkeypatch.setattr(gguf_check, "_check_cmd", _child("pass"))
    gguf_check.ensure_loadable(str(gguf_file), 512)
    monkeypatch.setattr(gguf_check, "_check_cmd", lambda *a: pytest.fail("should be cached"))
    gguf_check.ensure_loadable(str(gguf_file), 512)


def test_gguf_check_crash_becomes_an_error_and_is_cached(gguf_file, monkeypatch):
    # abort() as llama.cpp does; on Windows exit with abort's code (3) to avoid error-reporting dialogs
    code = ("import sys, os; sys.stderr.write('ggml.c:1: GGML_ASSERT(ggml_can_mul_mat(a, b)) failed\\n'); "
            "sys.stderr.flush(); os._exit(3) if os.name == 'nt' else os.abort()")
    monkeypatch.setattr(gguf_check, "_check_cmd", _child(code))
    with pytest.raises(gguf_check.GgufLoadError, match="crashed while loading.*GGML_ASSERT"):
        gguf_check.ensure_loadable(str(gguf_file), 512)
    monkeypatch.setattr(gguf_check, "_check_cmd", lambda *a: pytest.fail("should be cached"))
    with pytest.raises(gguf_check.GgufLoadError, match="GGML_ASSERT"):
        gguf_check.ensure_loadable(str(gguf_file), 512)


def test_gguf_check_reruns_when_the_file_changes(gguf_file, monkeypatch):
    monkeypatch.setattr(gguf_check, "_check_cmd", _child("raise SystemExit(1)"))
    with pytest.raises(gguf_check.GgufLoadError, match="exit code 1"):
        gguf_check.ensure_loadable(str(gguf_file), 512)
    gguf_file.write_bytes(b"GGUF-rebuilt")
    monkeypatch.setattr(gguf_check, "_check_cmd", _child("pass"))
    gguf_check.ensure_loadable(str(gguf_file), 512)


# --- run_server helper modes -------------------------------------------------------------

def test_run_server_runs_scripts_and_modules(tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("import sys; print('script', sys.argv[1:])", encoding="utf-8")
    runner = str(ROOT / "apps" / "backend" / "run_server.py")
    out = subprocess.run([sys.executable, runner, "--run-python-script", str(script), "a", "b"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "script ['a', 'b']" in out.stdout, out.stderr
    out = subprocess.run([sys.executable, runner, "--run-python-module", "json.tool", "--compact"],
                         input='{"a": 1}', capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == '{"a":1}', out.stderr


# --- stop sequences in streamed text --------------------------------------------------------

from services.inference.types import FALLBACK_STOP, StopTrimmer, format_messages_fallback  # noqa: E402


def _run(stops, chunks):
    trimmer = StopTrimmer(stops)
    out = []
    for chunk in chunks:
        out.append(trimmer.feed(chunk))
        if trimmer.done:
            break
    out.append(trimmer.flush())
    return "".join(out), trimmer.done


@pytest.mark.parametrize("chunks", [
    ["Paris is the capital.", "\nUser: and Spain?"],
    ["Paris is the capital.\n", "Us", "er: and"],
    ["Paris is the capital.\nU", "ser:"],
    list("Paris is the capital.\nUser: more"),
])
def test_stop_sequence_is_removed_even_when_split(chunks):
    assert _run([FALLBACK_STOP], chunks) == ("Paris is the capital.", True)


def test_text_resembling_a_stop_prefix_is_released():
    text, done = _run([FALLBACK_STOP], ["Line one\n", "Usually fine", "\nUs"])
    assert text == "Line one\nUsually fine\nUs" and not done


def test_earliest_of_several_stops_wins():
    assert _run(["###", "END"], ["abc END def ### x"]) == ("abc ", True)


def test_no_stops_passes_everything_through():
    assert _run([], ["a", "b"]) == ("ab", False)


def test_fallback_prompt_ends_with_assistant_turn():
    prompt = format_messages_fallback([{"role": "system", "content": "Be brief"}, {"role": "user", "content": "Hi"}])
    assert prompt == "System: Be brief\nUser: Hi\nAssistant:"


def test_run_server_does_nothing_when_reimported_by_multiprocessing(tmp_path):
    # Spawned multiprocessing children re-run the main script as __mp_main__; that must not start the
    # app (whose startup marks running jobs as interrupted) or a server.
    runner = str(ROOT / "apps" / "backend" / "run_server.py")
    code = ("import runpy, sys; runpy.run_path(%r, run_name='__mp_main__'); "
            "print('main' in sys.modules, 'uvicorn' in sys.modules)") % runner
    env = {**os.environ, "CRAFTML_USER_DATA_DIR": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, env=env)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False False"
