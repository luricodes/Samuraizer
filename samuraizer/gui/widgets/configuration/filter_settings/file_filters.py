# samuraizer/gui/widgets/configuration/filter_settings/file_filters.py

"""Modernised file filter configuration widget.

This module provides a richer, more approachable experience for configuring
project-level filters. The design focuses on clear information hierarchy,
inline editing and instant feedback via a live preview tool.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from samuraizer.config import ConfigurationManager
from .filter_config_listener import FilterConfigListener

logger = logging.getLogger(__name__)


class EditableListWidget(QWidget):
    """A custom widget that displays an editable list with add/remove functionality."""

    itemsChanged = pyqtSignal()  # Signal emitted when items change

    def __init__(self, title: str, placeholder: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.placeholder = placeholder or f"Add {self.title.lower()}"
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Inline entry row for quick additions
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(self.placeholder)
        self.input_field.returnPressed.connect(self.add_item)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_item)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.add_btn)

        # List widget showing entries
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        # Footer actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.addStretch()

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_items)
        btn_layout.addWidget(self.remove_btn)

        layout.addLayout(input_layout)
        layout.addWidget(self.list_widget)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    def show_context_menu(self, position) -> None:
        """Show context menu for list items."""
        menu = QMenu()

        add_action = QAction("Quick add", self)
        add_action.triggered.connect(lambda: self.input_field.setFocus())
        menu.addAction(add_action)

        if self.list_widget.selectedItems():
            remove_action = QAction("Remove selected", self)
            remove_action.triggered.connect(self.remove_selected_items)
            menu.addAction(remove_action)

        menu.exec(self.list_widget.mapToGlobal(position))

    # ------------------------------------------------------------------
    def add_item(self) -> None:
        """Add a new item to the list."""
        text = self.input_field.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.input_field.clear()
            self.itemsChanged.emit()

    # ------------------------------------------------------------------
    def remove_selected_items(self) -> None:
        """Remove selected items from the list."""
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.itemsChanged.emit()

    # ------------------------------------------------------------------
    def get_items(self) -> set[str]:
        """Get all items as a set."""
        return {
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        }

    # ------------------------------------------------------------------
    def set_items(self, items: Iterable[str]) -> None:
        """Set the list items."""
        self.list_widget.clear()
        for item in sorted(set(items)):
            self.list_widget.addItem(item)

    # ------------------------------------------------------------------
    def add_single_item(self, item: str) -> None:
        """Add a single item to the list without using the input field."""
        if item:
            self.list_widget.addItem(item)
            self.itemsChanged.emit()

    # ------------------------------------------------------------------
    def remove_item(self, item: str) -> None:
        """Remove a specific item from the list."""
        if not item:
            return
        items = self.list_widget.findItems(item, Qt.MatchFlag.MatchExactly)
        for item_widget in items:
            self.list_widget.takeItem(self.list_widget.row(item_widget))
        if items:
            self.itemsChanged.emit()

    # ------------------------------------------------------------------
    # Backwards compatibility helpers for existing listener code
    def setItems(self, items: Iterable[str]) -> None:  # noqa: N802 (Qt naming compatibility)
        self.set_items(items)

    def addItem(self, item: str) -> None:  # noqa: N802
        self.add_single_item(item)

    def removeItem(self, item: str) -> None:  # noqa: N802
        self.remove_item(item)


class PatternListWidget(QWidget):
    """Widget for managing exclusion patterns."""

    patternsChanged = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Pattern input
        input_layout = QHBoxLayout()
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Enter glob or regex pattern (e.g., *.txt or regex:^test.*)")
        self.pattern_input.returnPressed.connect(self.add_pattern)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_pattern)

        input_layout.addWidget(self.pattern_input)
        input_layout.addWidget(self.add_btn)

        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.pattern_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pattern_list.customContextMenuRequested.connect(self.show_context_menu)

        # Remove button
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_patterns)

        # Help text
        help_text = QLabel(
            "Patterns can be glob patterns (*.txt) or regex patterns (regex:^test.*)\n"
            "Glob patterns are simpler and match against filenames only\n"
            "Regex patterns are more powerful and can match against full paths"
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("filtersPatternsHelp")

        # Add widgets to layout
        layout.addLayout(input_layout)
        layout.addWidget(self.pattern_list)
        layout.addWidget(self.remove_btn)
        layout.addWidget(help_text)

    # ------------------------------------------------------------------
    def show_context_menu(self, position) -> None:
        """Show context menu for pattern list."""
        menu = QMenu()

        add_action = QAction("Focus input", self)
        add_action.triggered.connect(lambda: self.pattern_input.setFocus())
        menu.addAction(add_action)

        if self.pattern_list.selectedItems():
            remove_action = QAction("Remove selected", self)
            remove_action.triggered.connect(self.remove_selected_patterns)
            menu.addAction(remove_action)

        menu.exec(self.pattern_list.mapToGlobal(position))

    # ------------------------------------------------------------------
    def add_pattern(self) -> None:
        """Add a new pattern to the list."""
        pattern = self.pattern_input.text().strip()
        if pattern:
            self.pattern_list.addItem(pattern)
            self.pattern_input.clear()
            self.patternsChanged.emit()

    # ------------------------------------------------------------------
    def remove_selected_patterns(self) -> None:
        """Remove selected patterns from the list."""
        for item in self.pattern_list.selectedItems():
            self.pattern_list.takeItem(self.pattern_list.row(item))
        self.patternsChanged.emit()

    # ------------------------------------------------------------------
    def get_patterns(self) -> list[str]:
        """Get all patterns as a list."""
        return [
            self.pattern_list.item(i).text()
            for i in range(self.pattern_list.count())
        ]

    # ------------------------------------------------------------------
    def set_patterns(self, patterns: Iterable[str]) -> None:
        """Set the pattern list."""
        self.pattern_list.clear()
        for pattern in patterns:
            self.pattern_list.addItem(pattern)

    # ------------------------------------------------------------------
    def add_single_pattern(self, pattern: str) -> None:
        """Add a single pattern without clearing input."""
        if pattern:
            self.pattern_list.addItem(pattern)
            self.patternsChanged.emit()

    # ------------------------------------------------------------------
    def remove_pattern(self, pattern: str) -> None:
        """Remove a specific pattern."""
        if not pattern:
            return
        items = self.pattern_list.findItems(pattern, Qt.MatchFlag.MatchExactly)
        for item in items:
            self.pattern_list.takeItem(self.pattern_list.row(item))
        if items:
            self.patternsChanged.emit()

    # ------------------------------------------------------------------
    # Backwards compatibility helpers
    def setPatterns(self, patterns: Iterable[str]) -> None:  # noqa: N802
        self.set_patterns(patterns)

    def addPattern(self, pattern: str) -> None:  # noqa: N802
        self.add_single_pattern(pattern)

    def removePattern(self, pattern: str) -> None:  # noqa: N802
        self.remove_pattern(pattern)


class SectionCard(QFrame):
    """Visual section wrapper that mimics a settings card."""

    def __init__(self, title: str, description: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("filtersSectionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 18, 16, 16)
        root_layout.setSpacing(12)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("filtersSectionTitle")
        header_layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("filtersSectionDescription")
            description_label.setWordWrap(True)
            header_layout.addWidget(description_label)

        root_layout.addLayout(header_layout)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        root_layout.addWidget(self._content_widget)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout


class FileFiltersWidget(QWidget):
    """Main widget for managing file and folder filters."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = ConfigurationManager()
        self.config_listener = FilterConfigListener(self)
        self._syncing_config = False
        self.config_manager.add_change_listener(self._handle_config_change)
        self.destroyed.connect(self._on_destroyed)
        self._setup_ui()
        self.load_settings()

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(18)

        intro_card = SectionCard(
            "Organise which files are part of the analysis",
            "Create exclusions for folders, files and patterns. These filters apply before an analysis starts, "
            "ensuring only relevant content is processed.",
        )

        self.summary_label = QLabel()
        self.summary_label.setObjectName("filtersSummaryLabel")
        self.summary_label.setWordWrap(True)
        intro_card.content_layout.addWidget(self.summary_label)

        preview_frame = QFrame()
        preview_frame.setObjectName("filtersPreviewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)

        preview_title = QLabel("Instant filter preview")
        preview_title.setObjectName("filtersPreviewTitle")
        preview_description = QLabel(
            "Test a path to see whether it will be included or skipped based on your current filters."
        )
        preview_description.setObjectName("filtersPreviewDescription")
        preview_description.setWordWrap(True)

        preview_input_row = QHBoxLayout()
        preview_input_row.setSpacing(6)

        self.preview_input = QLineEdit()
        self.preview_input.setPlaceholderText("Paste or type a file path to preview")
        self.preview_input.textChanged.connect(self._update_preview_status)
        preview_input_row.addWidget(self.preview_input)

        self.preview_browse_btn = QToolButton()
        self.preview_browse_btn.setText("Browse…")
        self.preview_browse_btn.setToolTip("Choose a file or folder to test against the current filters.")
        self.preview_browse_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.preview_browse_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        preview_browse_menu = QMenu(self.preview_browse_btn)
        file_action = preview_browse_menu.addAction("Select File…")
        file_action.triggered.connect(self._choose_preview_file)
        folder_action = preview_browse_menu.addAction("Select Folder…")
        folder_action.triggered.connect(self._choose_preview_folder)
        self.preview_browse_btn.setMenu(preview_browse_menu)
        self.preview_browse_btn.setDefaultAction(file_action)
        preview_input_row.addWidget(self.preview_browse_btn)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.preview_status_badge = QLabel("Waiting for input")
        self.preview_status_badge.setObjectName("filtersPreviewBadge")
        self.preview_status_badge.setProperty("state", "idle")
        self.preview_reason_label = QLabel("Enter a path to evaluate how filters apply.")
        self.preview_reason_label.setObjectName("filtersPreviewReason")
        self.preview_reason_label.setWordWrap(True)
        status_row.addWidget(self.preview_status_badge)
        status_row.addWidget(self.preview_reason_label, 1)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_description)
        preview_layout.addLayout(preview_input_row)
        preview_layout.addLayout(status_row)
        intro_card.content_layout.addWidget(preview_frame)

        content_layout.addWidget(intro_card)

        folders_card = SectionCard(
            "Excluded folders",
            "Any folder name listed here will be skipped recursively. Useful for build artefacts or vendor directories.",
        )
        self.folders_list = EditableListWidget("Folder", placeholder="Add folder name, e.g. build or node_modules")
        self.folders_list.itemsChanged.connect(self._on_filters_changed)
        folders_card.content_layout.addWidget(self.folders_list)
        content_layout.addWidget(folders_card)

        files_card = SectionCard(
            "Excluded files",
            "Add exact filenames that should never be analysed, regardless of location.",
        )
        self.files_list = EditableListWidget("File", placeholder="Add filename, e.g. package-lock.json")
        self.files_list.itemsChanged.connect(self._on_filters_changed)
        files_card.content_layout.addWidget(self.files_list)
        content_layout.addWidget(files_card)

        image_card = SectionCard(
            "Image extensions",
            "These file extensions will be treated as binary assets and omitted from textual analysis.",
        )
        self.image_list = EditableListWidget("Image Extension", placeholder="Add extension, e.g. .png")
        self.image_list.itemsChanged.connect(self._on_filters_changed)
        help_text = QLabel("File extensions to identify image files (include the leading dot).")
        help_text.setObjectName("filtersHelpLabel")
        help_text.setWordWrap(True)
        image_card.content_layout.addWidget(self.image_list)
        image_card.content_layout.addWidget(help_text)
        content_layout.addWidget(image_card)

        patterns_card = SectionCard(
            "Exclusion patterns",
            "Combine glob patterns (e.g. *.log) or regular expressions (prefix with regex:) for more advanced targeting.",
        )
        self.patterns_list = PatternListWidget()
        self.patterns_list.patternsChanged.connect(self._on_filters_changed)
        patterns_card.content_layout.addWidget(self.patterns_list)
        content_layout.addWidget(patterns_card)

        config_path = self.config_manager.exclusion_config.config_file
        config_label = QLabel(f"Configuration file: {config_path}")
        config_label.setObjectName("filtersConfigPath")
        config_label.setWordWrap(True)
        content_layout.addWidget(config_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_row.addWidget(self.reset_btn)
        content_layout.addLayout(button_row)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._apply_styles()

    # ------------------------------------------------------------------
    def load_settings(self) -> None:
        """Load settings from configuration manager."""
        if self._syncing_config:
            return
        self._syncing_config = True
        try:
            excluded_folders = self.config_manager.exclusion_config.get_excluded_folders()
            excluded_files = self.config_manager.exclusion_config.get_excluded_files()
            exclude_patterns = self.config_manager.exclusion_config.get_exclude_patterns()
            image_extensions = self.config_manager.exclusion_config.get_image_extensions()

            self.folders_list.set_items(excluded_folders)
            self.files_list.set_items(excluded_files)
            self.patterns_list.set_patterns(exclude_patterns)
            self.image_list.set_items(image_extensions)

            logger.info("Filter settings loaded successfully")
            self._update_summary()
            self._update_preview_status()

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error loading filter settings: %s", exc)
            self.show_error("Settings Error", f"Failed to load settings: {exc}")
        finally:
            self._syncing_config = False

    # ------------------------------------------------------------------
    def save_settings(self) -> None:
        """Save current settings through configuration manager."""
        if self._syncing_config:
            return
        self._syncing_config = True
        try:
            config_snapshot = self.get_configuration()
            self.config_manager.save_gui_filters(self)
            logger.debug("Filter settings saved to config file")

            self._update_summary(config_snapshot)
            self._update_preview_status(config_snapshot)

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error saving filter settings: %s", exc)
            self.show_error("Save Error", f"Failed to save settings: {exc}")
        finally:
            self._syncing_config = False

    # ------------------------------------------------------------------
    def reset_to_defaults(self) -> None:
        """Reset all filters to default values."""
        try:
            result = QMessageBox.question(
                self,
                "Reset to Defaults",
                "Are you sure you want to reset all filters to their default values?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if result == QMessageBox.StandardButton.Yes:
                self.config_manager.reset_to_defaults()
                self.load_settings()
                logger.info("Filters reset to defaults")
                QMessageBox.information(self, "Reset Complete", "Filters have been reset to default values.")

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error resetting to defaults: %s", exc)
            self.show_error("Reset Error", f"Failed to reset to defaults: {exc}")

    # ------------------------------------------------------------------
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current filter configuration."""
        return {
            "excluded_folders": list(self.folders_list.get_items()),
            "excluded_files": list(self.files_list.get_items()),
            "exclude_patterns": self.patterns_list.get_patterns(),
            "image_extensions": list(self.image_list.get_items()),
        }

    # ------------------------------------------------------------------
    def _handle_config_change(self) -> None:
        self.load_settings()

    def _on_destroyed(self, _obj=None) -> None:
        try:
            self.config_manager.remove_change_listener(self._handle_config_change)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error detaching filter listener: %s", exc)

    # ------------------------------------------------------------------
    def show_error(self, title: str, message: str) -> None:
        """Show an error message dialog."""
        QMessageBox.critical(self, title, message)

    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        """Apply visual styling for a modern appearance."""
        self.setStyleSheet(
            """
            QWidget#filtersSectionCard {
                background: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 14px;
            }
            QLabel#filtersSectionTitle {
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#filtersSectionDescription {
                color: palette(mid);
            }
            QLabel#filtersSummaryLabel {
                color: palette(dark);
            }
            QLabel#filtersHelpLabel,
            QLabel#filtersConfigPath,
            QLabel#filtersPreviewDescription,
            QLabel#filtersPreviewReason,
            QLabel#filtersPatternsHelp {
                color: palette(mid);
                font-size: 12px;
            }
            QFrame#filtersPreviewFrame {
                background: palette(alternate-base);
                border: 1px dashed palette(midlight);
                border-radius: 12px;
            }
            QLabel#filtersPreviewTitle {
                font-weight: 600;
            }
            QLabel#filtersPreviewBadge {
                padding: 4px 12px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 600;
                background: #e5e7eb;
                color: #374151;
            }
            QLabel#filtersPreviewBadge[state="included"] {
                background: #dcfce7;
                color: #166534;
            }
            QLabel#filtersPreviewBadge[state="excluded"] {
                background: #fee2e2;
                color: #991b1b;
            }
            QLabel#filtersPreviewBadge[state="idle"] {
                background: #e5e7eb;
                color: #6b7280;
            }
            QLineEdit,
            QListWidget {
                border: 1px solid palette(midlight);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QPushButton {
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: palette(alternate-base);
            }
            QPushButton:disabled {
                background: palette(base);
                color: palette(mid);
            }
            QToolButton {
                border-radius: 8px;
                padding: 6px 14px;
            }
            QToolButton:hover {
                background: palette(alternate-base);
            }
            QToolButton:disabled {
                background: palette(base);
                color: palette(mid);
            }
            """
        )

    # ------------------------------------------------------------------
    def _on_filters_changed(self) -> None:
        """Handle updates coming from any filter list widget."""
        self.save_settings()

    # ------------------------------------------------------------------
    def _update_summary(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Refresh the filter summary helper text."""
        config = config or self.get_configuration()
        folders = len(config.get("excluded_folders", []))
        files = len(config.get("excluded_files", []))
        patterns = len(config.get("exclude_patterns", []))
        images = len(config.get("image_extensions", []))

        summary = (
            f"<b>{folders}</b> folder{'s' if folders != 1 else ''} excluded · "
            f"<b>{files}</b> file{'s' if files != 1 else ''} excluded · "
            f"<b>{patterns}</b> pattern{'s' if patterns != 1 else ''} active · "
            f"<b>{images}</b> image extension{'s' if images != 1 else ''} tracked"
        )
        self.summary_label.setText(summary)

    # ------------------------------------------------------------------
    def _update_preview_status(self, payload: Any = None) -> None:
        """Evaluate the preview input and update status messaging."""
        if isinstance(payload, dict):
            config = payload
        else:
            config = self.get_configuration()
        path_text = self.preview_input.text().strip()
        if not path_text:
            self._set_preview_state("idle", "Waiting for input", "Enter a path to evaluate how filters apply.")
            return

        is_excluded, reason = self._evaluate_path_against_filters(path_text, config)
        if is_excluded:
            self._set_preview_state("excluded", "Excluded", reason)
        else:
            self._set_preview_state("included", "Included", reason)

    # ------------------------------------------------------------------
    def _set_preview_state(self, state: str, badge_text: str, message: str) -> None:
        """Update preview badge appearance and helper text."""
        self.preview_status_badge.setText(badge_text)
        self.preview_status_badge.setProperty("state", state)
        self.preview_reason_label.setText(message)

        for widget in (self.preview_status_badge, self.preview_reason_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    # ------------------------------------------------------------------
    def _preview_dialog_start_dir(self) -> str:
        """Infer a sensible starting directory for preview browsing."""
        text = self.preview_input.text().strip()
        if text:
            try:
                candidate = Path(text)
                if candidate.is_dir():
                    return str(candidate)
                if candidate.exists():
                    return str(candidate.parent)
                parent = candidate.parent
                if parent.exists():
                    return str(parent)
            except Exception:  # pragma: no cover - defensive
                logger.debug("Unable to infer preview start dir from input: %s", text)

        try:
            config_dir = Path(self.config_manager.exclusion_config.config_file).parent
            if config_dir.exists():
                return str(config_dir)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Unable to derive preview start dir from config file")

        return str(Path.cwd())

    # ------------------------------------------------------------------
    def _choose_preview_file(self) -> None:
        """Launch a file picker to populate the preview input."""
        start_dir = self._preview_dialog_start_dir()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Preview",
            start_dir,
            "All files (*.*)",
        )
        if file_path:
            self.preview_input.setText(file_path)

    # ------------------------------------------------------------------
    def _choose_preview_folder(self) -> None:
        """Launch a folder picker to populate the preview input."""
        start_dir = self._preview_dialog_start_dir()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Preview",
            start_dir,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.preview_input.setText(directory)

    # ------------------------------------------------------------------
    def _evaluate_path_against_filters(self, path_text: str, config: Dict[str, Any]) -> tuple[bool, str]:
        """Return whether the path is excluded and the reason why."""
        as_posix = path_text.replace("\\", "/")
        try:
            path_obj = Path(path_text)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            path_obj = Path(as_posix)

        parts = {part.lower() for part in path_obj.parts if part and part not in {"/", "\\"}}
        filename = path_obj.name.lower()
        folders = [item.lower() for item in config.get("excluded_folders", [])]
        files = [item.lower() for item in config.get("excluded_files", [])]
        patterns = config.get("exclude_patterns", [])
        image_exts = {item.lower() for item in config.get("image_extensions", [])}

        for folder in folders:
            if folder and folder in parts:
                return True, f"Matches excluded folder '{folder}'."

        if filename and filename in files:
            return True, f"Matches excluded filename '{filename}'."

        for pattern in patterns:
            if not pattern:
                continue
            if pattern.startswith("regex:"):
                regex = pattern[6:]
                try:
                    if re.search(regex, as_posix):
                        return True, f"Matches regex pattern '{regex}'."
                except re.error:
                    logger.warning("Invalid regex pattern ignored in preview: %s", pattern)
                    continue
            else:
                if fnmatch.fnmatch(as_posix, pattern) or fnmatch.fnmatch(filename, pattern):
                    return True, f"Matches glob pattern '{pattern}'."

        suffix = path_obj.suffix.lower()
        if suffix and suffix in image_exts:
            return True, f"Tagged as image asset via extension '{suffix}'."

        return False, "No exclusion matched. This path will be analysed."
