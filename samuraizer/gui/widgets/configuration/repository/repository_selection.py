# samuraizer/gui/widgets/configuration/repository/repository_selection.py

from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, 
    QPushButton, QFileDialog, QGroupBox, QTabWidget, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

from samuraizer.backend.services.logging.logging_service import setup_logging
from .github.github_widget import GitHubWidget
from .widgets.repository_list_widget import RepositoryListWidget

logger = logging.getLogger(__name__)

class RepositorySelectionWidget(QWidget):
    """Widget for selecting and managing multiple repository directories or GitHub repositories."""
    
    pathChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Create repository list widget
        self.repo_list_widget = RepositoryListWidget()
        self.repo_list_widget.repositorySelected.connect(self.on_repository_selected)
        self.repo_list_widget.repositoryAdded.connect(self.on_repository_added)
        self.repo_list_widget.repositoryRemoved.connect(self.on_repository_removed)
        
        # Create GitHub repository widget
        self.github_widget = GitHubWidget()
        self.github_widget.repository_cloned.connect(self.onGitHubRepoCloned)
        # Removed the incorrect signal definition below
        # self.github_widget.repositoryCloned = pyqtSignal(str)
        
        # Create repository path line edit
        self.repo_path = QLineEdit()
        self.repo_path.setReadOnly(True)
        repo_path_layout = QHBoxLayout()
        repo_path_label = QLabel("Repository Path:")
        repo_path_layout.addWidget(repo_path_label)
        repo_path_layout.addWidget(self.repo_path)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.tab_widget.addTab(self.repo_list_widget, "Repository List")
        self.tab_widget.addTab(self.github_widget, "GitHub Repository")
        
        # Add tab widget and repo path to main layout
        group = QGroupBox("Repository Selection")
        group_layout = QVBoxLayout()
        group_layout.addWidget(self.tab_widget)
        group_layout.addLayout(repo_path_layout)
        group.setLayout(group_layout)
        
        main_layout.addWidget(group)
    
    def on_repository_selected(self, repo_path: str):
        """Handle repository selection from the list."""
        self.tab_widget.setCurrentWidget(self.repo_list_widget)
        self.repo_path.setText(repo_path)
        self.pathChanged.emit(repo_path)
        logger.info(f"Selected repository: {repo_path}")
    
    def on_repository_added(self, repo_path: str):
        """Handle addition of a new repository."""
        self.repo_path.setText(repo_path)
        self.pathChanged.emit(repo_path)
        logger.info(f"Added repository: {repo_path}")
    
    def on_repository_removed(self, repo_path: str):
        """Handle removal of a repository."""
        if self.repo_path.text() == repo_path:
            self.repo_path.clear()
        logger.info(f"Removed repository: {repo_path}")
    
    def onGitHubRepoCloned(self, repo_path: str):
        """Handle when a GitHub repository is successfully cloned."""
        self.repo_list_widget.repositories.append(repo_path)
        self.repo_list_widget.list_widget.addItem(repo_path)
        self.repo_path.setText(repo_path)
        self.pathChanged.emit(repo_path)
        logger.info(f"Cloned GitHub repository: {repo_path}")
    
    def validate(self) -> list[tuple[bool, str, str]]:
        """Validate all selected repository paths.
        
        Returns:
            list of tuples: Each tuple contains (is_valid, error_message, repo_path)
        """
        validations = []
        for repo_path in self.repo_list_widget.repositories:
            is_valid, error = self._validate_path(repo_path)
            validations.append((is_valid, error, repo_path))
        return validations
    
    def _validate_path(self, path: str) -> tuple[bool, str]:
        """Validate a single repository path.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if not path:
            return False, "Repository path is required."
        
        path_obj = Path(path)
        
        if not path_obj.exists():
            return False, f"Directory does not exist: {path}"
        
        if not path_obj.is_dir():
            return False, f"Selected path is not a directory: {path}"
        
        if not self._is_accessible(path_obj):
            return False, f"Directory is not accessible: {path}"
        
        return True, ""
    
    def _is_accessible(self, path: Path) -> bool:
        """Check if the directory is accessible."""
        try:
            # Try to list directory contents
            next(path.iterdir(), None)
            return True
        except (PermissionError, OSError):
            return False
    
    def set_repository_path(self, path: str):
        """Set the repository path."""
        self.repo_path.setText(path)
    
    def get_repository_path(self) -> str:
        """Get the repository path."""
        return self.repo_path.text()
    
    def closeEvent(self, event):
        """Handle widget closure."""
        self.github_widget.cleanup()
        super().closeEvent(event)
