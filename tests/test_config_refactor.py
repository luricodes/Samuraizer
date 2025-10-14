from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from samuraizer.config import ConfigurationManager, UnifiedConfigManager


@pytest.fixture
def unified_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[UnifiedConfigManager]:
    base = tmp_path / "config_env"
    monkeypatch.setenv("APPDATA", str(base / "appdata"))
    monkeypatch.setenv("HOME", str(base / "home"))

    UnifiedConfigManager._instance = None  # type: ignore[attr-defined]
    ConfigurationManager._instance = None  # type: ignore[attr-defined]

    manager = UnifiedConfigManager()
    config_file = base / "config" / "config.toml"
    manager.reload(config_path=config_file)

    try:
        yield manager
    finally:
        try:
            ConfigurationManager().cleanup()
        except Exception:
            pass
        UnifiedConfigManager._instance = None  # type: ignore[attr-defined]
        ConfigurationManager._instance = None  # type: ignore[attr-defined]


def test_unified_manager_roundtrip(unified_manager: UnifiedConfigManager) -> None:
    unified_manager.reload(profile="default")
    unified_manager.save()
    profiles = unified_manager.list_profiles()
    assert "default" in profiles

    config = unified_manager.get_active_profile_config()
    exclusions = config.get("exclusions", {})
    assert exclusions.get("folders", {}).get(
        "exclude"
    ), "Default folder exclusions missing"

    unified_manager.update_list("exclusions.folders.exclude", ["__tests__"])
    unified_manager.set_value("analysis.max_file_size_mb", 123)
    unified_manager.save()
    unified_manager.reload()

    updated = unified_manager.get_active_profile_config()
    folders = updated.get("exclusions", {}).get("folders", {}).get("exclude", [])
    assert "__tests__" in folders
    assert updated.get("analysis", {}).get("max_file_size_mb") == 123


def test_configuration_manager_profile_lifecycle(
    unified_manager: UnifiedConfigManager,
) -> None:
    cfg_mgr = ConfigurationManager()
    cfg_mgr.reload_configuration(config_path=str(unified_manager.config_path))
    baseline = cfg_mgr.get_active_profile_config()
    assert "analysis" in baseline

    profile_name = "pytest-profile"
    cfg_mgr.create_profile(profile_name, inherit="default")
    assert profile_name in cfg_mgr.list_profiles()

    cfg_mgr.delete_profile(profile_name)
    assert profile_name not in cfg_mgr.list_profiles()
    cfg_mgr.cleanup()
