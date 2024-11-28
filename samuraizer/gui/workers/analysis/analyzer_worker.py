import logging
from typing import Dict, Any, Optional, Generator
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from samuraizer.backend.services.event_service.events import shutdown_event
from samuraizer.backend.analysis.traversal.traversal_processor import get_directory_structure
from samuraizer.backend.analysis.traversal.traversal_stream import get_directory_structure_stream
from samuraizer.backend.output.factory.output_factory import OutputFactory
from samuraizer.backend.cache.cache_cleaner import check_and_vacuum_if_needed
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from samuraizer.backend.cache.connection_pool import initialize_connection_pool


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

    def _update_progress(self, current: int, total: int):
        """Update progress and emit signals."""
        self.processed_files = current
        self.progress.emit(current, total)
        self.fileProcessed.emit(current)

    def run(self):
        """Main worker execution method."""
        try:
            # Ensure shutdown_event is cleared at the start of a new analysis
            shutdown_event.clear()
            self._stop_requested = False
            
            self.status.emit("Initializing analysis...")
            
            # Validate configuration
            if not self._validate_config():
                return
            
            # Extract configuration
            repo_config = self.config.get('repository', {})
            filters_config = self.config.get('filters', {})
            output_config = self.config.get('output', {})
            
            # Set up path and basic parameters
            root_dir = Path(repo_config.get('repository_path'))
            if not root_dir.exists():
                raise FileNotFoundError(f"Repository path does not exist: {root_dir}")
            
            # Check if cache is disabled in settings
            settings = QSettings()
            cache_disabled = settings.value("settings/disable_cache", False, type=bool)
            logger.debug(f"Cache disabled setting: {cache_disabled}")
            
            # Get hash algorithm from config, defaulting to xxhash if caching is enabled
            hash_algorithm = None if cache_disabled else repo_config.get('hash_algorithm', 'xxhash')
            logger.debug(f"Using hash algorithm: {hash_algorithm}")
            
            # Configure analysis parameters
            analysis_params = {
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
                'hash_algorithm': hash_algorithm,  # Use the determined hash_algorithm
            }

            # Count total files before starting analysis
            self.status.emit("Counting files...")
            self.total_files = self._count_files(
                root_dir,
                analysis_params['excluded_folders'],
                analysis_params['excluded_files']
            )
            if self._stop_requested:
                self.status.emit("Analysis cancelled during file counting")
                return

            # Initialize progress tracking
            self.processed_files = 0
            self._update_progress(0, self.total_files)
            self.status.emit("Starting analysis...")
            
            results = None
            try:
                output_format = self._map_format_name(output_config.get('format', 'json'))
                is_streaming_format = output_format in ['jsonl']
                
                if output_config.get('streaming', False) or is_streaming_format:
                    # Get both the generator for output and collected results for GUI
                    generator, results = self._run_streaming_analysis(analysis_params)
                    
                    # Process output if needed
                    output_path = output_config.get('output_path')
                    if not self._stop_requested and output_path:
                        # Remove summary if not included
                        if not output_config.get('include_summary', True):
                            generator = (entry for entry in generator if "summary" not in entry)
                        self._write_output(generator, output_config)
                else:
                    results = self._run_standard_analysis(analysis_params)
                    
                    # Process output if needed
                    output_path = output_config.get('output_path')
                    if not self._stop_requested and output_path:
                        # Remove summary if not included
                        if not output_config.get('include_summary', True) and isinstance(results, dict):
                            results = {"structure": results.get("structure", {})}
                        self._write_output(results, output_config)
                
                if self._stop_requested:
                    # Update status with progress information
                    progress_percent = int((self.processed_files / self.total_files) * 100) if self.total_files > 0 else 0
                    status_msg = f"Analysis stopped at {progress_percent}% ({self.processed_files} of {self.total_files} files)"
                    self.status.emit(status_msg)
                    
                    # Ensure the results include the stopped_early flag
                    if results and isinstance(results, dict):
                        if 'summary' not in results:
                            results['summary'] = {}
                        results['summary']['stopped_early'] = True
                        results['summary']['processed_files'] = self.processed_files
                        results['summary']['total_files'] = self.total_files
                else:
                    self.status.emit("Analysis completed")

                # Check cache size after analysis if cache is enabled
                if not cache_disabled:
                    self.status.emit("Checking cache size...")
                    cache_path = settings.value("settings/cache_path", "")
                    if not cache_path:
                        cache_path = str(Path.cwd() / ".cache")
                    db_path = Path(cache_path) / CACHE_DB_FILE
                    check_and_vacuum_if_needed(db_path)
                    
                    # Reinitialize connection pool with current thread count
                    thread_count = repo_config.get('thread_count', 4)
                    initialize_connection_pool(str(db_path), thread_count)
                
                # Emit results even if stopped
                self.finished.emit(results)
                
            except Exception as e:
                logger.error(f"Analysis error: {e}", exc_info=True)
                self.error.emit(f"Analysis failed: {str(e)}")
                return
                
        except Exception as e:
            logger.error(f"Worker initialization error: {e}", exc_info=True)
            self.error.emit(f"Failed to initialize analysis: {str(e)}")
        finally:
            # Clean up resources
            shutdown_event.clear()

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
            self.error.emit(f"Configuration error: {str(e)}")
            return False

    def _run_standard_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run analysis in standard mode"""
        self.status.emit("Analyzing repository structure...")
        
        try:
            # Create a progress callback
            def progress_callback(current: int):
                self._update_progress(current, self.total_files)
            
            # Add progress callback to params
            params['progress_callback'] = progress_callback
            
            structure, summary = get_directory_structure(**params)
            
            # Ensure final progress is updated
            if not self._stop_requested:
                self._update_progress(summary.get('included_files', 0), self.total_files)
            
            return {
                "structure": structure,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Error in standard analysis: {e}", exc_info=True)
            raise

    def _run_streaming_analysis(self, params: Dict[str, Any]) -> tuple[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """Run analysis in streaming mode"""
        self.status.emit("Running streaming analysis...")
        
        file_count = 0
        structure = {}
        summary = {}
        failed_files = []
        included_files = 0
        excluded_files = 0
        
        try:
            # Create base generator
            base_generator = get_directory_structure_stream(**params)
            
            # Create a new generator that collects results while yielding
            def collecting_generator():
                nonlocal file_count, structure, summary, failed_files, included_files, excluded_files
                
                for entry in base_generator:
                    if self._stop_requested:
                        break

                    if "summary" in entry:
                        # Store the summary
                        summary.update(entry["summary"])
                    else:
                        # Update structure
                        parent = entry.get("parent", "")
                        filename = entry.get("filename", "")
                        info = entry.get("info", {})
                        
                        # Track file statistics
                        if info.get("type") == "error":
                            failed_files.append({
                                "file": str(Path(parent) / filename),
                                "error": info.get("content", "Unknown error")
                            })
                        else:
                            included_files += 1
                            # Update progress with actual count and total
                            self._update_progress(included_files, self.total_files)
                        
                        # Build structure
                        current = structure
                        if parent:
                            for part in Path(parent).parts:
                                current = current.setdefault(part, {})
                        current[filename] = info
                        
                        # Update file count
                        file_count += 1
                    
                    # Always yield the entry for streaming output
                    yield entry
                
                # Update final summary
                summary.update({
                    "total_files": included_files + excluded_files,
                    "included_files": included_files,
                    "excluded_files": excluded_files,
                    "excluded_percentage": (excluded_files / (included_files + excluded_files) * 100) if (included_files + excluded_files) > 0 else 0,
                    "failed_files": failed_files,
                    "stopped_early": self._stop_requested,
                    "processed_files": included_files,
                })
            
            # Create the generator and results dictionary
            generator = collecting_generator()
            results = {
                "structure": structure,
                "summary": summary
            }
            
            return generator, results
            
        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            raise

    def _write_output(self, results: Dict[str, Any] | Generator[Dict[str, Any], None, None], output_config: Dict[str, Any]):
        """Write results to output file"""
        try:
            output_format = self._map_format_name(output_config.get('format', 'json'))
            output_path = output_config.get('output_path')
            
            if not output_path:
                return
                
            self.status.emit(f"Writing output in {output_format} format...")
            
            # Create formatter configuration
            formatter_config = {
                'pretty_print': output_config.get('pretty_print', True),
                'use_compression': output_config.get('use_compression', False)
            }
            
            # For JSONL format, ensure we're using streaming mode
            if output_format == 'jsonl' and not isinstance(results, Generator):
                # Convert dictionary results to a generator format
                def dict_to_generator(data: Dict[str, Any]):
                    structure = data.get('structure', {})
                    
                    def process_structure(parent: str, items: Dict[str, Any]):
                        for name, info in items.items():
                            if isinstance(info, dict):
                                if 'type' in info:  # This is a file entry
                                    yield {
                                        'parent': parent,
                                        'filename': name,
                                        'info': info
                                    }
                                else:  # This is a directory
                                    yield from process_structure(
                                        str(Path(parent) / name) if parent else name,
                                        info
                                    )
                    
                    # First yield all file entries
                    yield from process_structure('', structure)
                    
                    # Then yield summary if it exists
                    if 'summary' in data:
                        yield {'summary': data['summary']}
                
                results = dict_to_generator(results)
            
            # Get output function with configuration
            output_func = OutputFactory.get_output(
                output_format,
                streaming=isinstance(results, Generator) or output_format == 'jsonl',
                config=formatter_config
            )
            
            # Write output
            output_func(results, output_path)
            
            self.status.emit(f"Results written to {output_path}")
            
        except Exception as e:
            logger.error(f"Error writing output: {e}", exc_info=True)
            self.error.emit(f"Failed to write output: {str(e)}")

    def stop(self):
        """Stop the analysis"""
        self._stop_requested = True
        shutdown_event.set()
