"""
Custom SSH host provider (Linux + NVIDIA GPU).

Runs the worker bundle on a host you control: SFTP-uploads the bundle, dataset and job file,
launches the worker detached (so it survives an SSH drop or an app crash) under ``timeout``
(the dead-man switch), tails its event file, and downloads the adapter over SFTP.

All remote paths are POSIX (``PurePosixPath``) and remote commands are built with
``shlex.quote``, so a Windows or macOS client behaves identically.  Secrets never appear on a
command line: the HF token goes in a 0600 env file that is sourced and deleted before launch.
The vendor SDK (paramiko) is imported lazily and confined to ``ParamikoSession``.
"""

from __future__ import annotations

import io
import json
import logging
import shlex
import stat
import time
from pathlib import Path, PurePosixPath
from typing import Callable, ClassVar, Dict, Iterator, List, Optional, Protocol, Tuple

from core.cloud.errors import (
    AuthError,
    ConfigError,
    HostKeyError,
    RemoteExecutionError,
    TransientError,
)
from core.cloud.hostkeys import HostKeyStore, fingerprint
from core.cloud.providers.base import CloudProvider, InferenceEndpoint
from core.cloud.retry import retry_call
from core.cloud.schemas import (
    AccountInfo,
    Capabilities,
    FieldSpec,
    ProviderId,
    RemoteEvent,
    RemoteJobHandle,
    RemoteModel,
    RemoteStatus,
    RemoteTrainingSpec,
    SshProfile,
    parse_event_line,
)
from core.cloud.secrets import SecretStore, redact
from core.cloud.ssh_profiles import SshProfileStore, key_secret, passphrase_secret
from core.cloud.tunnel import LocalForward

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime"
CONNECT_TIMEOUT = 15.0
POLL_INTERVAL = 0.25
LIVENESS_INTERVAL = 10.0
RECONNECT_WINDOW = 300.0
TERMINAL = ("completed", "failed", "stopped")


class SshSession(Protocol):
    """What the provider needs from an SSH connection (paramiko-backed in production)."""

    def run(self, command: str, timeout: float = 60.0) -> Tuple[int, str, str]: ...
    def put(self, data: bytes, remote_path: str, mode: int = 0o644) -> None: ...
    def get_tree(self, remote_dir: str, local_dir: Path) -> None: ...
    def open_forward_channel(self, host: str, port: int): ...
    def tail_lines(self, remote_file: str, start_line: int, stop: Callable[[], bool]) -> Iterator[str]: ...
    def close(self) -> None: ...


SessionFactory = Callable[[SshProfile, SecretStore, HostKeyStore], SshSession]


# --------------------------------------------------------------------------- pure helpers

def remote_dir_for(home: str, profile: SshProfile, job_id: str) -> str:
    base = PurePosixPath(profile.workdir)
    return str((base if base.is_absolute() else PurePosixPath(home) / base) / job_id)


def build_launch_command(
    profile: SshProfile, remote_dir: str, job_id: str, max_seconds: int, has_env: bool
) -> str:
    """
    Shell command that verifies and unpacks the bundle, then starts the worker detached.

    * ``timeout`` hard-limits the run even if the app dies (dead-man switch);
    * ``setsid`` makes the worker a process-group leader so cleanup can kill the whole tree;
    * the HF token is sourced from ``env.sh`` into the *launching* shell (children inherit it) and
      the file is deleted right after, so it is never on a command line and never races the worker;
    * the worker's exit code is written to ``exit_code``.
    """
    d = shlex.quote(remote_dir)
    if profile.runtime == "docker":
        name = shlex.quote(f"craftml-{job_id}")
        inner = (
            f"docker run --rm --name {name} --gpus all -v {d}:/work -w /work/craftml_worker "
            f"{'-e HF_TOKEN ' if has_env else ''}"
            f"-e CRAFTML_JOB_FILE=/work/job.json -e CRAFTML_USE_VENV=0 {DOCKER_IMAGE} bash bootstrap.sh"
        )
    else:
        inner = f"env CRAFTML_JOB_FILE={d}/job.json bash {d}/craftml_worker/bootstrap.sh"
    runner = (
        f"timeout --signal=TERM --kill-after=30 {int(max_seconds)} {inner} > {d}/worker.log 2>&1; "
        f"echo $? > {d}/exit_code"
    )
    # Every step is chained with && so a failed checksum or extraction can never fall through to launching.
    source_env = f"set -a && . {d}/env.sh && set +a && " if has_env else ""
    return (
        f"cd {d} && sha256sum -c bundle.sha256 >/dev/null && tar xzf bundle.tar.gz && "
        f"{source_env}"
        f"(nohup setsid bash -c {shlex.quote(runner)} >/dev/null 2>&1 & echo $! > {d}/pid) && "
        f"rm -f {d}/bundle.tar.gz {d}/env.sh"
    )


