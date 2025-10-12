# samuraizer/core/application.py

import os
from pathlib import Path
import logging
import signal
import multiprocessing
import sys
from typing import Any, Dict, Optional, Set, List
from PyQt6.QtCore import QSettings

from samuraizer.backend.services.event_service.cancellation import CancellationTokenSource
from samuraizer.backend.cache.connection_pool import (
    initialize_connection_pool,
    get_connection_context,
    close_all_connections,
    flush_pending_writes,
)
from samuraizer.cli.parser import parse_arguments
from samuraizer.backend.services.config_services import (
    CACHE_DB_FILE,
    DEFAULT_MAX_FILE_SIZE_MB,
    config_manager
)
from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.backend.output.factory.output_factory import OutputFactory
from ..backend.analysis.traversal.traversal_processor import get_directory_structure
from ..backend.analysis.traversal.traversal_stream import get_directory_structure_stream
from ..backend.analysis.traversal.progressive_store import ProgressiveResultStore
from ..backend.output.progressive_writer import write_progressive_output
from colorama import init as colorama_init

DEFAULT_THREAD_MULTIPLIER = 2

_cli_cancellation_source: Optional[CancellationTokenSource] = None


def _set_cli_cancellation_source(source: Optional[CancellationTokenSource]) -> None:
    global _cli_cancellation_source
    _cli_cancellation_source = source


def signal_handler(sig, frame):
    source = _cli_cancellation_source
    if source is None:
        logging.warning("Programme interrupted but no cancellable operation is active.")
        return

    if not source.is_cancelled():
        logging.warning("Programme interrupted by user (CTRL+C).")
        source.cancel()
    else:
        logging.warning("Second CTRL+C recognised. Immediate cancellation.")
        sys.exit(1)

def get_cache_path(args_cache_path: Path) -> Path:
    """
    Get the cache path from settings or use default.
    Handles both CLI and GUI modes appropriately.
    
    Args:
        args_cache_path: Cache path from command line arguments

    Returns:
        Path: The resolved cache path
    """
    try:
        # Check if we're running in GUI mode by trying to access QSettings
        try:
            from PyQt6.QtCore import QSettings
            settings = QSettings()
            in_gui_mode = True
        except ImportError:
            in_gui_mode = False

        # If in GUI mode, check GUI settings first
        if in_gui_mode:
            if settings.value("settings/disable_cache", False, type=bool):
                logging.info(f"Cache disabled in GUI settings, using default path: {args_cache_path}")
                return args_cache_path

            settings_cache_path = settings.value("settings/cache_path")
            if settings_cache_path:
                try:
                    cache_path = Path(settings_cache_path)
                    if not cache_path.is_absolute():
                        cache_path = cache_path.resolve()
                    logging.info(f"Using cache path from GUI settings: {cache_path}")
                    return cache_path
                except Exception as e:
                    logging.error(f"Error processing GUI cache path: {e}")

        # If we're in CLI mode or GUI settings aren't available/valid
        if args_cache_path != Path(".cache"):
            resolved_path = args_cache_path.resolve()
            logging.info(f"Using command line cache path: {resolved_path}")
            return resolved_path

        # Default to current directory .cache
        default_path = Path.cwd() / ".cache"
        logging.info(f"Using default cache path: {default_path}")
        return default_path

    except Exception as e:
        logging.error(f"Error determining cache path: {e}")
        return args_cache_path

def initialize_cache_directory(cache_path: Path) -> Path:
    """Initialize and validate the cache directory."""
    try:
        # Ensure absolute path
        cache_path = cache_path.resolve()
        
        # Create directory if it doesn't exist
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Verify directory is writable
        if not os.access(cache_path, os.W_OK):
            raise PermissionError(f"Cache directory is not writable: {cache_path}")
            
        logging.info(f"Cache directory initialized: {cache_path}")
        return cache_path
        
    except Exception as e:
        logging.error(f"Error initializing cache directory '{cache_path}': {e}")
        raise

