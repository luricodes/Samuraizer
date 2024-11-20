# samuraizer/gui/widgets/configuration/repository/github/widgets/status_widget.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

class StatusWidget(QWidget):
    """Widget for displaying GitHub clone operation status and progress."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Status message label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setWordWrap(True)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.hide()
        
        # Repository info label
        self.repo_info_label = QLabel()
        self.repo_info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.repo_info_label.setWordWrap(True)
        self.repo_info_label.hide()
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.repo_info_label)
        
    def update_status(self, message: str, show_progress: bool = False):
        """Update the status message and progress bar visibility."""
        self.status_label.setText(message)
        
        if show_progress:
            self.progress_bar.show()
            # Reset progress bar
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.hide()
            
    def update_progress(self, value: int):
        """Update the progress bar value."""
        self.progress_bar.setValue(value)
        
    def update_repo_info(self, info: str):
        """Update repository information."""
        self.repo_info_label.setText(info)
        self.repo_info_label.show()
        
    def clear(self):
        """Clear all displayed information."""
        self.status_label.clear()
        self.progress_bar.hide()
        self.repo_info_label.clear()
        self.repo_info_label.hide()