def parse_status_files(exit_code: Optional[str], alive: bool, exists: bool) -> RemoteStatus:
    if not exists:
        return "gone"
    if exit_code is not None and exit_code.strip():
        return "succeeded" if exit_code.strip() == "0" else "failed"
    return "running" if alive else "failed"


event_from_line = parse_event_line  # kept for callers/tests that import it from here


def _is_network_error(exc: BaseException) -> bool:
    return isinstance(exc, (TransientError, OSError, EOFError)) or type(exc).__module__.startswith("paramiko")


# --------------------------------------------------------------------------- paramiko session

class PinnedPolicy:
    """Host-key policy: only a key the user has confirmed is accepted (no auto-add)."""

    def __init__(self, store: HostKeyStore, host: str, port: int):
        self.store, self.host, self.port = store, host, port

    def missing_host_key(self, client, hostname, key) -> None:  # paramiko MissingHostKeyPolicy duck type
        fp = fingerprint(key.asbytes())
        status = self.store.check(self.host, self.port, key.get_name(), fp)
        if status == "trusted":
            return
        if status == "changed":
            raise HostKeyError(
                f"The host key for {self.host} has CHANGED. This could be a man-in-the-middle attack.",
                fingerprint=fp, changed=True,
                hint="If you reinstalled the server, remove it in Settings and add it again.",
            )
        raise HostKeyError(
            f"{self.host} hasn't been verified yet.", fingerprint=fp,
            hint="Confirm its fingerprint in Settings → Cloud GPUs → SSH hosts.",
        )


def load_private_key(text: str, passphrase: Optional[str]):
    import paramiko

    last: Optional[Exception] = None
    for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return cls.from_private_key(io.StringIO(text), password=passphrase)
        except paramiko.PasswordRequiredException as exc:
            raise ConfigError("This key is passphrase-protected.", hint="Enter the passphrase for this host.") from exc
        except (paramiko.SSHException, ValueError) as exc:
            last = exc
    raise ConfigError(f"Unsupported or invalid private key ({last}).", hint="Use an Ed25519, ECDSA or RSA key in OpenSSH/PEM format.")


def probe_host_key(host: str, port: int, timeout: float = CONNECT_TIMEOUT) -> Tuple[str, str]:
    """Fetch the server's host key without authenticating: (key type, fingerprint)."""
    import paramiko

    try:
        transport = paramiko.Transport((host, port))
        try:
            transport.start_client(timeout=timeout)
            key = transport.get_remote_server_key()
            return key.get_name(), fingerprint(key.asbytes())
        finally:
            transport.close()
    except OSError as exc:
        raise TransientError(f"Couldn't reach {host}:{port} ({exc}).", hint="Check the address, port and firewall.") from exc
    except paramiko.SSHException as exc:
        raise TransientError(f"SSH handshake with {host}:{port} failed ({exc}).") from exc


