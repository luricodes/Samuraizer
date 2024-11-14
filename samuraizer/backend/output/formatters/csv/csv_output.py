# samuraizer/output/formatters/csv/csv_output.py

import csv
import logging
from datetime import datetime
from typing import Any, Dict, Generator
from samuraizer.utils.time_utils import format_timestamp
from colorama import Fore, Style

def output_to_csv(data: Dict[str, Any], output_file: str, config: Dict[str, Any] = None) -> None:
    """
    Write data to a CSV file.
    
    Args:
        data: The data to write
        output_file: The output file path
        config: Optional configuration dictionary
    """
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['Path', 'Type', 'Size', 'Created', 'Modified', 'Permissions', 'Timezone'])
            
            # Write data
            for path, value in _flatten_structure(data).items():
                if isinstance(value, dict):
                    row = _create_csv_row(path, value)
                    writer.writerow(row)
                    
    except Exception as e:
        logging.error(
            f"{Fore.RED}Error writing CSV output file: {e}{Style.RESET_ALL}"
        )

def output_to_csv_stream(data_generator: Generator[Dict[str, Any], None, None], output_file: str, config: Dict[str, Any] = None) -> None:
    """
    Write data to a CSV file in streaming mode.
    
    Args:
        data_generator: Generator yielding data to write
        output_file: The output file path
        config: Optional configuration dictionary
    """
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['Path', 'Type', 'Size', 'Created', 'Modified', 'Permissions', 'Timezone'])
            
            for data in data_generator:
                if isinstance(data, dict):
                    if "summary" in data:
                        continue  # Skip summary in CSV output
                        
                    if "structure" in data:
                        for path, info in _flatten_structure(data["structure"]).items():
                            row = _create_csv_row(path, info)
                            writer.writerow(row)
                    else:
                        row = _create_csv_row(data.get("path", ""), data.get("info", {}))
                        writer.writerow(row)
                        
    except Exception as e:
        logging.error(
            f"{Fore.RED}Error writing CSV output file in streaming mode: {e}{Style.RESET_ALL}"
        )

def _create_csv_row(path: str, value: Dict[str, Any]) -> list:
    """Create a CSV row from file information."""
    try:
        return [
            path,
            value.get("type", ""),
            value.get("size", ""),
            format_timestamp(value.get("created")),
            format_timestamp(value.get("modified")),
            value.get("permissions", ""),
            value.get("timezone", "UTC")  # Include timezone information
        ]
    except Exception as e:
        logging.error(f"Error creating CSV row: {e}")
        return [path, "error", "", "", "", "", ""]

def _flatten_structure(structure: Dict[str, Any], parent_path: str = "") -> Dict[str, Any]:
    """
    Flatten a nested directory structure.
    
    Args:
        structure: The nested directory structure
        parent_path: The current parent path (used in recursion)
        
    Returns:
        Dict[str, Any]: Flattened structure
    """
    flattened = {}
    for name, value in structure.items():
        current_path = f"{parent_path}/{name}" if parent_path else name
        if isinstance(value, dict):
            if "type" in value or "size" in value:  # File info dict
                flattened[current_path] = value
            else:  # Directory
                flattened.update(_flatten_structure(value, current_path))
        else:
            flattened[current_path] = value
    return flattened
