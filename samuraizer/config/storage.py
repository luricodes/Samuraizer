from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .compat import tomllib
from .exceptions import ConfigIOError
from .toml_io import _toml_dumps

logger = logging.getLogger(__name__)


class ConfigStorage:
    """Filesystem interaction for configuration persistence."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = (path or self._determine_default_path()).expanduser().resolve()

    @staticmethod
    def _determine_default_path() -> Path:
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
            return base / "samurai" / "config.toml"
        return Path.home() / ".config" / "samurai" / "config.toml"

    @property
    def path(self) -> Path:
        return self._path

    def set_path(self, new_path: Path) -> None:
        self._path = new_path.expanduser().resolve()

    def ensure_directory(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ConfigIOError(
                f"Unable to create configuration directory: {exc}"
            ) from exc

    def backup_existing_config(self, suffix: str = "backup") -> Optional[Path]:
        if not self._path.exists():
            return None
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_name = f"{self._path.name}.{suffix}.{timestamp}.bak"
        backup_path = self._path.with_name(backup_name)
        try:
            shutil.copy2(self._path, backup_path)
            return backup_path
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to create configuration backup at %s: %s", backup_path, exc
            )
            return None

    def write_config(self, data: Dict[str, Any]) -> None:
        self.ensure_directory()
        serialized = _toml_dumps(data)
        self._path.write_text(serialized, encoding="utf-8")

    def write_default(self, content: str) -> None:
        self.ensure_directory()
        self._path.write_text(content, encoding="utf-8")

    def read_config(self) -> Dict[str, Any]:
        self.ensure_directory()
        with self._path.open("rb") as fh:
            loaded = tomllib.load(fh)
        return loaded


__all__ = ["ConfigStorage"]
