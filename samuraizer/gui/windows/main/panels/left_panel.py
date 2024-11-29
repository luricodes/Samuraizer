from typing import TYPE_CHECKING, Dict, Any
import logging
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, 
    QPushButton, QTabWidget, QMessageBox
)

from samuraizer.gui.widgets.configuration.analysis_options import AnalysisOptionsWidget
from samuraizer.gui.widgets.configuration.filter_settings.file_filters import FileFiltersWidget
from samuraizer.gui.widgets.configuration.output_settings import OutputOptionsWidget

from typing import TYPE_CHECKING
from samuraizer.gui.windows.main.panels.base import BasePanel
if TYPE_CHECKING:
    from samuraizer.gui.windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class LeftPanel(BasePanel):
    """Left panel containing configuration options."""
    
    def __init__(self, parent: 'MainWindow') -> None:
        super().__init__()
        self.main_window = parent
        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the panel UI."""
        try:
            layout = QVBoxLayout(self)

            # Create configuration tabs
            self.config_tabs = QTabWidget()
            
            # Analysis Options Tab
            self.analysis_options = AnalysisOptionsWidget()
            self.config_tabs.addTab(self.analysis_options, "Analysis Options")

            # Output Options Tab
            self.output_options = OutputOptionsWidget()
            self.config_tabs.addTab(self.output_options, "Output Options")

            # File Filters Tab
            self.file_filters = FileFiltersWidget()
            self.config_tabs.addTab(self.file_filters, "File Filters")

            layout.addWidget(self.config_tabs)

            # Add control buttons
            self.create_control_buttons(layout)
            
        except Exception as e:
            logger.error(f"Error setting up left panel UI: {e}", exc_info=True)
            raise
            
    def create_control_buttons(self, layout: QVBoxLayout) -> None:
        """Create the control buttons panel."""
        try:
            buttons_layout = QHBoxLayout()

            # Analyze button
            self.analyze_btn = QPushButton("Start Analysis")
            self.analyze_btn.clicked.connect(self.main_window.start_analysis)
            self.analyze_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2ecc71;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #27ae60;
                }
            """)

            # Stop button
            self.stop_btn = QPushButton("Stop")
            self.stop_btn.clicked.connect(self.main_window.stop_analysis)
            self.stop_btn.setEnabled(False)
            self.stop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)

            buttons_layout.addWidget(self.analyze_btn)
            buttons_layout.addWidget(self.stop_btn)
            layout.addLayout(buttons_layout)
            
        except Exception as e:
            logger.error(f"Error creating control buttons: {e}", exc_info=True)
            raise

    def validate_inputs(self) -> bool:
        """Validate all input fields."""
        try:
            # Validate repository path and analysis options
            if not self.analysis_options.validateInputs():
                QMessageBox.warning(self, "Validation Error", "Please configure repository path and analysis options correctly")
                return False
                
            # Validate output path
            output_path = self.output_options.output_path.text()
            if not output_path or not self.output_options.validateOutputPath(output_path):
                QMessageBox.warning(self, "Validation Error", "Please specify a valid output path")
                return False
                
            # Validate streaming configuration
            if self.output_options.enable_streaming.isChecked() and not self.output_options.isStreamingSupported():
                QMessageBox.warning(self, "Validation Error", "Streaming is not supported for the selected format")
                return False
                
            # Validate file filters (if any custom validation needed)
            try:
                self.file_filters.getConfiguration()
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid file filters: {str(e)}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating inputs: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error validating configuration: {str(e)}")
            return False

    def getConfiguration(self) -> Dict[str, Any]:
        """Get the complete configuration from all widgets."""
        try:
            if not self.validate_inputs():
                raise ValueError("Invalid configuration")
                
            return {
                'analysis': self.analysis_options.getConfiguration(),
                'output': self.output_options.getConfiguration(),
                'filters': self.file_filters.getConfiguration()
            }
        except Exception as e:
            logger.error(f"Error getting configuration: {e}", exc_info=True)
            raise