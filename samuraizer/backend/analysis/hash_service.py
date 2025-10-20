"""High-performance hashing utilities with graceful fallbacks."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Protocol, Set

from colorama import Fore, Style


logger = logging.getLogger(__name__)


class _HashLike(Protocol):
    """Protocol describing the subset of hashlib/xxhash we rely on."""

    def update(self, data: bytes) -> None:
        ...

    def hexdigest(self) -> str:
        ...


AvailabilityCallback = Callable[[], bool]
FactoryCallback = Callable[[], _HashLike]


@dataclass(frozen=True)
class HashBackend:
    """Describes one hashing backend implementation."""

    name: str
    factory: FactoryCallback
    is_available: AvailabilityCallback
    warning_message: Optional[str] = None


class HashRegistry:
    """Registry that selects the most appropriate available hashing backend."""

    def __init__(self, backends: Optional[Iterable[HashBackend]] = None) -> None:
        self._backends: List[HashBackend] = list(backends or [])
        self._selected_backend: Optional[HashBackend] = None
        self._warned_backends: Set[str] = set()
        self._failed_backends: Set[str] = set()

    @property
    def backends(self) -> List[HashBackend]:
        """Expose registered backends for diagnostic and testing purposes."""

        return list(self._backends)

    def register(self, backend: HashBackend, *, prefer: bool = False) -> None:
        if prefer:
            self._backends.insert(0, backend)
        else:
            self._backends.append(backend)
        # Reset selection so that new backend can be considered.
        self.reset()

    def reset(self) -> None:
        self._selected_backend = None
        self._failed_backends.clear()

    def create_hasher(self) -> _HashLike:
        backend = self._resolve_backend()
        try:
            return backend.factory()
        except ModuleNotFoundError:
            logger.debug(
                "Hash backend %s reported available but module import failed; falling back",
                backend.name,
                exc_info=True,
            )
        except Exception:
            logger.exception("Hash backend %s failed to initialize", backend.name)

        # Mark backend as failed so we do not repeatedly try to use it.
        self._failed_backends.add(backend.name)
        self._selected_backend = None
        fallback_backend = self._resolve_backend()
        return fallback_backend.factory()

    def _resolve_backend(self) -> HashBackend:
        if self._selected_backend and self._selected_backend.name not in self._failed_backends:
            return self._selected_backend

        for backend in self._backends:
            if backend.name in self._failed_backends:
                continue
            if not backend.is_available():
                continue

            self._selected_backend = backend
            self._emit_warning_if_needed(backend)
            return backend

        raise RuntimeError("No hashing backend is available")

    def _emit_warning_if_needed(self, backend: HashBackend) -> None:
        if not backend.warning_message or backend.name in self._warned_backends:
            return

        logger.warning(backend.warning_message)
        self._warned_backends.add(backend.name)


def _xxhash_available() -> bool:
    return importlib.util.find_spec("xxhash") is not None


def _xxhash_factory() -> _HashLike:
    import xxhash  # type: ignore

    return xxhash.xxh64()


def _blake2b_factory() -> _HashLike:
    import hashlib

    hasher = hashlib.blake2b(digest_size=8)
    return hasher


_FALLBACK_WARNING = (
    f"{Fore.YELLOW}xxhash package is not installed. "
    "Falling back to hashlib.blake2b for hashing, which may be slower."
    f"{Style.RESET_ALL}"
)


def _build_default_registry() -> HashRegistry:
    registry = HashRegistry()
    registry.register(
        HashBackend(
            name="xxhash64",
            factory=_xxhash_factory,
            is_available=_xxhash_available,
            warning_message=None,
        ),
        prefer=True,
    )
    registry.register(
        HashBackend(
            name="blake2b-64",
            factory=_blake2b_factory,
            is_available=lambda: True,
            warning_message=_FALLBACK_WARNING,
        )
    )
    return registry


_HASH_REGISTRY = _build_default_registry()

class HashService:
    """Service for computing fast file hashes for cache validation."""
    
    CHUNK_SIZE = 65536  # Optimal chunk size for reading
    
    @staticmethod
    def compute_file_hash(file_path: Path) -> Optional[str]:
        """
        Calculates a fast hash of a file for cache validation purposes.
        Prefers xxHash when available and transparently falls back to
        a portable hashlib implementation otherwise.

        Args:
            file_path (Path): The path to the file

        Returns:
            Optional[str]: The file's hash as a hex string or None in case of errors
        """
        if not file_path.exists():
            logger.warning(f"{Fore.YELLOW}File not found: {file_path}{Style.RESET_ALL}")
            return None

        try:
            hasher = _HASH_REGISTRY.create_hasher()
            with file_path.open('rb') as file:
                for chunk in iter(lambda: file.read(HashService.CHUNK_SIZE), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()

        except PermissionError:
            logger.warning(f"{Fore.YELLOW}No permission to read the file: {file_path}{Style.RESET_ALL}")
        except OSError as e:
            logger.warning(f"{Fore.YELLOW}OS error when reading the file {file_path}: {e}{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"{Fore.RED}Unexpected error computing hash for {file_path}: {e}{Style.RESET_ALL}")
        
        return None

# Simple interface for backward compatibility if needed
compute_file_hash = HashService.compute_file_hash
