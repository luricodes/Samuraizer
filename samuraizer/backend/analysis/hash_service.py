# samuraizer/analysis/hash_service.py

import logging
import xxhash
from pathlib import Path
from typing import Optional
from colorama import Fore, Style

class HashService:
    """Service for computing fast file hashes for cache validation."""
    
    CHUNK_SIZE = 65536  # Optimal chunk size for reading
    
    @staticmethod
    def compute_file_hash(file_path: Path) -> Optional[str]:
        """
        Calculates a fast hash of a file for cache validation purposes.
        Uses xxHash for optimal performance.

        Args:
            file_path (Path): The path to the file

        Returns:
            Optional[str]: The file's hash as a hex string or None in case of errors
        """
        if not file_path.exists():
            logging.warning(f"{Fore.YELLOW}File not found: {file_path}{Style.RESET_ALL}")
            return None

        try:
            hasher = xxhash.xxh64()
            with file_path.open('rb') as file:
                for chunk in iter(lambda: file.read(HashService.CHUNK_SIZE), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()

        except PermissionError:
            logging.warning(f"{Fore.YELLOW}No permission to read the file: {file_path}{Style.RESET_ALL}")
        except OSError as e:
            logging.warning(f"{Fore.YELLOW}OS error when reading the file {file_path}: {e}{Style.RESET_ALL}")
        except Exception as e:
            logging.error(f"{Fore.RED}Unexpected error computing hash for {file_path}: {e}{Style.RESET_ALL}")
        
        return None

# Simple interface for backward compatibility if needed
compute_file_hash = HashService.compute_file_hash