from typing import Dict, Any, Optional
import logging
import os
from PyQt6.QtCore import QThread, QSettings
from PyQt6.QtWidgets import QMessageBox
from samuraizer.gui.workers.analysis.analyzer_worker import AnalyzerWorker
from typing import TYPE_CHECKING
from samuraizer.gui.windows.base.window import BaseWindow
from samuraizer.gui.windows.main.panels import RightPanel, LeftPanel
from samuraizer.gui.windows.main.components.ui_state import AnalysisState
from samuraizer.backend.cache.connection_pool import initialize_connection_pool, close_all_connections
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Custom exception for configuration validation errors."""
    pass

class AnalysisManager:
    """Manages analysis-related functionality."""
    
    def __init__(self, parent: 'BaseWindow', left_panel: 'LeftPanel', right_panel: 'RightPanel'):
        self.parent = parent
        self.left_panel = left_panel
        self.right_panel = right_panel
        self.analyzer_thread: Optional[QThread] = None
        self.analyzer_worker: Optional[AnalyzerWorker] = None
        self.current_config: Optional[Dict[str, Any]] = None
        self.results_data: Optional[Dict[str, Any]] = None

    def open_repository(self) -> None:
        """Open a repository for analysis."""
        try:
            # Use the existing repository selection widget to open directory dialog
            repo_widget = self.left_panel.analysis_options.repository_widget
            repo_widget.browseRepository()
            
            # Get the selected path
            repo_path = repo_widget.repo_path.text()
            
            if repo_path:
                # Validate the repository path
                is_valid, error_msg = repo_widget.validate()
                if is_valid:
                    # First emit the pathChanged signal to update UI state
                    repo_widget.pathChanged.emit(repo_path)
                    self.parent.status_bar.showMessage(f"Repository opened: {repo_path}")
                else:
                    self.parent.status_bar.showMessage("Invalid repository path selected")
                    QMessageBox.warning(
                        self.parent,
                        "Invalid Repository",
                        error_msg
                    )
        except Exception as e:
            logger.error(f"Error opening repository: {e}", exc_info=True)
            QMessageBox.critical(self.parent, "Error", f"Failed to open repository: {str(e)}")

    def start_analysis(self) -> None:
        """Start the repository analysis."""
        try:
            if not self._validate_analysis_prerequisites():
                return
            
            # Set configuration
            self.right_panel.setConfiguration(self.current_config)
            
            # Update state and UI
            self.parent.ui_state_manager.set_analysis_state(AnalysisState.RUNNING)
            
            # Setup and start analysis
            self._setup_analysis_worker()
            
            # Start the analysis in the right panel
            self.right_panel.startAnalysis(self.analyzer_worker, self.analyzer_thread)
            
            # Start the thread
            self.analyzer_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting analysis: {e}", exc_info=True)
            QMessageBox.critical(self.parent, "Error", f"Failed to start analysis: {str(e)}")
            self.parent.ui_state_manager.set_analysis_state(AnalysisState.ERROR)

    def stop_analysis(self) -> None:
        """Stop the current analysis."""
        try:
            # Tell the right panel to stop analysis
            self.right_panel.stopAnalysis()
            self.parent.ui_state_manager.set_analysis_state(AnalysisState.IDLE)
            self.parent.status_bar.showMessage("Analysis stopped.")
        except Exception as e:
            logger.error(f"Error stopping analysis: {e}", exc_info=True)
            self.parent.status_bar.showMessage(f"Error stopping analysis: {str(e)}")
            self.parent.ui_state_manager.set_analysis_state(AnalysisState.ERROR)

    def _validate_analysis_prerequisites(self) -> bool:
        """Validate all prerequisites before starting analysis."""
        try:
            # Update configuration first
            self._update_configuration()
                
            # Validate repository path
            repo_path = self.current_config['repository']['repository_path']
            if not repo_path:
                raise ConfigurationError("Repository path is required")
            
            path_obj = Path(repo_path)
            if not path_obj.exists():
                raise ConfigurationError(f"Repository directory does not exist: {repo_path}")
            if not path_obj.is_dir():
                raise ConfigurationError(f"Selected path is not a directory: {repo_path}")
            if not os.access(path_obj, os.R_OK):
                raise ConfigurationError(f"Repository directory is not readable: {repo_path}")
            
            # Validate output path
            output_path = self.current_config['output']['output_path']
            if not output_path:
                raise ConfigurationError("Output path is required")
            
            output_dir = Path(output_path).parent
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ConfigurationError(f"Failed to create output directory: {str(e)}")
            
            if not os.access(output_dir, os.W_OK):
                raise ConfigurationError(f"Output directory is not writable: {output_dir}")
            
            # Check if caching is disabled in settings
            settings = QSettings()
            cache_disabled = settings.value("settings/disable_cache", False, type=bool)
            
            # Only validate cache directory if caching is not disabled
            if not cache_disabled:
                # Get cache path from settings or use default
                cache_path = settings.value("settings/cache_path", "")
                if not cache_path:
                    cache_path = str(Path.cwd() / ".cache")
                
                # Create cache directory if it doesn't exist
                cache_dir = Path(cache_path)
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ConfigurationError(f"Failed to create cache directory: {str(e)}")
                
                # Check if directory is writable
                if not os.access(cache_dir, os.W_OK):
                    raise ConfigurationError(f"Cache directory is not writable: {cache_dir}")
                
                logger.info(f"Cache directory validated: {cache_dir}")
            else:
                logger.info("Cache is disabled, skipping cache validation")
            
            return True
            
        except ConfigurationError as ce:
            QMessageBox.warning(
                self.parent,
                "Configuration Error",
                str(ce) + "\n\nPlease check your settings and try again."
            )
            return False
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Failed to validate analysis setup:\n\n{str(e)}\n\nCheck the logs for more details."
            )
            return False

    def _setup_analysis_worker(self) -> None:
        """Set up the analysis worker and thread."""
        try:
            self._cleanup_previous_analysis()
            
            # Create new worker and thread
            self.analyzer_worker = AnalyzerWorker(self.current_config)
            self.analyzer_thread = QThread()
            self.analyzer_worker.moveToThread(self.analyzer_thread)
            
            # Connect thread signals
            self.analyzer_thread.started.connect(self.analyzer_worker.run)
            self.analyzer_worker.finished.connect(self._on_analysis_finished)
            self.analyzer_worker.error.connect(self._on_analysis_error)
            self.analyzer_thread.finished.connect(self._cleanup_previous_analysis)
            
        except Exception as e:
            logger.error(f"Error setting up worker: {e}", exc_info=True)
            raise

    def _on_analysis_finished(self, results: Dict[str, Any]) -> None:
        """Handle analysis completion."""
        self.results_data = results
        self.parent.ui_state_manager.set_analysis_state(AnalysisState.COMPLETED)
        self.analyzer_thread.quit()

    def _on_analysis_error(self, error_message: str) -> None:
        """Handle analysis error."""
        QMessageBox.critical(
            self.parent,
            "Analysis Error",
            f"An error occurred during analysis:\n\n{error_message}\n\nCheck the logs for more details."
        )
        self.parent.ui_state_manager.set_analysis_state(AnalysisState.ERROR)
        self.analyzer_thread.quit()

    def _cleanup_previous_analysis(self) -> None:
        """Clean up previous analysis resources."""
        try:
            if self.analyzer_thread and self.analyzer_thread.isRunning():
                if self.analyzer_worker:
                    self.analyzer_worker.stop()
                self.analyzer_thread.quit()
                if not self.analyzer_thread.wait(5000):  # Wait up to 5 seconds
                    logger.warning("Thread did not terminate in time, forcing termination")
                    self.analyzer_thread.terminate()
                    self.analyzer_thread.wait()
            
            if self.analyzer_worker:
                self.analyzer_worker.deleteLater()
            if self.analyzer_thread:
                self.analyzer_thread.deleteLater()
                
            self.analyzer_thread = None
            self.analyzer_worker = None
            
        except Exception as e:
            logger.error(f"Error cleaning up analysis: {e}", exc_info=True)

    def cleanup(self) -> None:
        """Cleanup resources when closing the application."""
        self._cleanup_previous_analysis()

    def _update_configuration(self) -> None:
        """Update the current configuration from panels."""
        try:
            if not hasattr(self, 'left_panel'):
                raise ConfigurationError("Left panel not initialized")
                
            # Validate repository path first
            repo_widget = self.left_panel.analysis_options.repository_widget
            is_valid, error_msg = repo_widget.validate()
            if not is_valid:
                raise ConfigurationError(error_msg)
                
            # Get configurations from each panel
            repository_config = self.left_panel.analysis_options.get_configuration()
            filters_config = self.left_panel.file_filters.get_configuration()
            output_config = self.left_panel.output_options.get_configuration()

            # Default image extensions
            image_extensions = {
                '.png', '.jpg', '.jpeg', '.gif', '.bmp',
                '.svg', '.webp', '.tiff', '.ico'
            }
            
            # Create the complete configuration
            self.current_config = {
                'repository': {
                    'repository_path': repository_config['repository_path'],
                    'max_file_size': repository_config.get('max_file_size', 50),
                    'include_binary': repository_config.get('include_binary', False),
                    'follow_symlinks': repository_config.get('follow_symlinks', False),
                    'encoding': repository_config.get('encoding'),
                    'hash_algorithm': repository_config.get('hash_algorithm', 'xxhash'),
                    'thread_count': repository_config.get('thread_count', 4),
                    'image_extensions': list(image_extensions),
                    'cache_path': repository_config.get('cache_path', '.cache')
                },
                'filters': {
                    'excluded_folders': list(filters_config.get('excluded_folders', [])),
                    'excluded_files': list(filters_config.get('excluded_files', [])),
                    'exclude_patterns': filters_config.get('exclude_patterns', [])
                },
                'output': {
                    'format': output_config.get('format', 'json').lower(),
                    'output_path': output_config.get('output_path', ''),
                    'streaming': output_config.get('streaming', False),
                    'include_summary': output_config.get('include_summary', True),
                    'pretty_print': output_config.get('pretty_print', True),
                    'use_compression': output_config.get('use_compression', False)
                }
            }
            
            # Save thread count to settings for connection pool
            settings = QSettings()
            settings.setValue("analysis/thread_count", self.current_config['repository']['thread_count'])
            settings.sync()
            
            logger.debug("Configuration updated successfully")
            
        except ConfigurationError as ce:
            logger.error(f"Configuration error: {ce}")
            raise
        except Exception as e:
            logger.error(f"Error updating configuration: {e}", exc_info=True)
            raise ConfigurationError(f"Failed to update configuration: {str(e)}")
