import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from .path_utils import DEFAULT_BASENAME, sanitize_filename, extension_for_format

logger = logging.getLogger(__name__)


class OutputFileGroup(QGroupBox):
    """Collects and previews output destination information."""

    outputPathChanged = pyqtSignal(str)

    def __init__(self, settings_manager, get_file_extension_callback, parent=None):
        super().__init__("Output Destination", parent)
        self.settings_manager = settings_manager
        self.get_file_extension = get_file_extension_callback

        self._current_format: str = "json"
        self._current_extension: str = ".json"
        self._current_path: str = ""
        self._repository_path: str = ""
        self._repository_name: str = DEFAULT_BASENAME
        self._timestamp_fragment: Optional[str] = None
        self._auto_directory: bool = True
        self._auto_filename: bool = True
        self._loading: bool = False
        self._path_source: str = "default"

        self._build_ui()
        self.set_path_source("default")

    # ------------------------------------------------------------------ #
    # UI creation
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QFormLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # Directory selector
        directory_row = QHBoxLayout()
        directory_row.setSpacing(6)

        self.directory_edit = QLineEdit()
        self.directory_edit.setPlaceholderText("Select the folder where the export should be written...")
        self.directory_edit.textChanged.connect(self._on_directory_changed)
        self.directory_edit.textEdited.connect(self._mark_directory_overridden)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_for_directory)
        browse_btn.setMaximumWidth(100)

        self.use_repo_button = QPushButton("Use repo")
        self.use_repo_button.setToolTip("Use the active repository folder")
        self.use_repo_button.setEnabled(False)
        self.use_repo_button.clicked.connect(self._use_repository_directory)
        self.use_repo_button.setMaximumWidth(100)

        directory_row.addWidget(self.directory_edit)
        directory_row.addWidget(browse_btn)
        directory_row.addWidget(self.use_repo_button)
        layout.addRow("Directory", self._wrap_row(directory_row))

        # File naming options
        filename_row = QHBoxLayout()
        filename_row.setSpacing(6)

        self.naming_template = QComboBox()
        self.naming_template.addItem("Repository name", userData="repo")
        self.naming_template.addItem("Repository + timestamp", userData="repo_timestamp")
        self.naming_template.addItem("Format + timestamp", userData="format_timestamp")
        self.naming_template.addItem("Custom name", userData="custom")
        self.naming_template.currentIndexChanged.connect(self._on_template_changed)

        self.custom_name_edit = QLineEdit()
        self.custom_name_edit.setPlaceholderText("analysis-report")
        self.custom_name_edit.setEnabled(False)
        self.custom_name_edit.textChanged.connect(self._on_custom_name_changed)
        self.custom_name_edit.textEdited.connect(self._mark_filename_overridden)

        self.refresh_template_btn = QPushButton("Refresh")
        self.refresh_template_btn.setToolTip("Generate a fresh timestamp")
        self.refresh_template_btn.setFixedWidth(80)
        self.refresh_template_btn.clicked.connect(self._refresh_timestamp)
        self.refresh_template_btn.setVisible(False)

        filename_row.addWidget(self.naming_template, stretch=2)
        filename_row.addWidget(self.custom_name_edit, stretch=3)
        filename_row.addWidget(self.refresh_template_btn)
        layout.addRow("File name", self._wrap_row(filename_row))

        naming_hint = QLabel("Samuraizer will automatically append the correct extension for the selected format.")
        naming_hint.setWordWrap(True)
        naming_hint.setStyleSheet("color: palette(Mid);")
        layout.addRow("", naming_hint)

        # Final path preview
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("outputPreviewFrame")
        preview_layout = QHBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(8, 6, 8, 6)
        preview_layout.setSpacing(4)

        self.preview_label = QLabel("Select a directory to preview the full output path.")
        self.preview_label.setObjectName("outputPreviewLabel")
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        preview_layout.addWidget(self.preview_label)
        layout.addRow("Final path", self.preview_frame)

        self.preview_frame.setStyleSheet(
            """
            #outputPreviewFrame {
                border-radius: 6px;
                border: 1px solid palette(Midlight);
                background-color: palette(AlternateBase);
            }
            #outputPreviewLabel {
                font-weight: 500;
            }
            """
        )

        self.setLayout(layout)
        # Ensure the controls reflect the initial template selection
        self._on_template_changed(self.naming_template.currentIndex())

    @staticmethod
    def _wrap_row(layout: QHBoxLayout) -> QWidget:
        container = QWidget()
        container.setLayout(layout)
        return container

    # ------------------------------------------------------------------ #
    # Repository context & defaults
    # ------------------------------------------------------------------ #
    def apply_repository_defaults(self, repository_path: str) -> None:
        repository_path = repository_path.strip()
        self._repository_path = repository_path
        self.use_repo_button.setEnabled(bool(repository_path))

        if repository_path:
            repo_name = Path(repository_path).name
            self._repository_name = sanitize_filename(repo_name)
        else:
            self._repository_name = DEFAULT_BASENAME

        if repository_path and (self._auto_directory or not self.directory_edit.text().strip()):
            self._auto_directory = True
            self.directory_edit.setText(repository_path)

        if self.naming_template.currentData() == "custom":
            if not self.custom_name_edit.text().strip():
                self.custom_name_edit.setText(self._repository_name)
        else:
            # Refresh generated file name if using automatic templates
            self._auto_filename = True
            if self._uses_timestamp(self.naming_template.currentData()):
                self._ensure_timestamp()

        self._update_preview()
        if repository_path:
            self.set_path_source("repository")

    # ------------------------------------------------------------------ #
    # Slots and helpers
    # ------------------------------------------------------------------ #
    def _on_directory_changed(self, _value: str) -> None:
        self._update_preview()

    def _mark_directory_overridden(self, _value: str) -> None:
        self._auto_directory = False
        self.set_path_source("custom")

    def _on_template_changed(self, _index: int) -> None:
        template_key = self.naming_template.currentData()
        uses_timestamp = self._uses_timestamp(template_key)
        self.refresh_template_btn.setVisible(uses_timestamp)

        if template_key == "custom":
            self.custom_name_edit.setEnabled(True)
            if not self.custom_name_edit.text().strip():
                self.custom_name_edit.setText(self._repository_name)
            self._auto_filename = False
        else:
            self.custom_name_edit.setEnabled(False)
            self._auto_filename = True
            if uses_timestamp:
                self._ensure_timestamp()

        self._update_preview()

    def _on_custom_name_changed(self, _value: str) -> None:
        self._update_preview()

    def _mark_filename_overridden(self, _value: str) -> None:
        self._auto_filename = False
        self.set_path_source("custom")

    def _browse_for_directory(self) -> None:
        start_dir = self.directory_edit.text().strip() or self._repository_path or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if directory:
            self.directory_edit.setText(directory)
            self._auto_directory = False
            self.set_path_source("custom")

    def _use_repository_directory(self) -> None:
        if not self._repository_path:
            return
        self.directory_edit.setText(self._repository_path)
        self._auto_directory = True
        self.set_path_source("repository")

    def _refresh_timestamp(self) -> None:
        self._timestamp_fragment = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._update_preview()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_format(self, format_name: str) -> None:
        if not format_name or format_name == "Choose Output Format":
            format_key = self._current_format
        else:
            format_key = format_name.lower()

        self._current_format = format_key
        extension = extension_for_format(format_key)
        if not extension.startswith("."):
            extension = f".{extension}"
        self._current_extension = extension

        if self._uses_timestamp(self.naming_template.currentData()):
            self._ensure_timestamp()

        self._update_preview()

    def load_settings(self) -> None:
        try:
            self._loading = True

            saved_directory = self.settings_manager.load_setting("output/directory", "")
            saved_template = self.settings_manager.load_setting("output/naming_template", "repo")
            saved_custom_name = self.settings_manager.load_setting("output/custom_name", "")

            if saved_directory:
                self.directory_edit.setText(saved_directory)
                self._auto_directory = False
            else:
                legacy_path = self.settings_manager.load_setting("output/last_path", "")
                if legacy_path:
                    legacy_path_obj = Path(legacy_path)
                    self.directory_edit.setText(str(legacy_path_obj.parent))
                    saved_template = "custom"
                    saved_custom_name = legacy_path_obj.stem
                    self._auto_directory = False

            index = self.naming_template.findData(saved_template)
            if index == -1:
                index = 0
            self.naming_template.setCurrentIndex(index)

            if saved_template == "custom" and saved_custom_name:
                self.custom_name_edit.setText(saved_custom_name)
                self._auto_filename = False

        except Exception as exc:
            logger.error("Failed to load output settings: %s", exc, exc_info=True)
        finally:
            self._loading = False
            self._update_preview()

    def save_settings(self, settings_manager) -> None:
        try:
            settings_manager.save_setting("output/directory", self.directory_edit.text().strip())
            settings_manager.save_setting("output/naming_template", self.naming_template.currentData())
            settings_manager.save_setting("output/custom_name", self.custom_name_edit.text().strip())
            settings_manager.save_setting("output/last_path", self._current_path)
        except Exception as exc:
            logger.error("Failed to save output settings: %s", exc, exc_info=True)

    def get_output_path(self) -> str:
        return self._current_path

    def set_output_path(self, full_path: str) -> None:
        """Update the UI to reflect a concrete output path."""
        self._loading = True
        try:
            if not full_path:
                self.directory_edit.blockSignals(True)
                self.directory_edit.clear()
                self.directory_edit.blockSignals(False)
                custom_index = self.naming_template.findData("custom")
                if custom_index >= 0:
                    self.naming_template.blockSignals(True)
                    self.naming_template.setCurrentIndex(custom_index)
                    self.naming_template.blockSignals(False)
                self.custom_name_edit.blockSignals(True)
                self.custom_name_edit.clear()
                self.custom_name_edit.blockSignals(False)
                self._current_path = ""
                return

            path_obj = Path(full_path)
            directory = str(path_obj.parent)
            stem = path_obj.stem or sanitize_filename(path_obj.name)
            extension = path_obj.suffix or self._current_extension or ".json"

            self.directory_edit.blockSignals(True)
            self.directory_edit.setText(directory)
            self.directory_edit.blockSignals(False)
            self._auto_directory = False

            custom_index = self.naming_template.findData("custom")
            if custom_index < 0:
                custom_index = 0
            self.naming_template.blockSignals(True)
            self.naming_template.setCurrentIndex(custom_index)
            self.naming_template.blockSignals(False)

            self.custom_name_edit.blockSignals(True)
            self.custom_name_edit.setText(stem)
            self.custom_name_edit.blockSignals(False)
            self._auto_filename = False

            if extension:
                if not extension.startswith("."):
                    extension = f".{extension}"
                self._current_extension = extension

            self._current_path = str(path_obj.with_suffix(self._current_extension))
        except Exception as exc:
            logger.error("Failed to set output path from profile: %s", exc, exc_info=True)
        finally:
            try:
                self._update_preview()
            finally:
                self._loading = False

    def set_path_source(self, source: str) -> None:
        """Annotate the preview with context about the active path."""
        self._path_source = source
        if source == "profile":
            tooltip = "Output path provided by the active profile."
            style = "font-weight: 600;"
        elif source == "custom":
            tooltip = "Output path customised for this session."
            style = "font-weight: 500;"
        elif source == "repository":
            tooltip = "Output path derived from the active repository."
            style = "font-weight: 500;"
        else:
            tooltip = "Output path derived from default settings."
            style = "font-style: italic; font-weight: 500;"
        self.preview_frame.setToolTip(tooltip)
        self.preview_label.setStyleSheet(style)

    def get_path_source(self) -> str:
        return self._path_source

    def get_repository_path(self) -> str:
        return self._repository_path

    def get_current_extension(self) -> str:
        return self._current_extension or ".json"

    def get_preview_filename(self) -> str:
        return self._generate_filename()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_timestamp(self) -> None:
        if not self._timestamp_fragment:
            self._timestamp_fragment = datetime.now().strftime("%Y%m%d-%H%M%S")

    def _uses_timestamp(self, template_key: Optional[str]) -> bool:
        return template_key in {"repo_timestamp", "format_timestamp"}

    def _generate_filename(self) -> str:
        template_key = self.naming_template.currentData()
        repo_name = self._repository_name or DEFAULT_BASENAME
        format_base = sanitize_filename(self._current_format)

        if template_key == "repo":
            return repo_name

        if template_key == "repo_timestamp":
            self._ensure_timestamp()
            return f"{repo_name}_{self._timestamp_fragment}"

        if template_key == "format_timestamp":
            self._ensure_timestamp()
            return f"{format_base}_{self._timestamp_fragment}"

        custom_value = self.custom_name_edit.text().strip()
        return sanitize_filename(custom_value) or repo_name

    def _update_preview(self) -> None:
        filename = self._generate_filename()
        directory_text = self.directory_edit.text().strip()

        if directory_text:
            final_path = (Path(directory_text) / filename).with_suffix(self._current_extension)
            self._current_path = str(final_path)
            preview_text = self._current_path
        else:
            final_name = Path(filename).with_suffix(self._current_extension)
            preview_text = f"{final_name} (select a directory)"
            self._current_path = ""

        self.preview_label.setText(preview_text)

        if not self._loading:
            self.outputPathChanged.emit(self._current_path)

        
