# samuraizer/gui/widgets/configuration/repository/repository_selection.py

from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, 
    QPushButton, QFileDialog, QGroupBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from samuraizer.backend.services.logging.logging_service import setup_logging
from .github.github_widget import GitHubWidget

logger = logging.getLogger(__name__)

class RepositorySelectionWidget(QWidget):
    """Widget for selecting the repository directory or GitHub repository."""
    
    pathChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Local repository tab
        local_widget = QWidget()
        local_layout = QHBoxLayout(local_widget)
        
        # Repository path input
        self.repo_path = QLineEdit()
        self.repo_path.setPlaceholderText("Select repository directory...")
        self.repo_path.textChanged.connect(self.onPathChanged)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browseRepository)
        browse_btn.setMaximumWidth(100)
        
        local_layout.addWidget(self.repo_path)
        local_layout.addWidget(browse_btn)
        
        # GitHub repository tab
        self.github_widget = GitHubWidget()
        self.github_widget.repository_cloned.connect(self.onGitHubRepoCloned)
        
        # Add tabs
        self.tab_widget.addTab(local_widget, "Local Repository")
        self.tab_widget.addTab(self.github_widget, "GitHub Repository")
        
        # Add tab widget to main layout
        group = QGroupBox("Repository Selection")
        group_layout = QVBoxLayout()
        group_layout.addWidget(self.tab_widget)
        group.setLayout(group_layout)
        
        main_layout.addWidget(group)
    
    def browseRepository(self):
        """Open file dialog to select repository directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Repository Directory",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self.repo_path.setText(dir_path)
    
    def onPathChanged(self, path):
        """Handle repository path changes."""
        # Basic validation of the path
        if path:
            path_obj = Path(path)
            if not path_obj.exists():
                self.repo_path.setStyleSheet("border: 2px solid #FF6B6B;")  # Red border
                self.repo_path.setToolTip("Directory does not exist")
            elif not path_obj.is_dir():
                self.repo_path.setStyleSheet("border: 2px solid #FF6B6B;")  # Red border
                self.repo_path.setToolTip("Selected path is not a directory")
            elif not self._is_accessible(path_obj):
                self.repo_path.setStyleSheet("border: 2px solid #FF6B6B;")  # Red border
                self.repo_path.setToolTip("Directory is not accessible")
            else:
                self.repo_path.setStyleSheet("")  # Reset style
                self.repo_path.setToolTip("")
        else:
            self.repo_path.setStyleSheet("")  # Reset style
            self.repo_path.setToolTip("")
        
        self.pathChanged.emit(path)
    
    def onGitHubRepoCloned(self, repo_path: str):
        """Handle when a GitHub repository is successfully cloned."""
        self.tab_widget.setCurrentIndex(0)  # Switch to local repository tab
        self.repo_path.setText(repo_path)
    
    def _is_accessible(self, path: Path) -> bool:
        """Check if the directory is accessible."""
        try:
            # Try to list directory contents
            next(path.iterdir(), None)
            return True
        except (PermissionError, OSError):
            return False
    
    def validate(self) -> tuple[bool, str]:
        """Validate the selected repository path.
        
        Returns:
            tuple[bool, str]: A tuple containing (is_valid, error_message)
        """
        # If on GitHub tab, no validation needed as the clone operation handles it
        if self.tab_widget.currentWidget() == self.github_widget:
            return True, ""
            
        path = self.repo_path.text()
        
        if not path:
            return False, "Repository path is required"
        
        path_obj = Path(path)
        
        if not path_obj.exists():
            return False, f"Directory does not exist: {path}"
        
        if not path_obj.is_dir():
            return False, f"Selected path is not a directory: {path}"
        
        if not self._is_accessible(path_obj):
            return False, f"Directory is not accessible: {path}"
        
        return True, ""
        
    def closeEvent(self, event):
        """Handle widget closure."""
        self.github_widget.cleanup()
        super().closeEvent(event)
