"""Syntax highlighters used by run history widgets."""
from __future__ import annotations

from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class DiffHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for unified diff text."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._add_format = QTextCharFormat()
        self._add_format.setForeground(QColor("#22863a"))
        self._remove_format = QTextCharFormat()
        self._remove_format.setForeground(QColor("#b31d28"))
        self._header_format = QTextCharFormat()
        self._header_format.setForeground(QColor("#0366d6"))
        self._meta_format = QTextCharFormat()
        self._meta_format.setForeground(QColor("#6a737d"))

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        if not text:
            return
        if text.startswith("+++") or text.startswith("---"):
            self.setFormat(0, len(text), self._header_format)
        elif text.startswith("@@"):
            self.setFormat(0, len(text), self._meta_format)
        elif text.startswith("+"):
            self.setFormat(0, len(text), self._add_format)
        elif text.startswith("-"):
            self.setFormat(0, len(text), self._remove_format)