def run() -> None:
    colorama_init(autoreset=True)
    args = parse_arguments()

    # Register the global signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    setup_logging(args.verbose, args.log_file)

    # Prepare cancellation handling for this run
    cancellation_source = CancellationTokenSource()
    _set_cli_cancellation_source(cancellation_source)

    # Process command line arguments
    root_directory: Path = Path(args.root_directory).resolve()
    output_file: str = args.output
    include_binary: bool = args.include_binary
    follow_symlinks: bool = args.follow_symlinks
    include_summary: bool = args.include_summary
    output_format: str = args.format
    stream_mode: bool = args.stream
    encoding: Optional[str] = args.encoding
    cmd_cache_path: Path = Path(args.cache_path).expanduser().resolve()
    threads: int = args.threads or (multiprocessing.cpu_count() * DEFAULT_THREAD_MULTIPLIER)

    # Get configuration values
    excluded_folders = config_manager.exclusion_config.get_excluded_folders()
    excluded_files = config_manager.exclusion_config.get_excluded_files()
    exclude_patterns = config_manager.exclusion_config.get_exclude_patterns()
    image_extensions = config_manager.exclusion_config.get_image_extensions()

    # Update with CLI arguments if provided
    if args.exclude_folders:
        excluded_folders.update(args.exclude_folders)
    if args.exclude_files:
        excluded_files.update(args.exclude_files)
    if args.exclude_patterns:
        exclude_patterns.extend(args.exclude_patterns)
    if args.image_extensions:
        additional_image_extensions = {
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in args.image_extensions
        }
        image_extensions.update(additional_image_extensions)

    if args.no_cache:
        logging.info("File caching is disabled")
    else:
        logging.info("Using xxHash for efficient file caching")

    # Configure threading
    logging.info(f"Using {threads} threads for processing")

    # Configure max file size
    max_file_size = args.max_size * 1024 * 1024  # Convert MB to bytes
    logging.info(f"Maximum file size for reading: {max_file_size / (1024 * 1024)} MB")

    # Get cache path from settings or command line
    cmd_cache_path = Path(args.cache_path).expanduser()
    cache_path = get_cache_path(cmd_cache_path)

    # Log configuration
    logging.info(f"Search the directory: {root_directory}")
    logging.info(f"Excluded folders: {', '.join(sorted(excluded_folders))}")
    logging.info(f"Excluded files: {', '.join(sorted(excluded_files))}")
    if not include_binary:
        logging.info("Binary files and image files are excluded.")
    else:
        logging.info("Binary files and image files are included.")
    logging.info(f"Issue in: {output_file} ({output_format})")
    logging.info(f"Symbolic links are {'followed' if follow_symlinks else 'not followed'}")
    logging.info(f"Image file extensions: {', '.join(sorted(image_extensions))}")
    logging.info(f"Exclusion pattern: {', '.join(exclude_patterns)}")
    logging.info(f"Number of threads: {threads}")
    logging.info(f"Standard encoding: {encoding}")
    logging.info(f"Cache path: {cache_path}")

    # Initialize cache
    cache_dir: Path = initialize_cache_directory(cache_path)
    cache_db_path: Path = cache_dir / CACHE_DB_FILE
    db_path_str: str = str(cache_db_path)
    try:
        cache_dir = initialize_cache_directory(cache_path)
        cache_db_path = cache_dir / CACHE_DB_FILE
        db_path_str = str(cache_db_path)
        
        # Initialize connection pool with thread count instead of pool size
        initialize_connection_pool(db_path_str, thread_count=threads, force_disable_cache=args.no_cache)
        
        logging.info(f"Cache initialized at: {cache_dir}")
        
    except Exception as e:
        logging.error(f"Failed to initialize cache: {e}")
        sys.exit(1)

    try:
        if stream_mode:
            # Use Streaming-Mode
            if output_format in ["json", "jsonl", "msgpack"]:
                # USE JSON-Streaming or JSONL-Output or MsgPack-Output
                data_gen = get_directory_structure_stream(
                    root_dir=root_directory,
                    max_file_size=max_file_size,
                    include_binary=include_binary,
                    excluded_folders=excluded_folders,
                    excluded_files=excluded_files,
                    follow_symlinks=follow_symlinks,
                    image_extensions=image_extensions,
                    exclude_patterns=exclude_patterns,
                    threads=threads,
                    encoding=encoding,
                    hash_algorithm=None if args.no_cache else 'xxhash',
                    cancellation_token=cancellation_source.token,
                )
                output_function = OutputFactory.get_output(output_format, streaming=stream_mode)
                output_function(data_gen, output_file)
            else:
                logging.error("--stream is only available for the JSON, JSONL & MsgPack formats.")
                sys.exit(1)
        else:
            # Standard mode now writes progress incrementally to keep memory bounded
            with ProgressiveResultStore() as store:
                _, summary = get_directory_structure(
                    root_dir=root_directory,
                    max_file_size=max_file_size,
                    include_binary=include_binary,
                    excluded_folders=excluded_folders,
                    excluded_files=excluded_files,
                    follow_symlinks=follow_symlinks,
                    image_extensions=image_extensions,
                    exclude_patterns=exclude_patterns,
                    threads=threads,
                    encoding=encoding,
                    hash_algorithm=None if args.no_cache else 'xxhash',
                    cancellation_token=cancellation_source.token,
                    chunk_callback=store.add_entries,
                    materialize=False,
                )

                write_progressive_output(
                    fmt=output_format,
                    entries=store.iter_entries(),
                    summary=summary,
                    output_file=output_file,
                    config={},
                    include_summary=include_summary,
                )

        logging.info(
            f"The current status of the folder structure"
            f"{' and the summary ' if include_summary else ''}"
            f" have been saved in'{output_file}'"
        )
    except KeyboardInterrupt:
        if cancellation_source.is_cancelled():
            logging.warning("Forced programme abort.")
        else:
            logging.warning("Programme interrupted by user (CTRL+C).")
        sys.exit(1)
    except (OSError, IOError) as e:
        logging.error(
            f"Error when writing the output file after cancellation: {str(e)}"
        )
        sys.exit(1)
    except ValueError as ve:
        logging.error(f"Error when selecting the output format: {ve}")
        sys.exit(1)
    finally:
        try:
            flush_pending_writes()
            close_all_connections()
            config_manager.cleanup()  # Clean up config manager
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        finally:
            _set_cli_cancellation_source(None)
