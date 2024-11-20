# samuraizer/gui/widgets/configuration/repository/github/github_widget.py

import logging
from typing import Optional, Dict
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QComboBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal

from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.backend.analysis.traversal.traversal_processor import get_directory_structure
from samuraizer.backend.services.event_service.events import shutdown_event

from .workers.git_clone_worker import GitCloneWorker
from .widgets.status_widget import StatusWidget
from .exceptions.github_errors import CloneOperationError
from .utils.github_utils import is_valid_github_url, fetch_repo_info, get_repo_branches

logger = logging.getLogger(__name__)

class GitHubWidget(QWidget):
    """Widget for GitHub repository integration."""

    repository_cloned = pyqtSignal(str)  # Emits the path to the cloned repo

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.clone_worker = None
        self.temp_dir = None
        self.repo_info = None
        self._setup_ui()

    def _setup_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Create GitHub repository group
        group = QGroupBox("GitHub Repository")
        layout = QVBoxLayout()
        
        # URL input section
        url_layout = QHBoxLayout()
        url_label = QLabel("Repository URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://github.com/username/repository or git@github.com:username/repository")
        self.url_input.textChanged.connect(self._validate_url)
        
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input, stretch=1)
        
        # Branch selection
        branch_layout = QHBoxLayout()
        branch_label = QLabel("Branch:")
        self.branch_combo = QComboBox()
        self.branch_combo.setEnabled(False)
        self.branch_combo.addItem("default")
        
        branch_layout.addWidget(branch_label)
        branch_layout.addWidget(self.branch_combo, stretch=1)
        
        # Clone button
        self.clone_btn = QPushButton("Clone & Analyze")
        self.clone_btn.clicked.connect(self.clone_repository)
        self.clone_btn.setEnabled(False)
        
        # Status widget
        self.status_widget = StatusWidget()
        
        # Add all layouts to the group
        layout.addLayout(url_layout)
        layout.addLayout(branch_layout)
        layout.addWidget(self.clone_btn)
        layout.addWidget(self.status_widget)
        
        group.setLayout(layout)
        main_layout.addWidget(group)
        main_layout.addStretch()

    def _validate_url(self, url: str) -> None:
        """Validate the GitHub repository URL and fetch repository information."""
        if not url.strip():
            self.url_input.setStyleSheet("")
            self.status_widget.hide()
            self.clone_btn.setEnabled(False)
            self.branch_combo.setEnabled(False)
            return

        is_valid = is_valid_github_url(url)
        
        if is_valid:
            self.url_input.setStyleSheet("")
            self.status_widget.update_status("Fetching repository information...")
            
            # Fetch repository information
            self.repo_info = fetch_repo_info(url)
            if self.repo_info:
                # Update status with repository information
                info_text = (
                    f"Repository: {self.repo_info['name']}\n"
                    f"Owner: {self.repo_info['owner']}\n"
                    f"Stars: {self.repo_info['stars']}, Forks: {self.repo_info['forks']}"
                )
                if self.repo_info['description']:
                    info_text += f"\nDescription: {self.repo_info['description']}"
                self.status_widget.update_status(info_text)
                
                # Fetch and populate branches
                branches = get_repo_branches(url)
                if branches:
                    self.branch_combo.clear()
                    self.branch_combo.addItem("default")
                    self.branch_combo.addItems(branches)
                    default_branch = self.repo_info['default_branch']
                    default_index = self.branch_combo.findText(default_branch)
                    if default_index >= 0:
                        self.branch_combo.setCurrentIndex(default_index)
                
                self.clone_btn.setEnabled(True)
                self.branch_combo.setEnabled(True)
            else:
                self.status_widget.update_status("Repository not found or inaccessible")
                self.clone_btn.setEnabled(False)
                self.branch_combo.setEnabled(False)
        else:
            self.url_input.setStyleSheet("border: 1px solid red;")
            self.status_widget.update_status("Invalid GitHub repository URL")
            self.clone_btn.setEnabled(False)
            self.branch_combo.setEnabled(False)

        self.status_widget.show()

    def clone_repository(self):
        """Clone the GitHub repository."""
        url = self.url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid GitHub repository URL")
            return

        # Update UI state
        self.status_widget.update_status("Starting clone operation...", show_progress=True)
        self.clone_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.branch_combo.setEnabled(False)

        # Create temporary directory for cloning
        try:
            self.temp_dir = Path.home() / ".samuraizer" / "temp" / "github_repos"
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create temporary directory: {str(e)}")
            self._reset_ui_state()
            return

        # Start clone operation
        branch = self.branch_combo.currentText() if self.branch_combo.currentText() != "default" else None
        self.clone_worker = GitCloneWorker(url, str(self.temp_dir), branch)
        self.clone_worker.progress.connect(self.status_widget.update_status)
        self.clone_worker.error.connect(self._handle_clone_error)
        self.clone_worker.finished.connect(self._handle_clone_success)
        self.clone_worker.start()

    def _handle_clone_error(self, error_message: str):
        """Handle clone operation errors."""
        self.status_widget.update_status(f"Error: {error_message}", show_progress=False)
        QMessageBox.critical(self, "Clone Error", f"Failed to clone repository:\n{error_message}")
        self._reset_ui_state()

    def _handle_clone_success(self, repo_path: str):
        """Handle successful clone operation."""
        self.status_widget.update_status("Repository cloned successfully!", show_progress=False)
        self.repository_cloned.emit(repo_path)
        self._reset_ui_state()
        self.url_input.clear()
        self.branch_combo.setCurrentText("default")

    def _reset_ui_state(self):
        """Reset the UI state after clone operation."""
        self.clone_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.branch_combo.setEnabled(True)

    def cleanup(self):
        """Clean up temporary resources."""
        if self.clone_worker and self.clone_worker.isRunning():
            self.clone_worker.stop()
            self.clone_worker.wait()
            
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.error(f"Failed to cleanup temporary directory: {e}")

    def closeEvent(self, event):
        """Handle widget closure."""
        self.cleanup()
        super().closeEvent(event)
