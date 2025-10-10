import json
import logging
import os
from typing import Any, Dict, Iterable, Optional

from samuraizer.utils.time_utils import format_timestamp


def output_to_jsonl(
    data_generator: Iterable[Dict[str, Any]],
    output_file: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Write analysis results to a JSON Lines file."""
    remove_empty_fields = False
    if config:
        remove_empty_fields = config.get("remove_empty_fields", False)

    try:
        with open(output_file, "w", encoding="utf-8") as out_file:
            for data in data_generator:
                if not isinstance(data, dict):
                    logging.error(
                        "Unexpected data type: %s. Expected dict. Data: %r",
                        type(data),
                        data,
                    )
                    continue

                payload: Dict[str, Any]
                if "summary" in data:
                    summary_data = data.get("summary")
                    if not isinstance(summary_data, dict):
                        logging.error(
                            "Unexpected type for 'summary': %s. Expected dict.",
                            type(summary_data),
                        )
                        continue
                    payload = {"summary": summary_data}
                else:
                    parent = data.get("parent", "")
                    filename = data.get("filename", "")
                    info = data.get("info", {})

                    if not isinstance(info, dict):
                        logging.error(
                            "Unexpected type for 'info': %s. Expected dict. Data: %r",
                            type(info),
                            info,
                        )
                        continue

                    file_path = os.path.join(parent, filename) if parent else filename
                    file_path = file_path.replace(os.sep, "/")

                    payload = {
                        "path": file_path,
                        "type": info.get("type", ""),
                        "size": info.get("size", ""),
                        "created": format_timestamp(info.get("created")),
                        "modified": format_timestamp(info.get("modified")),
                        "permissions": info.get("permissions", ""),
                        "hash": info.get("file_hash", ""),
                        "content": info.get("content", ""),
                    }

                if remove_empty_fields:
                    payload = {
                        key: value
                        for key, value in payload.items()
                        if value not in ("", None, [], {})
                    }

                out_file.write(json.dumps(payload, ensure_ascii=False))
                out_file.write("\n")

    except Exception as exc:
        logging.error("Failed to write JSONL output: %s", exc, exc_info=True)
        raise
