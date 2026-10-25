from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

APP_NAME = "CraftML Studio"
ENV_VAR_ENV = "CRAFTML_ENV"
ENV_VAR_USER_DATA = "CRAFTML_USER_DATA_DIR"


def _project_root() -> Path:
    """Return repository root even when frozen."""
    # In a PyInstaller bundle, sys._MEIPASS is the bundle's data directory (_internal).
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def _platform_appdata_dir() -> Path:
    """Resolve platform-specific writable app data directory."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def _resolve_user_data_dir(env: str, is_frozen: bool) -> Path:
    """Compute the base user-data directory."""
    override = os.environ.get(ENV_VAR_USER_DATA)
    if override:
        return Path(override).expanduser().resolve()

    if env == "prod" or is_frozen:
        return _platform_appdata_dir() / APP_NAME

    # Development default mirrors other components that currently reference ~/.craftml
    return Path.home() / ".craftml"


@dataclass(slots=True)
class Settings:
    """Shared configuration used by backend services and the desktop bundle."""

    env: str
    root_dir: Path
    user_data_dir: Path
    resources_root: Path
    models_dir: Path
    datasets_dir: Path
    logs_dir: Path
    bundled_resources_dir: Path
    is_frozen: bool

    @classmethod
    def create(cls) -> "Settings":
        env = os.environ.get(ENV_VAR_ENV, "dev").strip().lower()
        is_frozen = bool(getattr(sys, "frozen", False))
        root_dir = _project_root()

        user_data_dir = _resolve_user_data_dir(env, is_frozen)
        resources_root = user_data_dir / "resources"
        models_dir = user_data_dir / "models"
        datasets_dir = user_data_dir / "datasets"
        logs_dir = user_data_dir / "logs"

        if bundle_root := getattr(sys, "_MEIPASS", None):
            bundled_resources_dir = Path(bundle_root) / "resources"
        else:
            bundled_resources_dir = root_dir / "resources"

        settings = cls(
            env=env,
            root_dir=root_dir,
            user_data_dir=user_data_dir,
            resources_root=resources_root,
            models_dir=models_dir,
            datasets_dir=datasets_dir,
            logs_dir=logs_dir,
            bundled_resources_dir=bundled_resources_dir,
            is_frozen=is_frozen,
        )
        settings._ensure_directories()
        return settings

    def _ensure_directories(self) -> None:
        writable_dirs: Iterable[Path] = (
            self.user_data_dir,
            self.resources_root,
            self.models_dir,
            self.datasets_dir,
            self.logs_dir,
        )
        for path in writable_dirs:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings.create()

