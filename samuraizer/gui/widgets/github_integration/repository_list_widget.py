# samuraizer/gui/widgets/configuration/repository/widgets/repository_list_widget.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon

logger = logging.getLogger(__name__)


class RepositoryListWidget(QWidget):
    """Widget for displaying and managing a list of repositories."""

    repositorySelected = pyqtSignal(str, dict)  # Emits the path and metadata of the selected repository
    repositoryAdded = pyqtSignal(str, dict)      # Emits the path and metadata of the added repository
    repositoryRemoved = pyqtSignal(str)          # Emits the path of the removed repository

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.repositories: list[str] = []
        self.repo_metadata: Dict[str, Dict[str, str]] = {}

    def _setup_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # List widget to display repositories
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setObjectName("repositoryList")
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # Buttons for adding and removing repositories
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        add_local_btn = QPushButton("Add Local Repository")
        add_github_btn = QPushButton("Link GitHub Clone")
        remove_btn = QPushButton("Remove Selected")

        add_local_btn.setObjectName("addLocalRepoButton")
        add_github_btn.setObjectName("addGithubRepoButton")
        remove_btn.setObjectName("removeRepoButton")

        add_local_btn.clicked.connect(self.add_local_repository)
        add_github_btn.clicked.connect(self.add_github_repository)
        remove_btn.clicked.connect(self.remove_repository)

        button_layout.addWidget(add_local_btn)
        button_layout.addWidget(add_github_btn)
        button_layout.addWidget(remove_btn)

        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Repository management helpers
    # ------------------------------------------------------------------
    def _create_list_item(self, repo_path: str, metadata: Dict[str, str]) -> QListWidgetItem:
        """Create a styled list item for a repository entry."""

        repo_type = metadata.get("type", "Local")
        display_name = Path(repo_path).name or repo_path
        branch = metadata.get("branch")
        branch_display = None
        if branch:
            branch_display = branch if branch.lower() != "default" else None
        descriptor = f"{repo_type}: {display_name}"
        if branch_display:
            descriptor += f" [{branch_display}]"

        icon = QIcon(":/icons/local_repo.png")
        item = QListWidgetItem(icon, descriptor)
        tooltip_lines = [f"Path: {repo_path}", f"Source: {repo_type}"]
        if branch:
            tooltip_lines.append(
                f"Branch: {branch if branch.lower() != 'default' else 'Default branch'}"
            )
        item.setToolTip("\n".join(tooltip_lines))
        item.setData(Qt.ItemDataRole.UserRole, repo_path)
        item.setData(Qt.ItemDataRole.UserRole + 1, metadata)
        return item

    def _register_repository(self, repo_path: str, metadata: Dict[str, str]) -> Optional[QListWidgetItem]:
        """Register a repository and return the created list item."""

        if repo_path in self.repositories:
            QMessageBox.information(self, "Duplicate Repository", "This repository is already in the list.")
            logger.info("Attempted to register duplicate repository: %s", repo_path)
            return None

        self.repositories.append(repo_path)
        self.repo_metadata[repo_path] = metadata
        item = self._create_list_item(repo_path, metadata)
        self.list_widget.addItem(item)
        return item

    # ------------------------------------------------------------------
    # Slots triggered by user interaction
    # ------------------------------------------------------------------
    def add_local_repository(self) -> None:
        """Add a new local repository to the list."""
        repo_path = QFileDialog.getExistingDirectory(
            self,
            "Select Local Repository",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )

        if not repo_path:
            return

        metadata = {"type": "Local"}
        item = self._register_repository(repo_path, metadata)
        if item is None:
            return

        self.list_widget.setCurrentItem(item)
        self.repositoryAdded.emit(repo_path, metadata)
        self.repositorySelected.emit(repo_path, metadata)
        logger.info("Added local repository: %s", repo_path)

    def add_github_repository(self):
        """Add a new GitHub repository to the list."""
        # This function assumes that GitHub repositories are cloned through the GitHubWidget
        # and automatically added to the list. If manual addition is needed, implement accordingly.
        QMessageBox.information(self, "Add GitHub Repository", "Please use the GitHub Repository tab to clone and add GitHub repositories.")

    def remove_repository(self) -> None:
        """Remove the selected repository from the list."""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a repository to remove.")
            return
        for item in selected_items:
            repo_path = item.data(Qt.ItemDataRole.UserRole)
            self.repositories.remove(repo_path)
            self.repo_metadata.pop(repo_path, None)
            self.list_widget.takeItem(self.list_widget.row(item))
            self.repositoryRemoved.emit(repo_path)
            logger.info(f"Removed repository: {repo_path}")

    def on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle repository selection."""
        repo_path = item.data(Qt.ItemDataRole.UserRole)
        metadata = item.data(Qt.ItemDataRole.UserRole + 1) or {"type": "Local"}
        self.repositorySelected.emit(repo_path, metadata)

    def clear_repositories(self) -> None:
        """Clear all repositories from the list."""
        self.repositories.clear()
        self.repo_metadata.clear()
        self.list_widget.clear()

    # ------------------------------------------------------------------
    # External helpers used by parent widgets
    # ------------------------------------------------------------------
    def register_github_repository(self, repo_path: str, branch: Optional[str] = None) -> None:
        """Register a cloned GitHub repository."""
        metadata = {"type": "GitHub"}
        if branch:
            metadata["branch"] = branch

        item = self._register_repository(repo_path, metadata)
        if item is None:
            return

        self.list_widget.setCurrentItem(item)
        self.repositoryAdded.emit(repo_path, metadata)
        self.repositorySelected.emit(repo_path, metadata)
        logger.info("Registered GitHub repository: %s", repo_path)

    def get_repository_metadata(self, repo_path: str) -> Dict[str, str]:
        """Return stored metadata for a repository."""
        return self.repo_metadata.get(repo_path, {"type": "Unknown"})
