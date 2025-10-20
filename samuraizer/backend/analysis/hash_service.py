# samuraizer/analysis/hash_service.py

import logging
from pathlib import Path
from typing import Optional

from colorama import Fore, Style

try:
    import xxhash  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    xxhash = None  # type: ignore

_missing_xxhash_warning_emitted = False


def _create_hasher():
    """Return a callable with an xxhash-compatible interface."""

    global _missing_xxhash_warning_emitted

    if xxhash is not None:
        return xxhash.xxh64()

    import hashlib

    if not _missing_xxhash_warning_emitted:
        warning_message = (
            f"{Fore.YELLOW}xxhash package is not installed. "
            "Falling back to hashlib.blake2b for hashing, which may be slower."
            f"{Style.RESET_ALL}"
        )
        logging.warning(warning_message)
        _missing_xxhash_warning_emitted = True

    class _HashlibWrapper:
        """Minimal xxhash-compatible wrapper using hashlib blake2b."""

        def __init__(self) -> None:
            self._hasher = hashlib.blake2b(digest_size=8)

        def update(self, data: bytes) -> None:
            self._hasher.update(data)

        def hexdigest(self) -> str:
            return self._hasher.hexdigest()

    return _HashlibWrapper()

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
            hasher = _create_hasher()
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
