"""Central management for run history entries."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import uuid
from typing import Dict, Iterable, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ....widgets.run_history import RunHistoryEntry


class RunHistoryManager(QObject):
    """Keeps track of analysis runs and coordinates UI updates."""

    entryAdded = pyqtSignal(RunHistoryEntry)
    comparisonRequested = pyqtSignal(RunHistoryEntry, RunHistoryEntry)
    comparisonUnavailable = pyqtSignal(str)
    openRequested = pyqtSignal(RunHistoryEntry)
    activeEntryChanged = pyqtSignal(Optional[str])

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: Dict[str, RunHistoryEntry] = {}
        self._order: List[str] = []
        self._active_entry_id: Optional[str] = None

    # ------------------------------------------------------------------
    def add_entry(self, entry: RunHistoryEntry) -> None:
        if entry.identifier in self._entries:
            self._entries[entry.identifier] = entry
            self.entryAdded.emit(entry)
            # Keep original order for updated entries
        else:
            self._entries[entry.identifier] = entry
            self._order.append(entry.identifier)
            self.entryAdded.emit(entry)
        self.set_active_entry(entry.identifier)

    def create_entry(
        self,
        display_name: str,
        repository: str,
        preset: str,
        output_format: str,
        configuration: Dict[str, object],
        summary: Dict[str, object],
        results: Dict[str, object],
        duration: Optional[float] = None,
        processed_files: Optional[int] = None,
    ) -> RunHistoryEntry:
        entry = RunHistoryEntry(
            identifier=str(uuid.uuid4()),
            display_name=display_name,
            timestamp=datetime.now(),
            repository=repository,
            preset=preset,
            output_format=output_format,
            duration_seconds=duration,
            processed_files=processed_files,
            configuration=deepcopy(configuration),
            summary=deepcopy(summary or {}),
            results=deepcopy(results or {}),
        )
        self.add_entry(entry)
        return entry

    def get_entry(self, entry_id: str) -> Optional[RunHistoryEntry]:
        return self._entries.get(entry_id)

    def entries(self) -> Iterable[RunHistoryEntry]:
        for identifier in self._order:
            entry = self._entries.get(identifier)
            if entry is not None:
                yield entry

    def set_active_entry(self, entry_id: Optional[str]) -> None:
        if entry_id is not None and entry_id not in self._entries:
            entry_id = None
        if entry_id == self._active_entry_id:
            return
        self._active_entry_id = entry_id
        self.activeEntryChanged.emit(entry_id)

    def request_comparison(self, entry_id: str) -> None:
        entry = self.get_entry(entry_id)
        if entry is None:
            self.comparisonUnavailable.emit("Selected run is no longer available for comparison.")
            return

        if self._active_entry_id is None:
            self.comparisonUnavailable.emit("Open or select a run in the viewer to compare against.")
            return

        active_entry = self.get_entry(self._active_entry_id)
        if active_entry is None:
            self.comparisonUnavailable.emit("The reference run could not be determined.")
            return

        if active_entry.identifier == entry.identifier:
            self.comparisonUnavailable.emit("Select a different run to compare with the current one.")
            return

        self.comparisonRequested.emit(active_entry, entry)

    def request_open(self, entry_id: str) -> None:
        entry = self.get_entry(entry_id)
        if entry is None:
            return
        self.openRequested.emit(entry)
