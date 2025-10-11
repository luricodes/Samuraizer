import logging
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
)

logger = logging.getLogger(__name__)


class DetailsPanel(QWidget):
    """Lightweight summary panel shown alongside analysis results."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._repository_path: str = ""
        self._current_summary: Dict[str, Any] = {}
        self._output_config: Dict[str, Any] = {}
        self._build_ui()
        self._apply_empty_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.title_label = QLabel("Analysis Summary")
        self.title_label.setObjectName("detailsPanelTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.title_label)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setObjectName("detailsPanelDescription")
        layout.addWidget(self.description_label)

        self.summary_group = QGroupBox("Overview")
        summary_layout = QFormLayout()
        summary_layout.setContentsMargins(12, 12, 12, 12)
        summary_layout.setSpacing(8)

        self.summary_labels: Dict[str, QLabel] = {}
        field_definitions = [
            ("repository_path", "Repository"),
            ("total_files", "Total files"),
            ("processed_files", "Processed files"),
            ("excluded_files", "Excluded files"),
            ("excluded_percentage", "Excluded %"),
            ("failed_files", "Failed files"),
            ("hash_algorithm", "Hash algorithm"),
            ("status", "Status"),
        ]

        for key, label in field_definitions:
            value_label = QLabel("—")
            value_label.setObjectName(f"details_{key}")
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            summary_layout.addRow(f"{label}:", value_label)
            self.summary_labels[key] = value_label

        self.summary_group.setLayout(summary_layout)
        layout.addWidget(self.summary_group)

        self.output_group = QGroupBox("Output configuration")
        output_layout = QFormLayout()
        output_layout.setContentsMargins(12, 12, 12, 12)
        output_layout.setSpacing(8)

        self.output_labels: Dict[str, QLabel] = {}
        output_fields = [
            ("format", "Format"),
            ("output_path", "Destination"),
            ("streaming", "Streaming"),
            ("include_summary", "Include summary"),
            ("pretty_print", "Pretty print"),
            ("use_compression", "Compression"),
        ]

        for key, label in output_fields:
            value_label = QLabel("-")
            value_label.setObjectName(f"details_output_{key}")
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            output_layout.addRow(f"{label}:", value_label)
            self.output_labels[key] = value_label

        self.output_group.setLayout(output_layout)
        layout.addWidget(self.output_group)

        self.failed_group = QGroupBox("Failed files")
        failed_layout = QVBoxLayout()
        failed_layout.setContentsMargins(12, 8, 12, 8)
        failed_layout.setSpacing(6)

        self.failed_list = QListWidget()
        self.failed_list.setAlternatingRowColors(True)
        self.failed_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.failed_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        failed_layout.addWidget(self.failed_list)

        self.failed_group.setLayout(failed_layout)
        layout.addWidget(self.failed_group)

        layout.addStretch(1)

    def set_configuration(self, config: Optional[Dict[str, Any]]) -> None:
        """Store the current configuration to show repository context."""
        try:
            if config:
                repo_cfg = config.get("repository", {})
                self._repository_path = repo_cfg.get("repository_path", "") or ""
                self._output_config = config.get("output", {}) or {}
            else:
                self._repository_path = ""
                self._output_config = {}
        except Exception as exc:
            logger.error("Failed to read repository configuration: %s", exc, exc_info=True)
            self._repository_path = ""
            self._output_config = {}

        self._update_repository_label()
        self._update_output_display()
        if not self._current_summary:
            self._apply_empty_state()

    def set_selection(self, selection_data: Optional[Dict[str, Any]]) -> None:
        """Update the panel with the latest analysis results."""
        summary = {}
        if isinstance(selection_data, dict):
            summary = selection_data.get("summary", {})

        if not summary:
            self._current_summary = {}
            self._apply_empty_state()
            return

        self._current_summary = summary
        self._update_summary_display()
        self._update_failed_files(summary.get("failed_files", []))
        self._update_output_display()

        self.description_label.setText("Overview of the latest analysis run.")
        self.summary_group.setVisible(True)

    def clear(self) -> None:
        """Reset the panel to its empty state."""
        self._current_summary = {}
        self._apply_empty_state()

    def _apply_empty_state(self) -> None:
        """Display helpful text when no results are available."""
        if self._repository_path:
            self.description_label.setText(
                f"Ready to analyse:\n{self._repository_path}"
            )
        else:
            self.description_label.setText(
                "Run an analysis to see repository statistics here."
            )

        for label in self.summary_labels.values():
            label.setText("-")

        # Keep repository path visible even without results
        self._update_repository_label()
        self._output_config = self._output_config or {}
        self._update_output_display()

        self.summary_group.setVisible(False)
        self.failed_group.setVisible(False)
        self.failed_list.clear()

    def _update_repository_label(self) -> None:
        label = self.summary_labels.get("repository_path")
        if label is not None:
            label.setText(self._repository_path or "—")

    def _update_summary_display(self) -> None:
        summary = self._current_summary

        def as_int(value: Any) -> str:
            try:
                return f"{int(value):,}"
            except (TypeError, ValueError):
                return "—"

        total_files = summary.get("total_files")
        processed_files = summary.get("processed_files", summary.get("included_files"))
        excluded_files = summary.get("excluded_files")
        excluded_percentage = summary.get("excluded_percentage")
        failed_entries: List[Dict[str, Any]] = summary.get("failed_files", []) or []
        hash_algorithm = summary.get("hash_algorithm")
        stopped_early = summary.get("stopped_early", False)

        self.summary_labels["repository_path"].setText(
            self._repository_path or "—"
        )
        self.summary_labels["total_files"].setText(as_int(total_files))
        self.summary_labels["processed_files"].setText(as_int(processed_files))
        self.summary_labels["excluded_files"].setText(as_int(excluded_files))

        if excluded_percentage is not None:
            try:
                self.summary_labels["excluded_percentage"].setText(
                    f"{excluded_percentage:.1f}%"
                )
            except (TypeError, ValueError):
                self.summary_labels["excluded_percentage"].setText("—")
        else:
            self.summary_labels["excluded_percentage"].setText("—")

        self.summary_labels["failed_files"].setText(str(len(failed_entries)))
        self.summary_labels["hash_algorithm"].setText(hash_algorithm or "—")
        self.summary_labels["status"].setText(
            "Stopped early" if stopped_early else "Completed"
        )

    def _update_failed_files(self, failed_files: List[Dict[str, Any]]) -> None:
        self.failed_list.clear()
        if not failed_files:
            self.failed_group.setVisible(False)
            return

        for entry in failed_files:
            path = entry.get("file", "Unknown file")
            error = entry.get("error", "Unknown error")
            text = f"{path}\n  {error}"
            item = QListWidgetItem(text)
            item.setToolTip(f"{path}\n{error}")
            self.failed_list.addItem(item)

        self.failed_group.setVisible(True)

    def _update_output_display(self) -> None:
        if not getattr(self, "output_labels", None):
            return

        config = self._output_config or {}
        if not config:
            for label in self.output_labels.values():
                label.setText("-")
            self.output_group.setVisible(False)
            return

        def as_bool_text(value: Any) -> str:
            return "Enabled" if bool(value) else "Disabled"

        format_value = config.get("format") or "-"
        if format_value not in {"", "-"}:
            format_value = str(format_value).upper()
        else:
            format_value = "-"

        destination = config.get("output_path") or "-"
        streaming = config.get("streaming", False)
        include_summary = config.get("include_summary", False)
        pretty_print = config.get("pretty_print", False)
        compression = config.get("use_compression", False)

        self.output_labels["format"].setText(format_value)
        self.output_labels["output_path"].setText(destination if destination.strip() else "-")
        self.output_labels["streaming"].setText(as_bool_text(streaming))
        self.output_labels["include_summary"].setText(as_bool_text(include_summary))
        self.output_labels["pretty_print"].setText(as_bool_text(pretty_print))
        self.output_labels["use_compression"].setText(as_bool_text(compression))

        self.output_group.setVisible(True)
