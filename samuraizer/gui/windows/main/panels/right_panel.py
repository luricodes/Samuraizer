from typing import TYPE_CHECKING, Dict, Any, Optional
import logging
from PyQt6.QtWidgets import QMessageBox
from samuraizer.gui.widgets.analysis_viewer.main_viewer import ResultsViewWidget
from samuraizer.gui.workers.analysis.analyzer_worker import AnalyzerWorker

if TYPE_CHECKING:
    from samuraizer.gui.windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class RightPanel(ResultsViewWidget):
    """Right panel containing analysis results."""
    
    def __init__(self, parent: 'MainWindow') -> None:
        """Initialize the right panel.
        
        Args:
            parent: Parent MainWindow instance
        """
        super().__init__(parent)
        self.main_window = parent
        self._configuration: Dict[str, Any] = {}
        self._results: Optional[Dict[str, Any]] = None
        
        # Ensure progress monitor is properly initialized
        if not hasattr(self, 'progress_monitor'):
            logger.error("Progress monitor not initialized by parent class")
            raise RuntimeError("Progress monitor initialization failed")
    
    def setConfiguration(self, config: Dict[str, Any]) -> None:
        """Set the current configuration.
        
        Args:
            config: Configuration dictionary
        """
        try:
            if not config:
                raise ValueError("Empty configuration provided")
            
            if 'output' not in config:
                raise ValueError("Configuration missing 'output' section")
                
            self._configuration = config.copy()

            # Set configuration on dependent components
            self.result_processor.setConfiguration(config)
            if getattr(self, "details_panel", None) is not None:
                try:
                    self.details_panel.set_configuration(config)
                except Exception as details_error:
                    logger.warning(
                        "Failed to update details panel configuration: %s",
                        details_error,
                        exc_info=True,
                    )
            logger.debug("Configuration set in right panel and result processor")
            
        except Exception as e:
            logger.error(f"Error setting configuration: {e}", exc_info=True)
            raise
    
    def hasConfiguration(self) -> bool:
        """Check if configuration is set.
        
        Returns:
            bool: True if configuration is set
        """
        return bool(self._configuration and self.result_processor.hasConfiguration())
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration.
        
        Returns:
            Dict[str, Any]: Current configuration
            
        Raises:
            ValueError: If no configuration is set
        """
        if not self._configuration:
            raise ValueError("No configuration set")
        return self._configuration.copy()

    def startAnalysis(self, worker: AnalyzerWorker) -> None:
        """Start a new analysis with the given worker.
        
        Args:
            worker: The analyzer worker instance
        """
        try:
            # Clean up any previous analysis
            self.cleanup()
            
            # Store worker instance
            self.analyzer_worker = worker
            
            # Connect worker signals
            self.analyzer_worker.progress.connect(self.updateProgress)
            self.analyzer_worker.status.connect(self.updateStatus)
            self.analyzer_worker.error.connect(self.handleError)
            self.analyzer_worker.fileProcessed.connect(self.updateFileCount)
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
                self.progress_monitor.updateStatus("Analysis stopped")
                self.progress_monitor.hideProgress()
        except Exception as e:
            logger.error(f"Error stopping analysis: {e}", exc_info=True)
            self.handleError(f"Error stopping analysis: {str(e)}")

    def analysisFinished(self, results: Dict[str, Any]) -> None:
        """Handle analysis completion.
        
        Args:
            results: Analysis results to display
        """
        if not results:
            logger.warning("No results to display")
            return
            
        if not self.hasConfiguration():
            logger.error("No configuration set for result display")
            QMessageBox.critical(
                self,
                "Error",
                "Configuration not set for result display"
            )
            return
            
        try:
            self._results = results.copy()
            super().analysisFinished(results)
            logger.info("Analysis results displayed successfully")
            
        except Exception as e:
            error_msg = f"Failed to display analysis results: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Error", error_msg)
            self.progress_monitor.updateStatus("Error displaying results")

    def saveResults(self, results: Optional[Dict[str, Any]] = None) -> None:
        """Save analysis results.
        
        Args:
            results: Results to save, uses stored results if None
            
        Raises:
            ValueError: If no results available or invalid configuration
        """
        try:
            # Use provided results or stored results
            data = results if results is not None else self._results
            if not data:
                raise ValueError("No results to save")
                
            # Validate configuration
            if not self._configuration or 'output' not in self._configuration:
                raise ValueError("No output configuration set")
                
            output_config = self._configuration['output']
            output_path = output_config.get('output_path')
            
            if not output_path:
                raise ValueError("No output path specified")
                
            # Export results
            self.exportResults(data, output_path)
            
            logger.info(f"Results saved to {output_path}")
            self.progress_monitor.updateStatus(f"Results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save results: {str(e)}"
            )
            raise

    def showProgress(self) -> None:
        """Show progress monitoring UI."""
        if hasattr(self, 'progress_monitor'):
            self.progress_monitor.progress_bar.show()
            self.progress_monitor.progress_bar.setValue(0)

    def hideProgress(self) -> None:
        """Hide progress monitoring UI."""
        if hasattr(self, 'progress_monitor'):
            self.progress_monitor.hideProgress()

    def updateProgress(self, current: int, total: int) -> None:
        """Update the progress information.
        
        Args:
            current: Current progress value
            total: Total progress value
        """
        try:
            self.progress_monitor.updateProgress(current, total)
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)

    def updateFileCount(self, count: int) -> None:
        """Update the processed file count.
        
        Args:
            count: Number of processed files
        """
        try:
            self.progress_monitor.updateFileCount(count)
        except Exception as e:
            logger.error(f"Error updating file count: {e}", exc_info=True)
            
    def updateStatus(self, message: str) -> None:
        """Update status message.
        
        Args:
            message: Status message to display
        """
        try:
            self.progress_monitor.updateStatus(message)
        except Exception as e:
            logger.error(f"Error updating status: {e}", exc_info=True)
