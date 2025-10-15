# samuraizer/output/json_output.py

import json
import logging
import os
from types import TracebackType
from typing import Any, Dict, Generator, Optional, TextIO

from samuraizer.utils.time_utils import format_timestamp
from colorama import Fore, Style

class JSONStreamWriter:
    """
    Context manager for incrementally writing a JSON file.
    Ensures that the JSON structure is properly closed, even in case of interruptions.
    """

    def __init__(self, output_file: str, pretty_print: bool = True):
        self.output_file = output_file
        self.file: Optional[TextIO] = None
        self.first_entry = True
        self.pretty_print = pretty_print
        self.indent = 4 if pretty_print else None

    def __enter__(self) -> "JSONStreamWriter":
        self.file = open(self.output_file, 'w', encoding='utf-8')
        self.file.write('{\n' if self.pretty_print else '{')
        self.file.write('  "structure": [\n' if self.pretty_print else '"structure":[')
        return self

    def write_entry(self, data: Dict[str, Any]) -> None:
        if self.file is None:
            raise RuntimeError("JSONStreamWriter not initialized. Call __enter__ first.")
        if not self.first_entry:
            self.file.write(',\n' if self.pretty_print else ',')
        else:
            self.first_entry = False
        json.dump(data, self.file, ensure_ascii=False, indent=self.indent)

    def write_summary(self, summary: Dict[str, Any]) -> None:
        if self.file is None:
            raise RuntimeError("JSONStreamWriter not initialized. Call __enter__ first.")
        self.file.write('\n  ],\n' if self.pretty_print else '],"summary":')
        if not self.pretty_print:
            json.dump(summary, self.file, ensure_ascii=False)
            self.file.write('}')
        else:
            self.file.write('  "summary": ')
            json.dump(summary, self.file, ensure_ascii=False, indent=4)
            self.file.write('\n}\n')

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.file:
            if exc_type is not None:
                # If an exception occurred, close the JSON structure gracefully
                try:
                    self.file.write('\n  ],\n' if self.pretty_print else '],"summary":{}')
                    if self.pretty_print:
                        self.file.write('  "summary": {}\n')
                        self.file.write('}\n')
                    else:
                        self.file.write('}')
                except Exception as e:
                    logging.error(
                        f"{Fore.RED}Error closing the JSON structure: {e}{Style.RESET_ALL}"
                    )
            self.file.close()

def output_to_json(
    data: Dict[str, Any],
    output_file: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Writes data in JSON format to a file.
    
    Args:
        data: The data to write
        output_file: The output file path
        config: Optional configuration dictionary containing formatting options
    """
    try:
        pretty_print = config.get('pretty_print', True) if config else True
        indent = 4 if pretty_print else None
        
        with open(output_file, 'w', encoding='utf-8') as out_file:
            json.dump(data, out_file, ensure_ascii=False, indent=indent)
    except Exception as e:
        logging.error(
            f"{Fore.RED}Error writing the JSON output file: {e}{Style.RESET_ALL}"
        )

def output_to_json_stream(
    data_generator: Generator[Dict[str, Any], None, None],
    output_file: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Writes the data to a JSON file in streaming mode.

    Args:
        data_generator: A generator that yields the data to be written
        output_file: The path to the output file
        config: Optional configuration dictionary containing formatting options
    """
    try:
        pretty_print = config.get('pretty_print', True) if config else True
        
        with JSONStreamWriter(output_file, pretty_print=pretty_print) as writer:
            summary = {}
            for data in data_generator:
                if isinstance(data, dict):
                    if "summary" in data:
                        summary = data["summary"]
                        continue
                    
                    # Handle the entry data
                    file_entry = {}
                    if "structure" in data:
                        # Handle nested structure format
                        for path, info in _flatten_structure(data["structure"]).items():
                            file_entry = {
                                "path": path.replace(os.sep, '/'),
                                "info": info
                            }
                            writer.write_entry(file_entry)
                    else:
                        # Handle direct entry format
                        writer.write_entry(data)

            # Write the summary at the end
            writer.write_summary(summary if summary else {})
    except Exception as e:
        logging.error(
            f"{Fore.RED}Error writing the JSON output file in streaming mode: {e}{Style.RESET_ALL}"
        )

def _flatten_structure(structure: Dict[str, Any], parent_path: str = "") -> Dict[str, Any]:
    """
    Flattens a nested directory structure into a dictionary of path-info pairs.
    
    Args:
        structure (Dict[str, Any]): The nested directory structure
        parent_path (str): The current parent path (used in recursion)
        
    Returns:
        Dict[str, Any]: A flattened dictionary where keys are file paths and values are file info
    """
    flattened = {}
    for name, value in structure.items():
        current_path = os.path.join(parent_path, name) if parent_path else name
        if isinstance(value, dict):
            if "type" in value or "size" in value:  # This is a file info dict
                flattened[current_path] = value
            else:  # This is a directory
                flattened.update(_flatten_structure(value, current_path))
        else:
            flattened[current_path] = value
    return flattened
