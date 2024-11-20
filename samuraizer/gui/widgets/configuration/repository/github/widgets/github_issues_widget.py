# samuraizer/gui/widgets/configuration/repository/github/widgets/github_issues_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem, QMessageBox, QHBoxLayout, QLineEdit, QTextEdit, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

import logging
import requests

from ..utils.github_auth import GitHubAuthManager

logger = logging.getLogger(__name__)

class GitHubIssuesWidget(QWidget):
    """Widget for displaying and managing GitHub issues."""
    
    def __init__(self, auth_manager: GitHubAuthManager, repo_owner: str, repo_name: str, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.issues = []
        self.init_ui()
        self.fetch_issues()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Title and Refresh Button
        header_layout = QHBoxLayout()
        header_label = QLabel("Open Issues")
        refresh_btn = QPushButton("Refresh Issues")
        refresh_btn.clicked.connect(self.fetch_issues)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        
        # Issues list
        self.issues_list = QListWidget()
        self.issues_list.itemClicked.connect(self.view_issue_details)
        
        # Create issue button
        create_btn = QPushButton("Create New Issue")
        create_btn.clicked.connect(self.create_issue)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.issues_list)
        layout.addWidget(create_btn)
        
    def fetch_issues(self):
        """Fetch open issues from the GitHub repository."""
        token = self.auth_manager.get_access_token()
        if not token:
            QMessageBox.warning(self, "Authentication Required", "Please authenticate with GitHub to view issues.")
            return
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            self.issues = response.json()
            self.populate_issues()
        else:
            logger.error(f"Failed to fetch issues: {response.status_code} {response.text}")
            QMessageBox.critical(self, "Error", f"Failed to fetch issues: {response.status_code} {response.text}")
    
    def populate_issues(self):
        """Populate the issues list with fetched issues."""
        self.issues_list.clear()
        for issue in self.issues:
            if 'pull_request' not in issue:  # Exclude pull requests
                item = QListWidgetItem(f"#{issue['number']} - {issue['title']}")
                item.setData(Qt.ItemDataRole.UserRole, issue)
                self.issues_list.addItem(item)
    
    def view_issue_details(self, item: QListWidgetItem):
        """Display the details of a selected issue."""
        issue = item.data(Qt.ItemDataRole.UserRole)
        details = f"Issue #{issue['number']}: {issue['title']}\n\n{issue['body']}"
        QMessageBox.information(self, f"Issue #{issue['number']}", details)
    
    def create_issue(self):
        """Open a dialog to create a new GitHub issue."""
        dialog = CreateIssueDialog(self.auth_manager, self.repo_owner, self.repo_name, self)
        if dialog.exec():
            self.fetch_issues()

class CreateIssueDialog(QMessageBox):
    """Dialog for creating a new GitHub issue."""
    
    def __init__(self, auth_manager: GitHubAuthManager, repo_owner: str, repo_name: str, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.setWindowTitle("Create New Issue")
        self.setIcon(QMessageBox.Icon.Question)
        
        # Setup layout
        self.layout = self.layout()
        self.title_input = QLineEdit()
        self.body_input = QTextEdit()
        
        self.layout.addWidget(QLabel("Title:"), 1, 0)
        self.layout.addWidget(self.title_input, 1, 1)
        self.layout.addWidget(QLabel("Description:"), 2, 0)
        self.layout.addWidget(self.body_input, 2, 1)
        
        self.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        self.addButton("Create", QMessageBox.ButtonRole.AcceptRole)
    
    def exec(self):
        """Execute the dialog and return True if accepted."""
        return super().exec()
    
    def accept(self):
        """Handle the creation of a new issue."""
        title = self.title_input.text().strip()
        body = self.body_input.toPlainText().strip()
        
        if not title:
            QMessageBox.warning(self, "Input Error", "Issue title cannot be empty.")
            return
        
        token = self.auth_manager.get_access_token()
        if not token:
            QMessageBox.warning(self, "Authentication Required", "Please authenticate with GitHub to create issues.")
            return
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        payload = {
            "title": title,
            "body": body
        }
        
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            QMessageBox.information(self, "Success", "Issue created successfully.")
            super().accept()
        else:
            logger.error(f"Failed to create issue: {response.status_code} {response.text}")
            QMessageBox.critical(self, "Error", f"Failed to create issue: {response.status_code} {response.text}")
