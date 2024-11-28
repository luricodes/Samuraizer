import json
import logging
from typing import Any, Dict, Generator
import os
import uuid
from datetime import datetime

from samuraizer.utils.time_utils import format_timestamp
from colorama import Fore, Style

def output_to_jsonl(
    data_generator: Generator[Dict[str, Any], None, None],
    output_file: str,
    config: Dict[str, Any] = None
) -> None:
    """
    Writes data to a JSONL file. Optionally formats data for LLM fine-tuning.

    Args:
        data_generator (Generator[Dict[str, Any], None, None]): Generator producing data dictionaries.
        output_file (str): Path to the output JSONL file.
        config (Dict[str, Any], optional): Configuration dictionary.
            - remove_empty_fields (bool): Whether to remove fields with empty values. Defaults to True.
            - llm_finetuning (bool): Whether to format data for LLM fine-tuning. Defaults to False.
            - include_metadata (bool): Whether to include metadata fields like 'source', 'timestamp', and 'id'. Defaults to False.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            for data in data_generator:
                if not isinstance(data, dict):
                    logging.error(
                        f"Unexpected data type: {type(data)}. Expected: dict. Data: {data}"
                    )
                    continue

                # Initialize JSON payload
                json_payload = {}

                if config and config.get('llm_finetuning', False):
                    # Format data for LLM fine-tuning
                    code = data.get("content", "")
                    language = data.get("type", "")

                    if not code or not language:
                        logging.error(
                            f"Missing 'content' or 'type' for LLM fine-tuning. Data: {data}"
                        )
                        continue

                    json_payload = {
                        "code": code,
                        "path": data.get("path", ""),
                        "language": language
                    }

                    # Include metadata if configured
                    if config.get('include_metadata', False):
                        json_payload["id"] = str(uuid.uuid4())
                        json_payload["timestamp"] = datetime.utcnow().isoformat() + 'Z'
                        json_payload["source"] = config.get("source", "samuraizer")

                elif "summary" in data:
                    # Write the summary as a separate JSON object
                    summary_data = data.get("summary")
                    if not isinstance(summary_data, dict):
                        logging.error(
                            f"Unexpected type for 'summary': {type(summary_data)}. Expected: dict."
                        )
                        continue
                    json_payload = {"summary": summary_data}
                else:
                    parent = data.get("parent", "")
                    filename = data.get("filename", "")
                    info = data.get("info", {})

                    if not isinstance(info, dict):
                        logging.error(
                            f"Unexpected type for 'info': {type(info)}. Expected: dict. Data: {info}"
                        )
                        continue

                    file_path = os.path.join(parent, filename) if parent else filename
                    file_path = file_path.replace(os.sep, '/')

                    # Create the JSON payload
                    json_payload = {
                        "path": file_path,
                        "type": info.get("type", ""),
                        "size": info.get("size", ""),
                        "created": format_timestamp(info.get("created")),
                        "modified": format_timestamp(info.get("modified")),
                        "permissions": info.get("permissions", ""),
                        "hash": info.get("file_hash", ""),
                        "content": info.get("content", "")
                    }

                # Remove empty fields if specified in config
                if config and config.get('remove_empty_fields', True):
                    json_payload = {k: v for k, v in json_payload.items() if v}

                try:
                    json_line = json.dumps(json_payload, ensure_ascii=False)
                    out_file.write(json_line + '\n')
                    logging.debug(f"Writing entry: {json_payload}")
                except (TypeError, ValueError) as json_err:
                    logging.error(
                        f"Error serializing JSON data: {json_err}. Data: {json_payload}"
                    )
            logging.info(f"JSONL output successfully written to '{output_file}'.")
    except IOError as io_err:
        logging.error(f"IO error while writing the JSONL output file: {io_err}")
    except Exception as e:
        logging.error(f"Unexpected error while writing the JSONL output file: {e}")
