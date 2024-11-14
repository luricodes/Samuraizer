# samuraizer/utils/helpers.py

import logging
from colorama import Fore, Style
from pathlib import Path


def is_binary_alternative(file_path: Path) -> bool:
    """
    Alternative method for binary file detection:
    Checks if the file contains NULL bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            if b'\0' in chunk:
                return True
        return False
    except Exception as e:
        logging.error(f"{Fore.RED}Error during alternative binary check for {file_path}: {e}{Style.RESET_ALL}")
        return False
