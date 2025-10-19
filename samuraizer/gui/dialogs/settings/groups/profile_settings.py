from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QSettings

from samuraizer.config import ConfigError, ConfigValidationError
from samuraizer.gui.widgets.configuration.output_settings.path_utils import (
    DEFAULT_BASENAME,
    derive_default_output_path,
    extension_for_format,
    normalise_output_path,
    sanitize_filename,
    validate_output_path as is_valid_output_path,
)
from ..base import BaseSettingsGroup

logger = logging.getLogger(__name__)


class ProfileSettingsGroup(BaseSettingsGroup):
    """Profile management UI backed by the unified configuration manager."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Configuration Profiles", parent)
        self.setObjectName("profileSettingsGroup")

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(6)

        label = QLabel("Active profile:")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.profile_combo = QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)

        selector_layout.addWidget(label)
        selector_layout.addWidget(self.profile_combo, stretch=1)
        layout.addLayout(selector_layout)

        self.config_path_label = QLabel()
        self.config_path_label.setObjectName("profileConfigPath")
        self.config_path_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.config_path_label)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: palette(dark);")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._create_profile)
        buttons_row.addWidget(self.new_button)

        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self._duplicate_profile)
        buttons_row.addWidget(self.duplicate_button)

        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self._rename_profile)
        buttons_row.addWidget(self.rename_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_profile)
        buttons_row.addWidget(self.delete_button)

        layout.addLayout(buttons_row)

        import_row = QHBoxLayout()
        import_row.setSpacing(6)

        self.import_button = QPushButton("Import…")
        self.import_button.clicked.connect(self._import_profile)
        import_row.addWidget(self.import_button)

        self.export_button = QPushButton("Export…")
        self.export_button.clicked.connect(self._export_profile)
        import_row.addWidget(self.export_button)

        layout.addLayout(import_row)
        layout.addStretch()

        self._refresh_profiles()

    # ------------------------------------------------------------------ #
    # Lifecycle hooks
    # ------------------------------------------------------------------ #

    def load_settings(self) -> None:
        self._refresh_profiles()

    def save_settings(self) -> None:  # pragma: no cover - managed instantly
        """Profiles are persisted immediately upon modification."""

    def validate(self) -> bool:
        return True

    def on_config_changed(self) -> None:
        self._refresh_profiles()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _refresh_profiles(self) -> None:
        with self.suspend_config_updates():
            active = self.config_manager.active_profile
            profiles = self.config_manager.list_profiles()

            current_selection = self.profile_combo.currentText()
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItems(profiles)
            index = self.profile_combo.findText(active, Qt.MatchFlag.MatchExactly)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
            else:
                self.profile_combo.setCurrentText(active)
            self.profile_combo.blockSignals(False)

            config_path = str(self.config_manager.config_path)
            self.config_path_label.setText(f"Configuration file: {config_path}")

            self.delete_button.setEnabled(active != "default")
            self.rename_button.setEnabled(active != "default")
            self.duplicate_button.setEnabled(bool(profiles))

            self.error_label.hide()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        logger.error(message)

    def _prompt_for_name(
        self,
        title: str,
        label: str,
        default: str = "",
    ) -> Optional[str]:
        text, ok = QInputDialog.getText(self, title, label, text=default)
        if not ok:
            return None
        name = text.strip()
        if not name:
            self._show_error("Profile name cannot be empty.")
            return None
        if name.lower() == "default":
            self._show_error("Profile name 'default' is reserved.")
            return None
        return name

    def _seed_profile_output_path(self, profile: str) -> None:
        try:
            resolved = self.config_manager.resolve_profile(profile).config
        except ConfigError as exc:
            logger.debug(
                "Unable to resolve profile '%s' for output path seeding: %s",
                profile,
                exc,
            )
            return

        output_cfg = resolved.get("output", {})
        if output_cfg.get("path"):
            return

        analysis_cfg = resolved.get("analysis", {})
        repository_path = self._current_repository_path()
        filename = DEFAULT_BASENAME
        if repository_path:
            try:
                filename = sanitize_filename(Path(repository_path).name)
            except Exception:  # pragma: no cover - defensive
                filename = DEFAULT_BASENAME

        extension = extension_for_format(analysis_cfg.get("default_format"))
        candidate_path = derive_default_output_path(repository_path, filename, extension)
        if not candidate_path:
            return

        try:
            candidate_path = normalise_output_path(candidate_path)
        except Exception:  # pragma: no cover - defensive
            pass

        if not is_valid_output_path(candidate_path):
            logger.debug(
                "Skipping output path seed for profile '%s' because '%s' is not writable",
                profile,
                candidate_path,
            )
            return

        try:
            self.config_manager.set_values_batch(
                {"output.path": candidate_path},
                profile=profile,
                notify=False,
            )
        except ConfigError as exc:
            logger.debug(
                "Unable to persist default output path for profile '%s': %s",
                profile,
                exc,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "Unexpected error while seeding output path for profile '%s': %s",
                profile,
                exc,
            )

    @staticmethod
    def _current_repository_path() -> Optional[str]:
        settings = QSettings()
        repo_value = settings.value("analysis/last_repository", "")
        repo_text = str(repo_value or "").strip()
        return repo_text or None

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_profile_selected(self, profile: str) -> None:
        if not profile:
            return
        with self.suspend_config_updates():
            try:
                self.config_manager.set_active_profile(profile)
                self.error_label.hide()
            except ConfigError as exc:
                self._show_error(f"Failed to activate profile: {exc}")

    def _create_profile(self) -> None:
        inherit = self.profile_combo.currentText() or "default"
        suggested = f"{inherit}-profile" if inherit != "default" else "new-profile"
        name = self._prompt_for_name("Create Profile", "New profile name:", default=suggested)
        if not name:
            return
        try:
            self.config_manager.create_profile(name, inherit=inherit)
            self._seed_profile_output_path(name)
            self.config_manager.set_active_profile(name)
            self._refresh_profiles()
        except ConfigError as exc:
            self._show_error(str(exc))

    def _duplicate_profile(self) -> None:
        source = self.profile_combo.currentText() or "default"
        name = self._prompt_for_name(
            "Duplicate Profile",
            f"Name for duplicate of '{source}':",
            default=f"{source}-copy",
        )
        if not name:
            return
        try:
            self.config_manager.create_profile(name, inherit=source)
            self.config_manager.set_active_profile(name)
            self._refresh_profiles()
        except ConfigError as exc:
            self._show_error(str(exc))

    def _rename_profile(self) -> None:
        current = self.profile_combo.currentText()
        if not current or current == "default":
            return
        name = self._prompt_for_name("Rename Profile", "New profile name:", default=current)
        if not name or name == current:
            return
        try:
            self.config_manager.rename_profile(current, name)
            self.config_manager.set_active_profile(name)
            self._refresh_profiles()
        except ConfigError as exc:
            self._show_error(str(exc))

    def _delete_profile(self) -> None:
        target = self.profile_combo.currentText()
        if not target or target == "default":
            return
        response = QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to delete the profile '{target}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            self.config_manager.remove_profile(target)
            self._refresh_profiles()
        except ConfigError as exc:
            self._show_error(str(exc))

    def _export_profile(self) -> None:
        profile = self.profile_combo.currentText() or "default"
        suggested_name = f"{profile}.toml"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile",
            str(Path.home() / suggested_name),
            "TOML Files (*.toml);;All Files (*.*)",
        )
        if not path:
            return
        try:
            toml_payload = self.config_manager.export_profile_as_toml(profile)
            Path(path).write_text(toml_payload, encoding="utf-8")
            self.error_label.hide()
        except (OSError, ConfigError) as exc:
            self._show_error(f"Failed to export profile: {exc}")

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profile",
            str(Path.home()),
            "TOML Files (*.toml);;All Files (*.*)",
        )
        if not path:
            return
        name = self._prompt_for_name("Import Profile", "Profile name:")
        if not name:
            return
        inherit = self.profile_combo.currentText() or "default"
        try:
            content = Path(path).read_text(encoding="utf-8")
            self.config_manager.import_profile_from_toml(name, content, inherit=inherit)
            self.config_manager.set_active_profile(name)
            self._refresh_profiles()
        except (OSError, ConfigError, ConfigValidationError) as exc:
            self._show_error(f"Failed to import profile: {exc}")