class ParamikoSession:
    """Production ``SshSession``. All paramiko usage is here."""

    def __init__(self, profile: SshProfile, secrets: SecretStore, host_keys: HostKeyStore):
        import paramiko

        key_text = secrets.get(key_secret(profile.name))
        if not key_text:
            raise ConfigError(f"No private key stored for '{profile.name}'.")
        pkey = load_private_key(key_text, secrets.get(passphrase_secret(profile.name)))

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(PinnedPolicy(host_keys, profile.host, profile.port))
        try:
            client.connect(
                hostname=profile.host, port=profile.port, username=profile.username, pkey=pkey,
                allow_agent=False, look_for_keys=False, timeout=CONNECT_TIMEOUT,
                banner_timeout=CONNECT_TIMEOUT, auth_timeout=CONNECT_TIMEOUT,
            )
        except paramiko.AuthenticationException as exc:
            raise AuthError(f"{profile.host} rejected the key for user '{profile.username}'.") from exc
        except (paramiko.SSHException, OSError, EOFError) as exc:
            raise TransientError(f"Couldn't connect to {profile.host}:{profile.port} ({exc}).") from exc
        self._client = client
        self._sftp = None

    @property
    def sftp(self):
        if self._sftp is None:
            self._sftp = self._client.open_sftp()
        return self._sftp

    def run(self, command: str, timeout: float = 60.0) -> Tuple[int, str, str]:
        _, out, err = self._client.exec_command(command, timeout=timeout)
        stdout = out.read().decode("utf-8", errors="replace")
        stderr = err.read().decode("utf-8", errors="replace")
        return out.channel.recv_exit_status(), stdout, stderr

    def put(self, data: bytes, remote_path: str, mode: int = 0o644) -> None:
        self.sftp.putfo(io.BytesIO(data), remote_path)
        self.sftp.chmod(remote_path, mode)

    def get_tree(self, remote_dir: str, local_dir: Path) -> None:
        local_dir.mkdir(parents=True, exist_ok=True)
        for entry in self.sftp.listdir_attr(remote_dir):
            remote_path = str(PurePosixPath(remote_dir) / entry.filename)
            local_path = local_dir / entry.filename
            if stat.S_ISDIR(entry.st_mode):
                self.get_tree(remote_path, local_path)
            elif stat.S_ISREG(entry.st_mode):
                self.sftp.get(remote_path, str(local_path))

    def open_forward_channel(self, host: str, port: int):
        """A direct-tcpip channel to ``host:port`` as seen from the SSH server."""
        return self._client.get_transport().open_channel("direct-tcpip", (host, port), ("127.0.0.1", 0))

    def tail_lines(self, remote_file: str, start_line: int, stop: Callable[[], bool]) -> Iterator[str]:
        channel = self._client.get_transport().open_session()
        channel.exec_command(f"tail -n +{int(start_line)} -F {shlex.quote(remote_file)} 2>/dev/null")
        buffer = b""
        try:
            while not stop():
                if channel.recv_ready():
                    buffer += channel.recv(65536)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        yield line.decode("utf-8", errors="replace")
                elif channel.exit_status_ready() or channel.closed:
                    return
                else:
                    time.sleep(POLL_INTERVAL)
        finally:
            channel.close()

    def close(self) -> None:
        try:
            if self._sftp is not None:
                self._sftp.close()
            self._client.close()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- provider

