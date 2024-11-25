# samuraizer/gui/widgets/configuration/repository/widgets/repository_list_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QMessageBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RepositoryListWidget(QWidget):
    """Widget for displaying and managing a list of repositories."""
    
    repositorySelected = pyqtSignal(str)  # Emits the path of the selected repository
    repositoryAdded = pyqtSignal(str, str)     # Emits the path and type of the added repository
    repositoryRemoved = pyqtSignal(str)   # Emits the path of the removed repository
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.repositories = []
        self.repo_types = {}  # Dictionary to store repository types ('Local' or 'GitHub')
    
    def _setup_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # List widget to display repositories
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        
        # Buttons for adding and removing repositories
        button_layout = QHBoxLayout()
        add_local_btn = QPushButton("Add Local Repository")
        add_github_btn = QPushButton("Add GitHub Repository")
        remove_btn = QPushButton("Remove Selected")
        
        add_local_btn.clicked.connect(self.add_local_repository)
        add_github_btn.clicked.connect(self.add_github_repository)
        remove_btn.clicked.connect(self.remove_repository)
        
        button_layout.addWidget(add_local_btn)
        button_layout.addWidget(add_github_btn)
        button_layout.addWidget(remove_btn)
        
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)
    
    def add_local_repository(self):
        """Add a new local repository to the list."""
        repo_path = QFileDialog.getExistingDirectory(
            self,
            "Select Local Repository Directory",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        if repo_path:
            if repo_path not in self.repositories:
                self.repositories.append(repo_path)
                self.repo_types[repo_path] = "Local"
                item = QListWidgetItem(QIcon(":/icons/local_repo.png"), f"Local: {Path(repo_path).name}")
                item.setToolTip(f"Path: {repo_path}\nType: Local")
                item.setData(Qt.ItemDataRole.UserRole, repo_path)
                self.list_widget.addItem(item)
                self.repositoryAdded.emit(repo_path, "Local")
                logger.info(f"Added local repository: {repo_path}")
            else:
                QMessageBox.information(self, "Duplicate Repository", "This repository is already added.")
    
    def add_github_repository(self):
        """Add a new GitHub repository to the list."""
        # This function assumes that GitHub repositories are cloned through the GitHubWidget
        # and automatically added to the list. If manual addition is needed, implement accordingly.
        QMessageBox.information(self, "Add GitHub Repository", "Please use the GitHub Repository tab to clone and add GitHub repositories.")
    
    def remove_repository(self):
        """Remove the selected repository from the list."""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a repository to remove.")
            return
        for item in selected_items:
            repo_path = item.data(Qt.ItemDataRole.UserRole)
            self.repositories.remove(repo_path)
            del self.repo_types[repo_path]
            self.list_widget.takeItem(self.list_widget.row(item))
            self.repositoryRemoved.emit(repo_path)
            logger.info(f"Removed repository: {repo_path}")
    
    def on_item_clicked(self, item: QListWidgetItem):
        """Handle repository selection."""
        repo_path = item.data(Qt.ItemDataRole.UserRole)
        self.repositorySelected.emit(repo_path)
    
    def clear_repositories(self):
        """Clear all repositories from the list."""
        self.repositories.clear()
        self.repo_types.clear()
        self.list_widget.clear()

    def get_repository_type(self, repo_path: str) -> str:
        """Get the type of the repository ('Local' or 'GitHub')."""
        return self.repo_types.get(repo_path, "Unknown")
