# samuraizer/utils/mime_type.py

import magic  # type: ignore[import-untyped]
import threading
from colorama import Fore, Style
import logging
from pathlib import Path
from .file_helpers import is_binary_alternative

thread_local_data = threading.local()

def get_magic_instance():
    if not hasattr(thread_local_data, 'mime'):
        try:
            thread_local_data.mime = magic.Magic(mime=True)
        except Exception as e:
            logging.error(f"{Fore.RED}Error initializing magic: {e}{Style.RESET_ALL}")
            thread_local_data.mime = None
    return thread_local_data.mime

def is_binary(file_path: Path) -> bool:
    """
    Checks if a file is binary based on its MIME type.
    If MIME detection fails, it uses an alternative method.
    """
    try:
        mime = get_magic_instance()
        if mime is None:
            return is_binary_alternative(file_path)
        
        # Read only the first 8192 bytes of the file
        with open(file_path, 'rb') as f:
            file_content = f.read(8192)
        
        mime_type = mime.from_buffer(file_content)
        logging.debug(f"File: {file_path} - MIME type: {mime_type}")
        return not mime_type.startswith('text/')
    except Exception as e:
        logging.warning(f"{Fore.YELLOW}Error detecting MIME type for {file_path}: {e}{Style.RESET_ALL}")
        # Alternative method for binary check
        return is_binary_alternative(file_path)
