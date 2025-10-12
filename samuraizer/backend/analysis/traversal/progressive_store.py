"""Utilities for buffering traversal results without unbounded memory usage."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple


class ProgressiveResultStore:
    """Persist traversal results to a temporary SQLite database.

    The store keeps the on-disk footprint bounded while allowing callers to
    iterate over the collected entries in lexical path order without retaining
    all entries in memory simultaneously.
    """

    def __init__(self, *, prefix: str = "samuraizer_results", dir: Optional[Path] = None) -> None:
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".db", dir=str(dir) if dir else None)
        os.close(fd)
        self._path = Path(path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                path TEXT PRIMARY KEY,
                parent TEXT NOT NULL,
                filename TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_parent ON entries(parent)")
        self._conn.commit()
        self._closed = False

    @property
    def path(self) -> Path:
        return self._path

    def add_entries(self, entries: Sequence[Dict[str, object]]) -> None:
        if not entries:
            return
        with self._conn:  # implicit transaction for the batch
            self._conn.executemany(
                "INSERT OR REPLACE INTO entries(path, parent, filename, payload) VALUES(?,?,?,?)",
                [
                    (
                        _compose_path(entry.get("parent", ""), entry.get("filename", "")),
                        entry.get("parent", ""),
                        entry.get("filename", ""),
                        json.dumps(entry.get("info", {}), ensure_ascii=False),
                    )
                    for entry in entries
                ],
            )

    def iter_entries(self) -> Iterator[Tuple[List[str], Dict[str, object]]]:
        cursor = self._conn.execute("SELECT path, payload FROM entries ORDER BY path")
        for path, payload in cursor:
            parts = [p for p in Path(path).parts if p]
            if not parts:
                continue
            yield parts, json.loads(payload)

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._conn.close()
        finally:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            self._closed = True

    def __enter__(self) -> "ProgressiveResultStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _compose_path(parent: object, filename: object) -> str:
    parent_str = str(parent or "").strip()
    filename_str = str(filename or "").strip()
    if parent_str in {"", "."}:
        return filename_str
    if not filename_str:
        return parent_str
    return str(Path(parent_str) / filename_str)
