# samuraizer/output/yaml_output.py

import logging
from typing import Any, Dict
from pathlib import Path
import tempfile
import shutil

from colorama import Fore, Style
import yaml


class YAMLError(Exception):
    """Custom exception for YAML-related errors."""
    pass


def output_to_yaml(data: Dict[str, Any], output_file: str, config: Dict[str, Any] = None) -> None:
    """
    Writes data to a YAML file with advanced options, atomic write operations, and improved error handling.

    Args:
        data (Dict[str, Any]): The data to be written to the YAML file.
        output_file (str): The path to the output file.
        config (Dict[str, Any], optional): Configuration options for YAML output.
    """
    default_options = {
        'allow_unicode': True,
        'sort_keys': False,
        'default_flow_style': False,  # Improves readability by using block style
        'width': 4096,  # Increases the maximum line width to avoid long lists
    }
    
    # Update default options with config options if provided
    if config:
        default_options.update(config)

    try:
        # Validation of the data
        validate_data(data)

        # Atomic write operation: Write to a temporary file and rename
        temp_dir = Path(output_file).parent
        with tempfile.NamedTemporaryFile('w', delete=False, dir=temp_dir, encoding='utf-8') as temp_file:
            yaml.dump(data, temp_file, **default_options)
            temp_file_path = Path(temp_file.name)

        # Rename the temporary file to the final output file
        shutil.move(str(temp_file_path), output_file)

        logging.debug(f"YAML output successfully written to '{output_file}'.")
    except yaml.YAMLError as e:
        logging.error(
            f"{Fore.RED}YAML error while dumping data to '{output_file}': {e}{Style.RESET_ALL}"
        )
        raise YAMLError(f"YAML error: {e}") from e
    except (IOError, OSError) as e:
        logging.error(
            f"{Fore.RED}Error writing YAML output file '{output_file}': {e}{Style.RESET_ALL}"
        )
        raise
    except Exception as e:
        logging.error(
            f"{Fore.RED}Unexpected error writing YAML output file '{output_file}': {e}{Style.RESET_ALL}"
        )
        raise


def validate_data(data: Any) -> None:
    """
    Validates whether the data is YAML-compatible.

    Args:
        data (Any): The data to validate.

    Raises:
        YAMLError: If the data is not YAML-compatible.
    """
    try:
        # Attempts to serialize the data without saving it
        yaml.safe_dump(data)
    except yaml.YAMLError as e:
        raise YAMLError(f"Data is not YAML-compatible: {e}") from e
