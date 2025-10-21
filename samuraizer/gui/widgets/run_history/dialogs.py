"""Dialogs used by the run history dock."""
from __future__ import annotations

import difflib
from typing import Iterable, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .highlighters import DiffHighlighter
from .models import RunHistoryEntry, normalise_json


class ComparisonDialog(QDialog):
    """Dialog that provides a multi-tab comparison view for run history entries."""

    def __init__(self, reference: RunHistoryEntry, target: RunHistoryEntry, parent=None) -> None:
        super().__init__(parent)
        self.reference = reference
        self.target = target

        self.setWindowTitle("Run Comparison")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b>{reference.display_name}</b> ↔ <b>{target.display_name}</b>",
            self,
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)

        self._build_overview_tab()
        self._build_diff_tab()

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        export_button = QPushButton("Export Diff…")
        copy_button = QPushButton("Copy Diff")
        button_box.addButton(export_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.rejected.connect(self.reject)
        export_button.clicked.connect(self._export_diff)
        copy_button.clicked.connect(self._copy_diff)
        layout.addWidget(button_box)

    # ------------------------------------------------------------------
    def _build_overview_tab(self) -> None:
        table = QTableWidget(0, 3, self)
        table.setHorizontalHeaderLabels(["Metric", self.reference.display_name, self.target.display_name])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        overview_rows = self._overview_rows()
        for row_index, (label, left, right) in enumerate(overview_rows):
            table.insertRow(row_index)
            table.setItem(row_index, 0, QTableWidgetItem(label))
            table.setItem(row_index, 1, QTableWidgetItem(left))
            table.setItem(row_index, 2, QTableWidgetItem(right))

        table.resizeColumnsToContents()
        self.tabs.addTab(table, "Overview")

    def _build_diff_tab(self) -> None:
        diff_text = "\n".join(
            difflib.unified_diff(
                normalise_json(self.reference.results).splitlines(),
                normalise_json(self.target.results).splitlines(),
                fromfile=self.reference.display_name,
                tofile=self.target.display_name,
                lineterm="",
            )
        )

        if not diff_text.strip():
            diff_text = "No differences detected."

        self.diff_view = QPlainTextEdit(self)
        self.diff_view.setReadOnly(True)
        self.diff_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.diff_view.setPlainText(diff_text)
        DiffHighlighter(self.diff_view.document())
        self.tabs.addTab(self.diff_view, "Unified Diff")

    def _overview_rows(self) -> Iterable[Tuple[str, str, str]]:
        ref_metadata = self.reference.metadata_for_overview()
        tgt_metadata = self.target.metadata_for_overview()

        all_keys = sorted(set(ref_metadata) | set(tgt_metadata))
        for key in all_keys:
            yield (
                key,
                str(ref_metadata.get(key, "")),
                str(tgt_metadata.get(key, "")),
            )

        # add summary metrics
        ref_summary = self.reference.summary or {}
        tgt_summary = self.target.summary or {}
        summary_keys = sorted(set(ref_summary) | set(tgt_summary))
        for key in summary_keys:
            yield (
                f"Summary: {key}",
                str(ref_summary.get(key, "")),
                str(tgt_summary.get(key, "")),
            )

    def _export_diff(self) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diff",
            "run-comparison.diff",
            "Diff Files (*.diff *.patch);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(self.diff_view.toPlainText())
        except Exception as exc:  # pragma: no cover - filesystem interaction
            QMessageBox.critical(self, "Export Failed", f"Could not export diff:\n{exc}")
            return

        QMessageBox.information(self, "Export Complete", f"Diff exported to {file_path}")

    def _copy_diff(self) -> None:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        try:
            QApplication.clipboard().setText(self.diff_view.toPlainText())
        except Exception as exc:  # pragma: no cover - clipboard
            QMessageBox.warning(self, "Clipboard Error", f"Unable to copy diff:\n{exc}")
            return

        QMessageBox.information(self, "Diff Copied", "Diff copied to clipboard.")
