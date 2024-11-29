# samuraizer/gui/widgets/configuration/analysis_options.py

import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PyQt6.QtCore import QSettings, Qt

from pathlib import Path

from ..github_integration.repository_selection import RepositorySelectionWidget
from .analysis_settings.analysis_configuration import AnalysisConfigurationWidget
from .analysis_settings.threading_options import ThreadingOptionsWidget

logger = logging.getLogger(__name__)

class AnalysisOptionsWidget(QWidget):
    """Main widget for configuring analysis options."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.initUI()
        self.loadSettings()

    def initUI(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to maximize space

        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # Allow the widget to resize
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create a container widget for the scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        # Repository Selection
        self.repository_widget = RepositorySelectionWidget()
        self.repository_widget.pathChanged.connect(self.onPathChanged)
        layout.addWidget(self.repository_widget)

        # Analysis Configuration
        self.analysis_config_widget = AnalysisConfigurationWidget()
        layout.addWidget(self.analysis_config_widget)

        # Threading Options
        self.threading_options_widget = ThreadingOptionsWidget()
        layout.addWidget(self.threading_options_widget)

        # Add stretch at the end to keep everything aligned at the top
        layout.addStretch()

        # Set the container as the scroll area's widget
        scroll_area.setWidget(container)
        
        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)

    def onPathChanged(self, path):
        """Handle repository path changes."""
        self.settings.setValue("analysis/last_repository", path)

    def loadSettings(self):
        """Load saved settings."""
        try:
            # Load last used repository
            last_repo = self.settings.value("analysis/last_repository", "")
            if last_repo:
                self.repository_widget.set_repository_path(last_repo)

            # Load other settings with defaults
            self.analysis_config_widget.max_size.setValue(
                int(self.settings.value("analysis/max_file_size", 50))
            )
            self.analysis_config_widget.include_binary.setChecked(
                self.settings.value("analysis/include_binary", False, type=bool)
            )
            self.analysis_config_widget.follow_symlinks.setChecked(
                self.settings.value("analysis/follow_symlinks", False, type=bool)
            )
            self.analysis_config_widget.encoding.setCurrentText(
                self.settings.value("analysis/encoding", "auto")
            )
            self.threading_options_widget.thread_count.setValue(
                int(self.settings.value("analysis/thread_count", 4))
            )

        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)

    def saveSettings(self):
        """Save current settings."""
        try:
            self.settings.setValue("analysis/max_file_size", self.analysis_config_widget.max_size.value())
            self.settings.setValue("analysis/include_binary", self.analysis_config_widget.include_binary.isChecked())
            self.settings.setValue("analysis/follow_symlinks", self.analysis_config_widget.follow_symlinks.isChecked())
            self.settings.setValue("analysis/encoding", self.analysis_config_widget.encoding.currentText())
            self.settings.setValue("analysis/thread_count", self.threading_options_widget.thread_count.value())
            
            # Remove old pool_size setting if it exists
            self.settings.remove("analysis/pool_size")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)

    def validateInputs(self) -> bool:
        """Validate the analysis options."""
        repo_path = self.repository_widget.get_repository_path().strip()
        if not repo_path:
            return False
        if not Path(repo_path).exists():
            return False
        return True

    def get_configuration(self) -> dict:
        """Get the current configuration as a dictionary."""
        return {
            'repository_path': self.repository_widget.get_repository_path(),
            'max_file_size': self.analysis_config_widget.max_size.value(),
            'include_binary': self.analysis_config_widget.include_binary.isChecked(),
            'follow_symlinks': self.analysis_config_widget.follow_symlinks.isChecked(),
            'encoding': None if self.analysis_config_widget.encoding.currentText() == "auto" else self.analysis_config_widget.encoding.currentText(),
            'thread_count': self.threading_options_widget.thread_count.value(),
        }
