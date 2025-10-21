<<<<<<< ours
<<<<<<< ours
"""Data structures used by the run history UI components."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
=======
=======
>>>>>>> theirs
"""Data structures and helpers used by the run history UI components."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Dict, List, Optional


def normalise_json(data: Any) -> str:
    """Return a stable, human-readable JSON representation of ``data``.

    The run history frequently needs to write arbitrary dictionaries to disk or
    display them in a diff viewer.  The helper mirrors :func:`json.dumps` but is
    defensive towards objects that are not directly serialisable by falling back
    to ``str`` representations.
    """

    try:
        return json.dumps(data, indent=2, sort_keys=True, default=str)
    except TypeError:
        safe_payload = json.loads(json.dumps(data, default=str))
        return json.dumps(safe_payload, indent=2, sort_keys=True)
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs


@dataclass(slots=True)
class RunHistoryEntry:
    """Container describing a single analysis run."""

    identifier: str
    display_name: str
    timestamp: datetime
    repository: str
    preset: str
    output_format: str
    duration_seconds: Optional[float] = None
    processed_files: Optional[int] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)

    def metadata_for_overview(self) -> Dict[str, Any]:
        """Return a simplified metadata dictionary for overview displays."""

        overview = {
            "Display Name": self.display_name,
            "Repository": self.repository,
            "Preset": self.preset or "default",
            "Output Format": self.output_format,
            "Timestamp": self.timestamp.isoformat(sep=" ", timespec="seconds"),
        }
        if self.duration_seconds is not None:
            overview["Duration (s)"] = f"{self.duration_seconds:.2f}"
        if self.processed_files is not None:
            overview["Files"] = str(self.processed_files)
        return overview
<<<<<<< ours
<<<<<<< ours
=======
=======
>>>>>>> theirs

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def summary_lines(self) -> List[str]:
        """Return formatted lines summarising the run metadata and metrics."""

        lines: List[str] = [f"{key}: {value}" for key, value in self.metadata_for_overview().items()]

        if self.summary:
            lines.append("")
            lines.append("Summary metrics:")
            for key in sorted(self.summary):
                value = self.summary.get(key, "")
                lines.append(f"- {key}: {value}")

        return lines

    def summary_text(self) -> str:
        """Return a ready-to-share text description for clipboard actions."""

        return "\n".join(self.summary_lines()).strip()

    def export_payload(self) -> Dict[str, Any]:
        """Return a deep-copied payload suitable for serialisation."""

        payload: Dict[str, Any] = {
            "identifier": self.identifier,
            "display_name": self.display_name,
            "timestamp": self.timestamp.isoformat(),
            "repository": self.repository,
            "preset": self.preset,
            "output_format": self.output_format,
            "duration_seconds": self.duration_seconds,
            "processed_files": self.processed_files,
            "configuration": deepcopy(self.configuration),
            "summary": deepcopy(self.summary),
            "results": deepcopy(self.results),
        }
        return payload

    def export_as_json(self) -> str:
        """Return a JSON string representing the export payload."""

        return normalise_json(self.export_payload())
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
