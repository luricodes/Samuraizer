import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Generator, List
from pathlib import Path
import fnmatch
from PyQt6.QtCore import QObject, pyqtSignal
from samuraizer.backend.services.event_service.cancellation import CancellationTokenSource
from samuraizer.backend.analysis.traversal.async_traversal import (
    get_directory_structure_async,
    get_directory_structure_stream_async,
)
from samuraizer.backend.output.factory.output_factory import OutputFactory
from samuraizer.backend.cache.cache_cleaner import check_and_vacuum_if_needed
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from samuraizer.backend.cache.connection_pool import (
    initialize_connection_pool,
    is_cache_disabled,
    set_cache_disabled,
)
from samuraizer.config.unified import UnifiedConfigManager


logger = logging.getLogger(__name__)

class AnalyzerWorker(QObject):
    # Signal declarations
    progress = pyqtSignal(int, int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    fileProcessed = pyqtSignal(int)
    finished = pyqtSignal(object)

    # Format name mapping
    _format_mapping = {
        's-expression': 'sexp',
        'messagepack': 'msgpack'
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._stop_requested = False
        self.processed_files = 0
        self.total_files = 0
        self._estimator_thread: Optional[threading.Thread] = None
        self._estimator_stop = threading.Event()
        self._cancellation = CancellationTokenSource()

    def _map_format_name(self, format_name: str) -> str:
        """Map GUI format names to OutputFactory format keys"""
        return self._format_mapping.get(format_name.lower(), format_name.lower())

    def _count_files(self, root_dir: Path, excluded_folders: set, excluded_files: set) -> int:
        """Count total files to process before analysis."""
        total = 0
        try:
            for path in root_dir.rglob('*'):
                if self._stop_requested:
                    return 0

                if path.is_file():
                    # Check if file should be excluded
                    relative_path = path.relative_to(root_dir)
                    parent_parts = relative_path.parent.parts

                    # Skip if in excluded folders
                    if any(part in excluded_folders for part in parent_parts):
                        continue

                    # Skip if matches excluded files
                    if path.name in excluded_files:
                        continue

                    total += 1
            return total
        except Exception as e:
            logger.error(f"Error counting files: {e}")
            return 0

    def _start_file_estimator(
        self,
        root_dir: Path,
        excluded_folders: set,
        excluded_files: set,
        exclude_patterns: List[str],
    ) -> None:
        """Start a background thread that estimates the total number of files."""

        if self._estimator_thread and self._estimator_thread.is_alive():
            return

        self._estimator_stop.clear()

        def estimator():
            estimated_total = 0
            try:
                for path in root_dir.rglob('*'):
                    if self._stop_requested or self._estimator_stop.is_set():
                        break

                    if not path.is_file():
                        continue

                    try:
                        relative_path = path.relative_to(root_dir)
                    except ValueError:
                        # If relative path can't be determined, skip estimation for this entry
                        continue

                    parent_parts = relative_path.parent.parts

                    if any(part in excluded_folders for part in parent_parts):
                        continue

                    if path.name in excluded_files:
                        continue

                    relative_str = str(relative_path)
                    if any(fnmatch.fnmatch(relative_str, pattern) for pattern in exclude_patterns):
                        continue

                    estimated_total += 1

                    if estimated_total % 25 == 0:
                        self._update_total_estimate(estimated_total)

                self._update_total_estimate(estimated_total)
            except Exception as exc:
                logger.debug(f"File estimation failed: {exc}", exc_info=True)

        self._estimator_thread = threading.Thread(
            target=estimator,
            name="AnalyzerFileEstimator",
            daemon=True,
        )
        self._estimator_thread.start()

    def _stop_file_estimator(self, wait: bool = False) -> None:
        """Stop the background estimator thread."""

        self._estimator_stop.set()

        if self._estimator_thread and self._estimator_thread.is_alive():
            if wait:
                self._estimator_thread.join(timeout=5)
        self._estimator_thread = None

    def _update_total_estimate(self, total: int) -> None:
        """Update the estimated total file count and emit progress."""

        if total <= self.total_files:
            return

        self.total_files = total
        self.progress.emit(self.processed_files, self.total_files)

    def _update_progress(self, current: int, total: int):
        """Update progress and emit signals."""

        adjusted_total = max(total, current, self.total_files)
        self.processed_files = current
        self.total_files = adjusted_total
        self.progress.emit(current, adjusted_total)
        self.fileProcessed.emit(current)

    def _emit_status(self, message: str) -> None:
        self.status.emit(message)

    def _emit_error(self, message: str) -> None:
        self.error.emit(message)

    async def run(self):
        """Main worker execution method executed via asyncio."""
        results: Optional[Dict[str, Any]] = None
        try:
            self._loop = asyncio.get_running_loop()
            self._cancellation.reset()
            self._stop_requested = False

            self._emit_status("Initializing analysis...")

            if not self._validate_config():
                return

            repo_config = self.config.get('repository', {})
            filters_config = self.config.get('filters', {})
            output_config = self.config.get('output', {})

            root_dir = Path(repo_config.get('repository_path'))
            if not root_dir.exists():
                raise FileNotFoundError(f"Repository path does not exist: {root_dir}")

            config_manager = UnifiedConfigManager()
            config = config_manager.get_active_profile_config()
            analysis_cfg = config.get("analysis", {})
            cache_disabled_setting = not bool(analysis_cfg.get("cache_enabled", True))
            set_cache_disabled(cache_disabled_setting)
            cache_disabled = is_cache_disabled()
            logger.debug(f"Cache disabled setting: {cache_disabled}")

            hash_algorithm = None if cache_disabled else repo_config.get('hash_algorithm', 'xxhash')
            logger.debug(f"Using hash algorithm: {hash_algorithm}")

            analysis_params: Dict[str, Any] = {
                'root_dir': root_dir,
                'max_file_size': repo_config.get('max_file_size', 50) * 1024 * 1024,
                'include_binary': repo_config.get('include_binary', False),
                'excluded_folders': set(filters_config.get('excluded_folders', [])),
                'excluded_files': set(filters_config.get('excluded_files', [])),
                'follow_symlinks': repo_config.get('follow_symlinks', False),
                'image_extensions': set(repo_config.get('image_extensions', [])),
                'exclude_patterns': filters_config.get('exclude_patterns', []),
                'threads': repo_config.get('thread_count', 4),
                'encoding': repo_config.get('encoding'),
                'hash_algorithm': hash_algorithm,
                'cancellation_token': self._cancellation.token,
            }

            self.processed_files = 0
            self.total_files = 0
            self._update_progress(0, 0)

            self._start_file_estimator(
                root_dir,
                analysis_params['excluded_folders'],
                analysis_params['excluded_files'],
                analysis_params.get('exclude_patterns') or [],
            )

            output_format = self._map_format_name(output_config.get('format', 'json'))
            is_streaming_format = output_format in ['jsonl']
            use_streaming = output_config.get('streaming', True) or is_streaming_format

            try:
                if use_streaming:
                    results = await self._run_streaming_analysis_async(analysis_params, output_config)
                else:
                    results = await self._run_standard_analysis_async(analysis_params, output_config)
            except asyncio.CancelledError:
                logger.info("Analysis task cancelled")
                self._stop_requested = True
                raise

            if self._stop_requested:
                progress_percent = int((self.processed_files / self.total_files) * 100) if self.total_files > 0 else 0
                status_msg = f"Analysis stopped at {progress_percent}% ({self.processed_files} of {self.total_files} files)"
                self._emit_status(status_msg)
                results = self._finalize_stop_summary(results)
            else:
                self._emit_status("Analysis completed")

            if results is None:
                results = {}

            if not cache_disabled:
                self._emit_status("Checking cache size...")
                cache_cfg = config.get("cache", {})
                cache_path_setting = cache_cfg.get("path") or str(Path.cwd() / ".cache")
                thread_count = repo_config.get('thread_count', 4)
                await asyncio.to_thread(
                    self._post_analysis_cache_maintenance,
                    cache_path_setting,
                    thread_count,
                )

            self.finished.emit(results)
            return results

        except asyncio.CancelledError:
            self._emit_status("Analysis cancelled by user")
            results = self._finalize_stop_summary(results)
            self.finished.emit(results)
            raise
        except Exception as e:
            logger.error(f"Worker initialization error: {e}", exc_info=True)
            self._emit_error(f"Failed to initialize analysis: {str(e)}")
            raise
        finally:
            self._stop_file_estimator()

    def _finalize_stop_summary(self, results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Ensure stop metadata is captured in the summary."""
        if results is None:
            results = {}
        if isinstance(results, dict):
            summary = results.setdefault('summary', {})
            summary['stopped_early'] = True
            summary['processed_files'] = self.processed_files
            summary['total_files'] = self.total_files
        return results

    def _validate_config(self) -> bool:
        """Validate the configuration."""
        try:
            if not self.config:
                raise ValueError("Configuration is empty")
            
            repo_config = self.config.get('repository')
            if not repo_config:
                raise ValueError("Repository configuration is missing")
            
            repo_path = repo_config.get('repository_path')
            if not repo_path:
                raise ValueError("Repository path is required")
            
            # Check output configuration
            output_config = self.config.get('output')
            if not output_config:
                raise ValueError("Output configuration is missing")
            
            output_format = output_config.get('format')
            if not output_format:
                raise ValueError("Output format is required")
            
            return True
            
        except Exception as e:
            self._emit_error(f"Configuration error: {str(e)}")
            return False

    async def _run_standard_analysis_async(
        self,
        params: Dict[str, Any],
        output_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run analysis in standard mode using asynchronous helpers."""
        self._emit_status("Analyzing repository structure...")

        def progress_callback(current: int) -> None:
            estimated_total = max(self.total_files, current)
            self._update_progress(current, estimated_total)

        local_params = dict(params)
        local_params['progress_callback'] = progress_callback
        local_params['cancellation_token'] = self._cancellation.token

        structure, summary = await get_directory_structure_async(**local_params)

        if not self._stop_requested:
            final_count = summary.get('included_files', 0)
            estimated_total = max(self.total_files, final_count)
            self._update_progress(final_count, estimated_total)

        results = {
            "structure": structure,
            "summary": {
                **summary,
                "estimated_total_files": max(
                    self.total_files,
                    summary.get('total_files', summary.get('included_files', 0))
                )
            }
        }

        output_format = self._map_format_name(output_config.get('format', 'json'))
        output_path = output_config.get('output_path')
        if not self._stop_requested and output_path:
            payload: Dict[str, Any] | Dict[str, Any] = results
            if not output_config.get('include_summary', True):
                payload = {"structure": results.get("structure", {})}
            self._emit_status(f"Writing output in {output_format} format...")
            await asyncio.to_thread(self._write_output_sync, payload, output_config)
            self._emit_status(f"Results written to {output_path}")

        return results

    async def _run_streaming_analysis_async(
        self,
        params: Dict[str, Any],
        output_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run analysis in streaming mode without blocking the event loop."""
        self._emit_status("Running streaming analysis...")

        root_dir: Optional[Path] = params.get('root_dir')
        structure: Dict[str, Any] = {}
        summary: Dict[str, Any] = {}
        failed_files: List[Dict[str, str]] = []
        included_files = 0
        last_status_update = 0.0
        summary_received = False

        local_params = dict(params)
        local_params['cancellation_token'] = self._cancellation.token

        stream = get_directory_structure_stream_async(**local_params)

        output_path = output_config.get('output_path')
        output_format = self._map_format_name(output_config.get('format', 'json'))
        include_summary = output_config.get('include_summary', True)

        stream_entries: List[Dict[str, Any]] = [] if output_path else []

        async for entry in stream:
            if self._stop_requested:
                break

            if "summary" in entry:
                summary.update(entry["summary"])
                summary_received = True
                if output_path and include_summary:
                    stream_entries.append(entry)
                continue

            parent = entry.get("parent", "")
            filename = entry.get("filename", "")
            info = entry.get("info", {})

            if info.get("type") == "error":
                failed_files.append({
                    "file": str(Path(parent) / filename),
                    "error": info.get("content", "Unknown error"),
                })
            else:
                included_files += 1
                estimated_total = max(self.total_files, included_files)
                self._update_progress(included_files, estimated_total)

                now = time.monotonic()
                if now - last_status_update >= 0.5:
                    display_name = filename or (
                        parent if parent else (root_dir.name if isinstance(root_dir, Path) else "")
                    )
                    self._emit_status(
                        f"Processed {included_files} files (latest: {display_name})"
                    )
                    last_status_update = now

            current = structure
            if parent:
                for part in Path(parent).parts:
                    current = current.setdefault(part, {})
            current[filename] = info

            if output_path:
                stream_entries.append(entry)

        if not summary_received:
            summary.update({
                "included_files": included_files,
                "failed_files": failed_files,
            })

        summary.setdefault("included_files", included_files)
        summary.setdefault("processed_files", included_files)
        summary.setdefault("failed_files", failed_files)
        summary.setdefault("excluded_files", summary.get("excluded_files", 0))
        summary["stopped_early"] = self._stop_requested
        summary.setdefault("total_files", summary.get("included_files", included_files))
        summary.setdefault(
            "estimated_total_files",
            max(self.total_files, summary.get("total_files", included_files)),
        )

        results = {
            "structure": structure,
            "summary": summary,
        }

        if output_path:
            if include_summary and not summary_received:
                stream_entries.append({"summary": summary})

            entries_for_output = (
                stream_entries
                if include_summary
                else [entry for entry in stream_entries if "summary" not in entry]
            )

            def entry_iterator() -> Generator[Dict[str, Any], None, None]:
                for item in entries_for_output:
                    yield item

            self._emit_status(f"Writing output in {output_format} format...")
            await asyncio.to_thread(self._write_output_sync, entry_iterator(), output_config)
            self._emit_status(f"Results written to {output_path}")

        return results

    def _write_output_sync(
        self,
        results: Dict[str, Any] | Generator[Dict[str, Any], None, None],
        output_config: Dict[str, Any],
    ) -> None:
        """Synchronously write analysis results to disk."""
        output_format = self._map_format_name(output_config.get('format', 'json'))
        output_path = output_config.get('output_path')

        if not output_path:
            return

        formatter_config = {
            'pretty_print': output_config.get('pretty_print', True),
            'use_compression': output_config.get('use_compression', False),
        }

        streaming = isinstance(results, Generator) or output_format == 'jsonl'
        output_func = OutputFactory.get_output(
            output_format,
            streaming=streaming,
            config=formatter_config,
        )
        output_func(results, output_path)

    def stop(self):
        """Stop the analysis"""
        self._stop_requested = True
        self._cancellation.cancel()
        self._stop_file_estimator()
