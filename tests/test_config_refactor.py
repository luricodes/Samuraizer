from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from samuraizer.config import UnifiedConfigManager


@pytest.fixture
def unified_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[UnifiedConfigManager]:
    base = tmp_path / "config_env"
    monkeypatch.setenv("APPDATA", str(base / "appdata"))
    monkeypatch.setenv("HOME", str(base / "home"))

    UnifiedConfigManager._instance = None  # type: ignore[attr-defined]
    manager = UnifiedConfigManager()
    config_file = base / "config" / "config.toml"
    manager.reload(config_path=config_file)

    try:
        yield manager
    finally:
        manager.cleanup()


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


def test_unified_manager_profile_lifecycle(
    unified_manager: UnifiedConfigManager,
) -> None:
    baseline = unified_manager.get_active_profile_config()
    assert "analysis" in baseline

    profile_name = "pytest-profile"
    unified_manager.create_profile(profile_name, inherit="default")
    assert profile_name in unified_manager.list_profiles()

    unified_manager.remove_profile(profile_name)
    assert profile_name not in unified_manager.list_profiles()


def test_batch_updates_reduce_notifications(
    unified_manager: UnifiedConfigManager,
) -> None:
    events = 0

    def listener() -> None:
        nonlocal events
        events += 1

    unified_manager.add_change_listener(listener)

    unified_manager.set_values_batch(
        {
            "analysis.include_summary": False,
            "output.streaming": True,
        }
    )
    assert events == 1

    events = 0
    unified_manager.set_values_batch(
        {
            "analysis.include_summary": False,
            "output.streaming": True,
        }
    )
    assert events == 0
