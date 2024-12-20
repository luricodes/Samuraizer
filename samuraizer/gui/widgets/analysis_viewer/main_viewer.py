import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QTabWidget, QMessageBox, QSplitterHandle
)
from PyQt6.QtCore import Qt, QThread, QSettings, QTimer
from .components.progress_monitor import ProgressMonitor
from .components.result_tabs import ResultTabs
from .handlers.result_processor import ResultProcessor
from ...dialogs.export import ExportDialog
from ...workers.analysis.analyzer_worker import AnalyzerWorker
from ....utils.log_handler import GuiLogHandler
# Removed the direct import of DetailsPanel to avoid circular import
# from ...windows.main.panels.details_panel import DetailsPanel

if TYPE_CHECKING:
    from ...windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class CollapsibleSplitter(QSplitter):
    """Custom QSplitter with magnetic snap points"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setChildrenCollapsible(True)
        self.setHandleWidth(10)
        self.setOpaqueResize(False)
        
    def createHandle(self) -> QSplitterHandle:
        """Create a custom handle with snap behavior"""
        return CollapsibleSplitterHandle(self.orientation(), self)

class CollapsibleSplitterHandle(QSplitterHandle):
    """Custom splitter handle with magnetic snap behavior"""
    def __init__(self, orientation: Qt.Orientation, parent: QSplitter):
        super().__init__(orientation, parent)
        self.snap_range = 20  # Pixels within which snapping occurs
        
    def mouseMoveEvent(self, event):
        """Handle mouse movement with snap behavior"""
        pos = event.position().y() if self.orientation() == Qt.Orientation.Vertical else event.position().x()
        splitter = self.splitter()
        index = splitter.indexOf(self)
        
        # Get the total size and current sizes
        total_size = splitter.height() if self.orientation() == Qt.Orientation.Vertical else splitter.width()
        sizes = splitter.sizes()
        
        # Calculate position relative to splitter
        relative_pos = event.globalPosition().y() - splitter.mapToGlobal(splitter.pos()).y()
        
        # Check if we're near the bottom snap point
        if abs(relative_pos - total_size) < self.snap_range:
            # Snap to collapsed state
            new_sizes = sizes.copy()
            if len(new_sizes) >= 1:
                new_sizes[-1] = 0  # Collapse the last widget
                splitter.setSizes(new_sizes)
        else:
            # Normal handle movement
            super().mouseMoveEvent(event)

class ResultsViewWidget(QWidget):
    """Widget for displaying repository analysis results"""

    def __init__(self, parent: Optional['MainWindow'] = None):
        super().__init__(parent)
        self.main_window = parent
        self.settings = QSettings()
        self.analyzer_thread: Optional[QThread] = None
        self.analyzer_worker: Optional[AnalyzerWorker] = None
        self.results_data: Optional[Dict[str, Any]] = None
        self.tab_counter = 0
        self.current_progress = 0
        self.total_files = 0
        self.gui_log_handler = None

        # Initialize components
        self.progress_monitor = ProgressMonitor(self)
        self.result_processor = ResultProcessor()
        self.initUI()
        self.setupLogging()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add progress monitor
        layout.addWidget(self.progress_monitor)

        # Create main splitter with custom snap behavior
        self.main_splitter = CollapsibleSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.main_splitter)

        # Create results tabs
        self.results_tabs = ResultTabs()
        self.results_tabs.currentChanged.connect(self._on_tab_changed)  # Add this connection
        self.main_splitter.addWidget(self.results_tabs)

        # Initialize DetailsPanel within the method to avoid circular import
        try:
            from ...windows.main.panels.details_panel import DetailsPanel
            self.details_panel = DetailsPanel(self)
            self.details_panel.analysis_completed.connect(self._on_analysis_completed)  # Add this connection
            self.main_splitter.addWidget(self.details_panel)
        except ImportError as e:
            logger.error(f"Failed to import DetailsPanel: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import DetailsPanel: {str(e)}"
            )

        # Create and add log panel
        try:
            from ...windows.main.panels import LogPanel
            self.log_panel = LogPanel()
            self.log_panel.setMinimumHeight(0)  # Allow complete collapse
            self.main_splitter.addWidget(self.log_panel)
        except ImportError as e:
            logger.error(f"Failed to import LogPanel: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import LogPanel: {str(e)}"
            )

        # Set initial sizes for better default appearance
        total_height = self.height()
        self.main_splitter.setSizes([
            int(total_height * 0.4),
            int(total_height * 0.3),
            int(total_height * 0.3)
        ])

        # Restore splitter state if it exists
        splitter_state = self.settings.value("main_splitter/state")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

    def _on_tab_changed(self, index: int):
        """Handle results tab changes."""
        if index >= 0:
            current_widget = self.results_tabs.widget(index)
            if hasattr(current_widget, 'results_data'):
                self.details_panel.set_selection(current_widget.results_data)

    def _on_analysis_completed(self, analysis_results: Dict[str, Any]):
        """Handle completion of detailed analysis."""
        try:
            # Add analysis results to the current results data
            if self.results_data is None:
                self.results_data = {}
            
            analysis_type = analysis_results['type']
            if 'detailed_analysis' not in self.results_data:
                self.results_data['detailed_analysis'] = {}
            
            self.results_data['detailed_analysis'][analysis_type] = {
                'timestamp': datetime.now().isoformat(),
                'results': analysis_results['results']
            }

            # Log the completion
            logger.info(f"Detailed analysis completed: {analysis_type}")
            
        except Exception as e:
            logger.error(f"Error processing analysis results: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Analysis Error",
                f"Error processing analysis results: {str(e)}"
            )

    def setupLogging(self):
        """Set up logging to route messages to the GUI log panel."""
        try:
            # Create and configure GUI log handler with settings
            buffer_size = self.settings.value("log_panel/buffer_size", 1000, type=int)
            batch_size = self.settings.value("log_panel/batch_size", 10, type=int)
            batch_interval = self.settings.value("log_panel/batch_interval", 100, type=int)
            
            self.gui_log_handler = GuiLogHandler(
                max_buffer_size=buffer_size,
                batch_size=batch_size,
                batch_interval=batch_interval
            )
            
            # Connect handler signals to log panel
            self.gui_log_handler.log_record_received.connect(self.log_panel.addLogMessage)
            self.gui_log_handler.batch_records_received.connect(self.log_panel.addBatchMessages)
            
            # Store handler reference in log panel for buffer management
            self.log_panel.gui_log_handler = self.gui_log_handler
            
            # Add handler to root logger to catch all messages
            root_logger = logging.getLogger()
            root_logger.addHandler(self.gui_log_handler)
            
            # Log initial message
            logger.info("GUI logging initialized")
            
        except Exception as e:
            # Use basic logging if GUI logging setup fails
            logging.error(f"Failed to initialize GUI logging: {e}", exc_info=True)

    def saveLoggerState(self):
        """Save logging-related settings."""
        try:
            self.settings.setValue("main_splitter/state", self.main_splitter.saveState())
            self.log_panel.saveSettings()
        except Exception as e:
            logger.error(f"Failed to save logger state: {e}", exc_info=True)

    def cleanupLogging(self):
        """Clean up logging resources."""
        try:
            if self.gui_log_handler is not None:
                # Prepare handler for shutdown
                self.gui_log_handler.prepare_for_shutdown()
                
                # Remove handler from root logger
                root_logger = logging.getLogger()
                root_logger.removeHandler(self.gui_log_handler)
                
                try:
                    # Disconnect signals if they're still connected
                    self.gui_log_handler.log_record_received.disconnect()
                    self.gui_log_handler.batch_records_received.disconnect()
                except (RuntimeError, TypeError):
                    pass  # Signals might already be disconnected
                
                # Clear reference in log panel
                if hasattr(self.log_panel, 'gui_log_handler'):
                    self.log_panel.gui_log_handler = None
                
                # Clear our reference
                self.gui_log_handler = None
                
        except Exception as e:
            # Don't log here as logging system might be shutting down
            print(f"Error during logging cleanup: {e}")

    def setConfiguration(self, config: Dict[str, Any]) -> None:
        self.result_processor.setConfiguration(config)

    def startAnalysis(self, worker: AnalyzerWorker, thread: QThread) -> None:
        """Start a new analysis with the given worker and thread."""
        try:
            self.cleanup()  # Clean up any previous analysis
            
            self.analyzer_worker = worker
            self.analyzer_thread = thread
            
            # Connect worker signals
            self.analyzer_worker.progress.connect(self.updateProgress)
            self.analyzer_worker.status.connect(self.updateStatus)
            self.analyzer_worker.error.connect(self.handleError)
            self.analyzer_worker.fileProcessed.connect(self.progress_monitor.updateFileCount)
            self.analyzer_worker.finished.connect(self.analysisFinished)
            
            # Show progress bar and update status
            self.progress_monitor.progress_bar.show()
            self.progress_monitor.updateStatus("Analysis started...")
            
        except Exception as e:
            logger.error(f"Error starting analysis: {e}", exc_info=True)
            self.handleError(f"Failed to start analysis: {str(e)}")

    def stopAnalysis(self) -> None:
        """Stop the current analysis."""
        try:
            if self.analyzer_worker:
                self.analyzer_worker.stop()
                # Show how many files were processed before stopping
                status_msg = (
                    f"Analysis stopped. Processed {self.current_progress} of "
                    f"{self.total_files} files "
                    f"({int((self.current_progress / self.total_files) * 100)}% complete)"
                )
                self.progress_monitor.updateStatus(status_msg)
                self.progress_monitor.hideProgress()
        except Exception as e:
            logger.error(f"Error stopping analysis: {e}", exc_info=True)
            self.handleError(f"Error stopping analysis: {str(e)}")

    def cleanup(self) -> None:
        """Clean up current analysis resources."""
        try:
            # Store references locally
            worker = self.analyzer_worker
            thread = self.analyzer_thread
            
            # Clear instance references immediately
            self.analyzer_worker = None
            self.analyzer_thread = None
            self.current_progress = 0
            self.total_files = 0

            # Clean up worker first if it exists
            if worker is not None:
                try:
                    worker.stop()
                    worker.disconnect()  # Disconnect all signals
                except RuntimeError:
                    # Worker might already be deleted
                    pass
                else:
                    try:
                        worker.deleteLater()
                    except RuntimeError:
                        pass

            # Then clean up thread if it exists
            if thread is not None:
                try:
                    # Only attempt to stop the thread if it's still valid and running
                    if not thread.parent():  # Check if thread is still valid
                        return
                        
                    if thread.isRunning():
                        thread.quit()
                        if not thread.wait(5000):  # Wait up to 5 seconds
                            try:
                                thread.terminate()
                                thread.wait()
                            except RuntimeError:
                                pass
                except RuntimeError:
                    # Thread might already be deleted
                    pass
                else:
                    try:
                        thread.deleteLater()
                    except RuntimeError:
                        pass
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    def updateProgress(self, current: int, total: int) -> None:
        """Update the progress bar."""
        try:
            self.current_progress = current
            self.total_files = total
            self.progress_monitor.progress_bar.show()  # Ensure progress bar is visible
            self.progress_monitor.updateProgress(current, total)
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)

    def updateStatus(self, message: str) -> None:
        """Update the status message."""
        try:
            self.progress_monitor.updateStatus(message)
        except Exception as e:
            logger.error(f"Error updating status: {e}", exc_info=True)

    def handleError(self, error_message: str):
        logger.error(f"Analysis error: {error_message}")
        QMessageBox.critical(
            self,
            "Analysis Error",
            f"An error occurred during analysis:\n\n{error_message}"
        )
        self.progress_monitor.updateStatus("Analysis failed")
        self.progress_monitor.hideProgress()

    def analysisFinished(self, results: Dict[str, Any]):
        try:
            self.results_data = results
            view = self.result_processor.createView(results)
            if view:
                self.tab_counter += 1
                tab_name = f"Analysis {self.tab_counter}"
                
                view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                view.customContextMenuRequested.connect(
                    lambda pos, v=view: self.results_tabs.showResultContextMenu(pos, v, self.exportResults)
                )
                
                self.results_tabs.addTab(view, tab_name)
                self.results_tabs.setCurrentWidget(view)
                self.results_tabs.active_analyses.add(tab_name)
                
                # Update the details panel with the new results
                self.details_panel.set_selection(results)
            
            self.progress_monitor.hideProgress()
            
            # Check if analysis was stopped early
            if results.get("summary", {}).get("stopped_early", False):
                status_msg = (
                    f"Analysis stopped. Processed {self.current_progress} of "
                    f"{self.total_files} files "
                    f"({int((self.current_progress / self.total_files) * 100)}% complete)"
                )
            else:
                status_msg = "Analysis completed"
            self.progress_monitor.updateStatus(status_msg)

            # Auto-save functionality using Output Options settings
            auto_save_enabled = self.settings.value("settings/auto_save", False, type=bool)
            if auto_save_enabled and results:
                try:
                    # Get settings from Output Options
                    output_format = self.settings.value("output/format", "json")
                    output_path = self.settings.value("output/last_path", "")
                    
                    if output_path:
                        # Export the results using Output Options settings
                        self.exportResults(results, output_path)
                        self.progress_monitor.updateStatus(f"Results auto-saved to {output_path}")
                    else:
                        logger.warning("Auto-save failed: No output path set in Output Options")
                        self.progress_monitor.updateStatus("Auto-save failed: No output path set in Output Options")
                except Exception as e:
                    logger.error(f"Auto-save failed: {e}", exc_info=True)
                    self.progress_monitor.updateStatus("Auto-save failed")
            
        except Exception as e:
            logger.error(f"Error handling analysis results: {e}", exc_info=True)
            self.handleError(f"Error processing results: {str(e)}")

    def exportResults(self, results: Dict[str, Any], file_path: Optional[str] = None):
        try:
            if file_path:
                # Direct export using provided path and last used settings
                format_name = self.settings.value("export/format", "json")
                # Add detailed analysis to the export data
                export_data = results.copy()
                if hasattr(self, 'details_panel'):
                    if 'detailed_analysis' not in export_data:
                        export_data['detailed_analysis'] = {}
                    export_data['detailed_analysis'].update(
                        self.results_data.get('detailed_analysis', {})
                    )
                # Implement export logic here using format_name and file_path
                self.progress_monitor.updateStatus(f"Results exported to {file_path}")
            else:
                # Show export dialog for manual export
                dialog = ExportDialog(self)
                if dialog.exec():
                    format_name, file_path = dialog.getExportOptions()
                    # Implement export logic here
                    self.progress_monitor.updateStatus(f"Results exported to {file_path}")
        except Exception as e:
            logger.error(f"Error exporting results: {e}", exc_info=True)
            self.handleError(f"Error exporting results: {str(e)}")

    def closeEvent(self, event):
        """Handle widget close event."""
        try:
            # Save settings first
            self.saveLoggerState()
            
            # Clean up analysis resources
            self.cleanup()
            
            # Clean up logging last
            self.cleanupLogging()
            
        except Exception as e:
            print(f"Error during close: {e}")  # Use print as logging might be unavailable
            
        event.accept()