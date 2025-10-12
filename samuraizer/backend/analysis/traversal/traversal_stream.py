"""Streaming helpers for repository traversal."""

from typing import Generator, Dict, Any, Set, Optional, List
from pathlib import Path
import logging

from .traversal_processor import generate_directory_chunks, _DEFAULT_CHUNK_SIZE
from ...services.event_service.cancellation import CancellationToken


def get_directory_structure_stream(
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: List[str],
    threads: int,
    encoding: str = 'utf-8',
    hash_algorithm: Optional[str] = "xxhash",
    cancellation_token: Optional[CancellationToken] = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_pending_tasks: Optional[int] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Yield traversal results as soon as they are available."""

    logging.debug("Starting streaming directory structure generation")

    chunk_generator = generate_directory_chunks(
        root_dir=root_dir,
        max_file_size=max_file_size,
        include_binary=include_binary,
        excluded_folders=excluded_folders,
        excluded_files=excluded_files,
        follow_symlinks=follow_symlinks,
        image_extensions=image_extensions,
        exclude_patterns=exclude_patterns,
        threads=threads,
        encoding=encoding or 'utf-8',
        hash_algorithm=hash_algorithm,
        progress_callback=None,
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
        max_pending_tasks=max_pending_tasks,
    )

    for payload in chunk_generator:
        if "entries" in payload:
            for entry in payload["entries"]:
                yield entry
        else:
            yield payload
