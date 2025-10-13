import logging
import multiprocessing
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from colorama import init as colorama_init
from PyQt6.QtCore import QSettings

from samuraizer.backend.analysis.traversal.progressive_store import ProgressiveResultStore
from samuraizer.backend.analysis.traversal.traversal_processor import get_directory_structure
from samuraizer.backend.analysis.traversal.traversal_stream import (
    get_directory_structure_stream,
)
from samuraizer.backend.cache.connection_pool import (
    close_all_connections,
    flush_pending_writes,
    initialize_connection_pool,
    set_cache_disabled,
)
from samuraizer.backend.output.factory.output_factory import OutputFactory
from samuraizer.backend.output.progressive_writer import write_progressive_output
from samuraizer.backend.services.config_services import (
    CACHE_DB_FILE,
    config_manager,
    get_default_analysis_settings,
    get_default_cache_settings,
    get_default_output_settings,
    get_default_timezone_settings,
)
from samuraizer.backend.services.event_service.cancellation import CancellationTokenSource
from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.cli.parser import SUPPORTED_FORMATS, parse_arguments
from samuraizer.config import ConfigError

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
    """Determine the cache path using GUI settings when available."""

    try:
        try:
            settings = QSettings()
            in_gui_mode = True
        except Exception:  # pragma: no cover - GUI not available
            in_gui_mode = False
            settings = None

        if in_gui_mode and settings is not None:
            if settings.value("settings/disable_cache", False, type=bool):
                logging.info(
                    "Cache disabled in GUI settings, using path from configuration/CLI: %s",
                    args_cache_path,
                )
                return args_cache_path

            settings_cache_path = settings.value("settings/cache_path")
            if settings_cache_path:
                cache_path = Path(settings_cache_path)
                if not cache_path.is_absolute():
                    cache_path = cache_path.resolve()
                logging.info("Using cache path from GUI settings: %s", cache_path)
                return cache_path

        if args_cache_path != Path(".cache"):
            resolved_path = args_cache_path.resolve()
            logging.info("Using command line cache path: %s", resolved_path)
            return resolved_path

        default_path = Path.cwd() / ".cache"
        logging.info("Using default cache path: %s", default_path)
        return default_path
    except Exception as exc:
        logging.error("Error determining cache path: %s", exc)
        return args_cache_path


def initialize_cache_directory(cache_path: Path) -> Path:
    try:
        cache_path = cache_path.resolve()
        cache_path.mkdir(parents=True, exist_ok=True)
        if not os.access(cache_path, os.W_OK):
            raise PermissionError(f"Cache directory is not writable: {cache_path}")
        logging.info("Cache directory initialized: %s", cache_path)
        return cache_path
    except Exception as exc:
        logging.error("Error initializing cache directory '%s': %s", cache_path, exc)
        raise


def _prepare_output_format(output_file: str, output_format: str) -> str:
    extension_map = {
        "json": ".json",
        "yaml": ".yaml",
        "xml": ".xml",
        "jsonl": ".jsonl",
        "dot": ".dot",
        "csv": ".csv",
        "sexp": ".sexp",
        "msgpack": ".msgpack",
    }
    expected_extension = extension_map.get(output_format)
    if expected_extension is None:
        raise ValueError(f"Unsupported output format: {output_format}")

    output_path = Path(output_file)
    if output_path.suffix.lower() != expected_extension:
        adjusted = str(output_path.with_suffix(expected_extension))
        logging.info(
            "Adjusted output filename to use correct extension: %s -> %s",
            output_file,
            adjusted,
        )
        return adjusted
    return output_file