class SshProvider(CloudProvider):
    id: ClassVar[ProviderId] = ProviderId.SSH
    label: ClassVar[str] = "SSH host"
    description: ClassVar[str] = (
        "Train on your own Linux server with an NVIDIA GPU. Your dataset is copied to the host and "
        "removed afterwards."
    )
    capabilities: ClassVar[Capabilities] = Capabilities(training=True, inference=True)
    fields: ClassVar[List[FieldSpec]] = []  # per-host profiles instead of a single credential form

    def __init__(
        self,
        secrets: SecretStore,
        host_keys: Optional[HostKeyStore] = None,
        profiles: Optional[SshProfileStore] = None,
        session_factory: SessionFactory = ParamikoSession,
        sleep: Callable[[float], None] = time.sleep,
    ):
        super().__init__(secrets)
        directory = getattr(secrets, "directory", Path("."))
        self.host_keys = host_keys or HostKeyStore(Path(directory) / "ssh_known_hosts.json")
        self.profiles = profiles or SshProfileStore(Path(directory) / "ssh_profiles.json", secrets)
        self._session_factory = session_factory
        self._sleep = sleep
        self._tunnels: Dict[str, Tuple[SshSession, LocalForward]] = {}

    # -- credentials = profiles ------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.profiles.list())

    def validate_credentials(self) -> AccountInfo:
        count = len(self.profiles.list())
        if not count:
            raise ConfigError("No SSH hosts set up.")
        return AccountInfo(name=f"{count} SSH host{'s' if count != 1 else ''}")

    def _session(self, profile: SshProfile) -> SshSession:
        return self._session_factory(profile, self.secrets, self.host_keys)

    def describe_host(self, name: str) -> Dict[str, object]:
        """Connect and report OS and GPUs (used by the UI's "Test connection")."""
        profile = self.profiles.get(name)
        session = self._session(profile)
        try:
            return self._inspect(session, profile)
        finally:
            session.close()

    def _inspect(self, session: SshSession, profile: SshProfile) -> Dict[str, object]:
        _, uname, _ = session.run("uname -s")
        os_name = uname.strip() or "unknown"
        gpus: List[Dict[str, object]] = []
        code, out, _ = session.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits")
        if code == 0:
            for line in out.strip().splitlines():
                gpu_name, _, mem = line.rpartition(",")
                try:
                    gpus.append({"name": gpu_name.strip(), "vram_gb": round(float(mem) / 1024, 1)})
                except ValueError:
                    continue
        docker_ok = profile.runtime != "docker" or session.run("docker --version")[0] == 0
        return {"os": os_name, "gpus": gpus, "docker": docker_ok, "ready": os_name == "Linux" and bool(gpus) and docker_ok}

    # -- training -----------------------------------------------------------------

    def submit_training(self, spec: RemoteTrainingSpec, bundle) -> RemoteJobHandle:
        profile = self.profiles.get(spec.target.ssh_profile or "")
        session = self._session(profile)
        remote_dir: Optional[str] = None
        try:
            info = self._inspect(session, profile)
            if info["os"] != "Linux":
                raise ConfigError(f"{profile.host} runs {info['os']}; remote training needs Linux with an NVIDIA GPU.")
            if not info["gpus"]:
                raise ConfigError(f"No NVIDIA GPU found on {profile.host} (nvidia-smi failed).")
            if not info["docker"]:
                raise ConfigError(f"Docker isn't available on {profile.host}.", hint="Install Docker or switch the host to 'venv'.")

            _, home, _ = session.run("printf %s \"$HOME\"")
            remote_dir = remote_dir_for(home.strip(), profile, spec.job_id)
            d = shlex.quote(remote_dir)
            code, _, err = session.run(f"mkdir -p {d} && chmod 700 {d}")
            if code != 0:
                raise RemoteExecutionError(f"Couldn't create {remote_dir} on {profile.host}: {err.strip()}")

            dataset = Path(spec.dataset_path)
            job = {
                "job_id": spec.job_id, "model_name": spec.model_name, "dataset_filename": dataset.name,
                "training_method": spec.training_method, "lora_config": spec.lora_config,
                "training_config": spec.training_config,
            }
            base = PurePosixPath(remote_dir)
            session.put(bundle.data, str(base / "bundle.tar.gz"))
            session.put(f"{bundle.sha256}  bundle.tar.gz\n".encode(), str(base / "bundle.sha256"))
            session.put(json.dumps(job).encode("utf-8"), str(base / "job.json"))
            session.put(dataset.read_bytes(), str(base / dataset.name))

            token = spec.hf_token.get_secret_value() if spec.hf_token else None
            if token:  # via a 0600 file sourced then deleted by the launch command, never a command line
                session.put(f"HF_TOKEN={shlex.quote(token)}\n".encode(), str(base / "env.sh"), mode=0o600)

            command = build_launch_command(profile, remote_dir, spec.job_id, spec.target.max_runtime_minutes * 60, bool(token))
            code, _, err = session.run(command, timeout=120)
            if code != 0:
                raise RemoteExecutionError(f"Couldn't start the worker on {profile.host}: {redact(err.strip()) or 'bundle verification failed'}")
        except BaseException:
            if remote_dir:
                self._rm(session, remote_dir)
            raise
        finally:
            session.close()

        gpu = (info["gpus"][0]["name"] if info["gpus"] else None)  # type: ignore[index]
        return RemoteJobHandle(
            provider=self.id, remote_id=f"{profile.name}:{spec.job_id}", job_id=spec.job_id, gpu_name=gpu,
            meta={"profile": profile.name, "dir": remote_dir, "runtime": profile.runtime},
        )

    def stream_events(self, handle: RemoteJobHandle, stop: Callable[[], bool]) -> Iterator[RemoteEvent]:
        """
        Tail the worker's event file, reconnecting after network drops (the worker keeps running
        remotely) and detecting a worker that died without reporting.
        """
        profile = self.profiles.get(handle.meta["profile"])
        events_file = str(PurePosixPath(handle.meta["dir"]) / "events.jsonl")
        state: Dict[str, object] = {"consumed": 0, "terminal": False, "dead": None}
        session: Optional[SshSession] = None
        down_since: Optional[float] = None

        try:
            while not stop() and not state["terminal"]:
                try:
                    if session is None:
                        session = self._session(profile)
                        down_since = None
                    yield from self._tail(session, handle, events_file, state, stop)
                    if state["dead"]:
                        yield from self._finish_dead(session, handle, events_file, state)
                        return
                    if not (stop() or state["terminal"]):  # channel closed on its own: reopen
                        self._close(session)
                        session = None
                        self._sleep(1.0)
                except (HostKeyError, AuthError, ConfigError):
                    raise
                except Exception as exc:  # noqa: BLE001
                    if not _is_network_error(exc):
                        raise
                    self._close(session)
                    session = None
                    down_since = down_since if down_since is not None else time.monotonic()
                    if time.monotonic() - down_since > RECONNECT_WINDOW:
                        raise TransientError(
                            f"Lost the connection to {profile.host} and couldn't reconnect ({exc}).",
                            hint="The job may still be running there; check the host.",
                        ) from exc
                    self._sleep(min(5.0, 0.5 + (time.monotonic() - down_since) / 10))
        finally:
            self._close(session)

    def _tail(self, session: SshSession, handle: RemoteJobHandle, events_file: str,
              state: Dict[str, object], stop: Callable[[], bool]) -> Iterator[RemoteEvent]:
        last_check = [time.monotonic()]

        def should_stop() -> bool:
            if stop():
                return True
            if time.monotonic() - last_check[0] >= LIVENESS_INTERVAL:  # tail -F never ends by itself
                last_check[0] = time.monotonic()
                status = self._status_via(session, handle)
                if status in ("failed", "gone"):
                    state["dead"] = status
                    return True
            return False

        for line in session.tail_lines(events_file, int(state["consumed"]) + 1, should_stop):  # type: ignore[arg-type]
            state["consumed"] = int(state["consumed"]) + 1  # type: ignore[arg-type]
            event = event_from_line(line)
            if event is None:
                continue
            yield event
            if event.type == "status" and event.status in TERMINAL:
                state["terminal"] = True
                return

    def _finish_dead(self, session: SshSession, handle: RemoteJobHandle, events_file: str,
                     state: Dict[str, object]) -> Iterator[RemoteEvent]:
        """The worker is gone: first deliver any events it wrote, then explain the crash if none was final."""
        _, out, _ = session.run(f"tail -n +{int(state['consumed']) + 1} {shlex.quote(events_file)} 2>/dev/null")  # type: ignore[arg-type]
        for line in out.splitlines():
            event = event_from_line(line)
            if event is None:
                continue
            yield event
            if event.type == "status" and event.status in TERMINAL:
                return
        yield from self._crash_events(session, handle, str(state["dead"]))

    def _crash_events(self, session: SshSession, handle: RemoteJobHandle, status: str) -> Iterator[RemoteEvent]:
        """Explain a worker that vanished without a final event (killed by `timeout`, OOM-killer, host reboot…)."""
        d = shlex.quote(handle.meta["dir"])
        _, code, _ = session.run(f"cat {d}/exit_code 2>/dev/null")
        _, tail, _ = session.run(f"tail -n 30 {d}/worker.log 2>/dev/null")
        if tail.strip():
            yield RemoteEvent(type="log", level="error", message=redact(tail.strip()))
        reason = "its working directory is gone" if status == "gone" else f"exit code {code.strip() or 'unknown'}"
        yield RemoteEvent(type="status", status="failed", error=f"The worker stopped unexpectedly ({reason}).")

    def fetch_artifacts(self, handle: RemoteJobHandle, dest: Path) -> Path:
        profile = self.profiles.get(handle.meta["profile"])
        final = Path(dest) / "final"
        session = retry_call(lambda: self._session(profile))
        try:
            session.get_tree(str(PurePosixPath(handle.meta["dir"]) / "output" / "final"), final)
        finally:
            session.close()
        if not (final / "adapter_config.json").exists() and not (final / "config.json").exists():
            raise RemoteExecutionError("The remote job finished but returned no model files.")
        return final

    def get_status(self, handle: RemoteJobHandle) -> RemoteStatus:
        profile = self.profiles.get(handle.meta["profile"])
        session = self._session(profile)
        try:
            return self._status_via(session, handle)
        finally:
            session.close()

    def _status_via(self, session: SshSession, handle: RemoteJobHandle) -> RemoteStatus:
        d = shlex.quote(handle.meta["dir"])
        _, out, _ = session.run(
            f"if [ -d {d} ]; then echo exists; cat {d}/exit_code 2>/dev/null || true; "
            f"echo ---; kill -0 $(cat {d}/pid 2>/dev/null) 2>/dev/null && echo alive; fi"
        )
        exists = out.startswith("exists")
        head, _, tail = out.partition("---")
        exit_code = "\n".join(head.splitlines()[1:]).strip() or None
        return parse_status_files(exit_code, "alive" in tail, exists)

    def cancel(self, handle: RemoteJobHandle) -> None:
        profile = self.profiles.get(handle.meta["profile"])
        session = self._session(profile)
        try:
            session.run(f"touch {shlex.quote(str(PurePosixPath(handle.meta['dir']) / 'CANCEL'))}")
        finally:
            session.close()

    def cleanup(self, handle: RemoteJobHandle) -> None:
        profile = self.profiles.get(handle.meta["profile"])
        session = retry_call(lambda: self._session(profile), attempts=3)
        try:
            self._rm(session, handle.meta["dir"], job_id=handle.job_id, docker=handle.meta.get("runtime") == "docker")
        finally:
            session.close()

    # -- inference: tunnel to an OpenAI-compatible server already running on the host --------

    def inference_endpoint(self, model: RemoteModel) -> InferenceEndpoint:
        """``model.endpoint_id`` is the SSH host name; the server's port is the profile's ``inference_port``."""
        profile = self.profiles.get(model.endpoint_id or "")
        if not profile.inference_port:
            raise ConfigError(
                f"'{profile.name}' has no inference port.",
                hint="Set the port your OpenAI-compatible server (vLLM, llama.cpp, Ollama…) listens on.",
            )
        existing = self._tunnels.get(profile.name)
        if existing is None or not existing[1].alive:
            self._close_tunnel(profile.name)
            session = self._session(profile)
            forward = LocalForward(lambda: session.open_forward_channel("127.0.0.1", int(profile.inference_port)))
            forward.start()
            self._tunnels[profile.name] = (session, forward)
        port = self._tunnels[profile.name][1].port
        return InferenceEndpoint(kind="openai", base_url=f"http://127.0.0.1:{port}/v1", headers={}, model=model.remote_model)

    def test_model(self, model: RemoteModel) -> str:
        from core.cloud.http import default_http
        from core.cloud.providers.remote_inference import _probe_openai

        return _probe_openai(default_http(), self.inference_endpoint(model), "The SSH host")

    def close_tunnels(self) -> None:
        for name in list(self._tunnels):
            self._close_tunnel(name)

    def _close_tunnel(self, name: str) -> None:
        entry = self._tunnels.pop(name, None)
        if entry:
            entry[1].close()
            self._close(entry[0])

    # -- internals ------------------------------------------------------------------

    @staticmethod
    def _rm(session: SshSession, remote_dir: str, job_id: Optional[str] = None, docker: bool = False) -> None:
        """Stop the worker process tree (and container) and delete the run directory. Idempotent."""
        d = shlex.quote(remote_dir)
        if docker and job_id:
            session.run(f"docker rm -f {shlex.quote('craftml-' + job_id)} >/dev/null 2>&1 || true")
        session.run(
            f"if [ -f {d}/pid ]; then P=$(cat {d}/pid); kill -TERM -- -$P 2>/dev/null; sleep 2; "
            f"kill -KILL -- -$P 2>/dev/null; fi; rm -rf {d}"
        )

    @staticmethod
    def _close(session: Optional[SshSession]) -> None:
        if session is not None:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass
