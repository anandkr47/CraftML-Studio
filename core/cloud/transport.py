"""
Hugging Face Hub transport for runs that can't share a filesystem with the desktop app
(RunPod pods, Modal).  The dataset and worker bundle go up to a *private* dataset repo, the
trained adapter comes back from a *private* model repo, and both repos are deleted afterwards
so user data doesn't linger in the user's HF account.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.cloud.errors import AuthError, ConfigError, RemoteExecutionError, TransientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunRepos:
    dataset_repo: str  # private dataset repo: bundle, job.json, data, (pod.log on failure)
    adapter_repo: str  # private model repo the worker uploads the adapter to


def repo_names(username: str, job_id: str) -> RunRepos:
    slug = job_id.replace("_", "-").lower()
    return RunRepos(dataset_repo=f"{username}/craftml-{slug}", adapter_repo=f"{username}/craftml-{slug}-adapter")


class HubTransport:
    """Thin, testable wrapper over ``huggingface_hub`` (the API object is injectable)."""

    def __init__(self, token: str, api: Optional[Any] = None, snapshot_download: Optional[Callable[..., str]] = None):
        if not token:
            raise ConfigError("A Hugging Face token is required for this provider.", hint="Add one in Settings → Hugging Face.")
        self.token = token
        if api is None:
            from huggingface_hub import HfApi

            api = HfApi(token=token)
        self.api = api
        self._snapshot_download = snapshot_download

    def _wrap(self, action: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classify huggingface_hub errors without importing them eagerly
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403):
                raise AuthError(f"Hugging Face refused to {action}.", hint="Use a token with write access.") from exc
            if status in (429, 500, 502, 503, 504) or isinstance(exc, (ConnectionError, TimeoutError, OSError)):
                raise TransientError(f"Hugging Face is unreachable while trying to {action} ({exc}).") from exc
            raise RemoteExecutionError(f"Could not {action} on Hugging Face: {exc}") from exc

    def username(self) -> str:
        info = self._wrap("verify the token", self.api.whoami)
        return info["name"]

    def upload_run_assets(self, job_id: str, files: Dict[str, bytes]) -> RunRepos:
        """Create the private dataset repo and upload ``files`` (name -> bytes)."""
        repos = repo_names(self.username(), job_id)
        self._wrap("create the transfer repo", lambda: self.api.create_repo(
            repo_id=repos.dataset_repo, repo_type="dataset", private=True, exist_ok=True))
        for name, data in files.items():
            self._wrap(f"upload {name}", lambda n=name, d=data: self.api.upload_file(
                path_or_fileobj=d, path_in_repo=n, repo_id=repos.dataset_repo, repo_type="dataset"))
        return repos

    def adapter_exists(self, repo: str) -> bool:
        try:
            return bool(self.api.list_repo_files(repo_id=repo, repo_type="model"))
        except Exception:  # noqa: BLE001 - missing repo
            return False

    def read_text(self, repo: str, filename: str, repo_type: str = "dataset") -> Optional[str]:
        """A small text file from a repo (used to fetch ``pod.log`` after a pod dies), or None."""
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(repo_id=repo, filename=filename, repo_type=repo_type, token=self.token)
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return None

    def download_adapter(self, repo: str, dest: Path) -> Path:
        """Download the adapter into ``dest/final``."""
        final = Path(dest) / "final"
        final.mkdir(parents=True, exist_ok=True)
        download = self._snapshot_download
        if download is None:
            from huggingface_hub import snapshot_download as download  # type: ignore[assignment]
        self._wrap("download the adapter", lambda: download(
            repo_id=repo, repo_type="model", local_dir=str(final), token=self.token))
        if not (final / "adapter_config.json").exists() and not (final / "config.json").exists():
            raise RemoteExecutionError("The adapter repo exists but contains no model files.")
        # snapshot_download leaves a .cache folder behind
        cache = final / ".cache"
        if cache.exists():
            import shutil

            shutil.rmtree(cache, ignore_errors=True)
        return final

    def delete_repos(self, repos: RunRepos) -> List[str]:
        """Best-effort removal of both transfer repos; returns the ones that couldn't be deleted."""
        failed: List[str] = []
        for repo, kind in ((repos.dataset_repo, "dataset"), (repos.adapter_repo, "model")):
            try:
                self.api.delete_repo(repo_id=repo, repo_type=kind)
            except Exception as exc:  # noqa: BLE001
                if getattr(getattr(exc, "response", None), "status_code", None) == 404 or "404" in str(exc):
                    continue  # already gone
                logger.warning("Could not delete %s repo %s: %s", kind, repo, exc)
                failed.append(repo)
        return failed


def stage_training(transport, spec, bundle) -> RunRepos:
    """
    Upload everything a remote worker needs to a private dataset repo and return the repo names.
    Shared by the providers that can't share a filesystem with the app (RunPod, Modal).
    """
    import json

    dataset = Path(spec.dataset_path)
    repos = repo_names(transport.username(), spec.job_id)
    job = {
        "job_id": spec.job_id, "model_name": spec.model_name, "dataset_filename": dataset.name,
        "training_method": spec.training_method, "lora_config": spec.lora_config,
        "training_config": spec.training_config,
        "hf": {"dataset_repo": repos.dataset_repo, "adapter_repo": repos.adapter_repo},
    }
    transport.upload_run_assets(spec.job_id, {
        "bundle.tar.gz": bundle.data,
        "bundle.sha256": f"{bundle.sha256}  bundle.tar.gz\n".encode(),
        "job.json": json.dumps(job).encode("utf-8"),
        dataset.name: dataset.read_bytes(),
    })
    return repos