def run() -> None:
    colorama_init(autoreset=True)
    args = parse_arguments()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    setup_logging(args.verbose, args.log_file)

    # Load configuration and profiles
    config_path = Path(args.config).expanduser() if args.config else None
    try:
        config_manager.reload_configuration(
            str(config_path) if config_path else None, profile=args.profile
        )
    except ConfigError as exc:
        logging.error("Failed to load configuration: %s", exc)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Unexpected configuration error: %s", exc)
        sys.exit(1)

    if args.config_validate:
        valid = config_manager.validate_configuration()
        message = "Configuration is valid." if valid else "Configuration validation failed."
        print(message)
        sys.exit(0 if valid else 1)

    if args.config_migrate:
        try:
            migrated = config_manager.migrate_configuration()
        except ConfigError as exc:
            logging.error("Configuration migration failed: %s", exc)
            print(f"Configuration migration failed: {exc}")
            sys.exit(1)
        if migrated:
            logging.info("Legacy configuration migrated successfully.")
            print("Legacy configuration migrated successfully.")
        else:
            logging.info("No legacy configuration files found to migrate.")
            print("No legacy configuration files found to migrate.")
        sys.exit(0)

    cancellation_source = CancellationTokenSource()
    _set_cli_cancellation_source(cancellation_source)

    root_directory = Path(args.root_directory).resolve()
    output_file = args.output

    analysis_defaults = get_default_analysis_settings()
    cache_defaults = get_default_cache_settings()
    output_defaults = get_default_output_settings()
    timezone_defaults = get_default_timezone_settings()

    output_format = args.format or analysis_defaults.get("default_format", "json")
    if output_format not in SUPPORTED_FORMATS:
        logging.error("Unsupported output format requested: %s", output_format)
        sys.exit(2)

    stream_mode = output_defaults.get("streaming", False)
    if args.stream is True:
        stream_mode = True
    if output_format in {"jsonl", "msgpack"}:
        stream_mode = True

    include_binary = bool(analysis_defaults.get("include_binary", False))
    if args.include_binary:
        include_binary = True

    follow_symlinks = bool(analysis_defaults.get("follow_symlinks", False))
    if args.follow_symlinks:
        follow_symlinks = True

    encoding = args.encoding or analysis_defaults.get("encoding", "auto")

    threads = analysis_defaults.get("threads") or (
        multiprocessing.cpu_count() * DEFAULT_THREAD_MULTIPLIER
    )
    if args.threads:
        threads = args.threads

    include_summary = bool(analysis_defaults.get("include_summary", True))
    if args.include_summary:
        include_summary = True

    cache_enabled = bool(analysis_defaults.get("cache_enabled", True))
    if args.no_cache:
        cache_enabled = False

    hash_algorithm = args.hash_algorithm or analysis_defaults.get("hash_algorithm", "xxhash")
    if args.no_hash or not cache_enabled:
        hash_algorithm = None

    max_size_mb = args.max_size or analysis_defaults.get("max_file_size_mb", 50)
    max_file_size = max_size_mb * 1024 * 1024

    cache_path_setting = Path(cache_defaults.get("path", "~/.cache/samurai")).expanduser()
    cmd_cache_path = Path(args.cache_path).expanduser() if args.cache_path else cache_path_setting
    cache_path = get_cache_path(cmd_cache_path)

    use_utc = bool(timezone_defaults.get("use_utc", False))
    if args.use_utc:
        use_utc = True
    repository_timezone = args.repository_timezone or timezone_defaults.get("repository_timezone")

    output_file = _prepare_output_format(output_file, output_format)

    excluded_folders = config_manager.exclusion_config.get_excluded_folders()
    excluded_files = config_manager.exclusion_config.get_excluded_files()
    exclude_patterns = config_manager.exclusion_config.get_exclude_patterns()
    image_extensions = config_manager.exclusion_config.get_image_extensions()

    if args.exclude_folders:
        excluded_folders.update(args.exclude_folders)
    if args.exclude_files:
        excluded_files.update(args.exclude_files)
    if args.exclude_patterns:
        exclude_patterns = list(dict.fromkeys(exclude_patterns + args.exclude_patterns))
    if args.image_extensions:
        additional_image_extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.image_extensions
        }
        image_extensions.update(additional_image_extensions)

    logging.info("Active configuration profile: %s", config_manager.get_active_profile())
    logging.info("Search the directory: %s", root_directory)
    logging.info("Excluded folders: %s", ", ".join(sorted(excluded_folders)))
    logging.info("Excluded files: %s", ", ".join(sorted(excluded_files)))
    logging.info("Exclusion pattern: %s", ", ".join(exclude_patterns))
    logging.info("Image file extensions: %s", ", ".join(sorted(image_extensions)))
    logging.info("Binary files %s included", "are" if include_binary else "are not")
    logging.info("Symbolic links are %s", "followed" if follow_symlinks else "not followed")
    logging.info("Number of threads: %s", threads)
    logging.info("Standard encoding: %s", encoding)
    logging.info("Output file: %s (%s)", output_file, output_format)
    logging.info("Include summary: %s", include_summary)
    logging.info("Cache enabled: %s", cache_enabled)
    logging.info("Cache path: %s", cache_path)
    logging.info("Max file size (MB): %s", max_size_mb)
    logging.info("Using UTC timestamps: %s", use_utc)
    if repository_timezone:
        logging.info("Repository timezone: %s", repository_timezone)

    try:
        cache_dir = initialize_cache_directory(cache_path)
        cache_db_path = cache_dir / CACHE_DB_FILE
        set_cache_disabled(not cache_enabled)
        initialize_connection_pool(
            str(cache_db_path), thread_count=threads, force_disable_cache=not cache_enabled
        )
    except Exception as exc:
        logging.error("Failed to initialize cache: %s", exc)
        sys.exit(1)

    try:
        if stream_mode:
            if output_format in {"json", "jsonl", "msgpack"}:
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
                    hash_algorithm=hash_algorithm,
                    cancellation_token=cancellation_source.token,
                )
                output_function = OutputFactory.get_output(
                    output_format, streaming=True, config=output_defaults
                )
                output_function(data_gen, output_file)
            else:
                logging.error("--stream is only available for the JSON, JSONL & MsgPack formats.")
                sys.exit(1)
        else:
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
                    hash_algorithm=hash_algorithm,
                    cancellation_token=cancellation_source.token,
                    chunk_callback=store.add_entries,
                    materialize=False,
                )

                write_progressive_output(
                    fmt=output_format,
                    entries=store.iter_entries(),
                    summary=summary,
                    output_file=output_file,
                    config=output_defaults,
                    include_summary=include_summary,
                )

        logging.info(
            "The current status of the folder structure%s have been saved in '%s'",
            " and the summary " if include_summary else "",
            output_file,
        )
    except KeyboardInterrupt:
        if cancellation_source.is_cancelled():
            logging.warning("Forced programme abort.")
        else:
            logging.warning("Programme interrupted by user (CTRL+C).")
        sys.exit(1)
    except (OSError, IOError) as exc:
        logging.error("Error when writing the output file after cancellation: %s", exc)
        sys.exit(1)
    except ValueError as exc:
        logging.error("Error when selecting the output format: %s", exc)
        sys.exit(1)
    finally:
        try:
            flush_pending_writes()
            close_all_connections()
            config_manager.cleanup()
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logging.error("Error during cleanup: %s", exc)
        finally:
            _set_cli_cancellation_source(None)
