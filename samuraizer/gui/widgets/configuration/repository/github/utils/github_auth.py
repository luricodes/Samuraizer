# samuraizer/gui/widgets/configuration/repository/github/utils/github_auth.py

import logging
import requests
import keyring
from typing import Optional, Dict
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QMessageBox

logger = logging.getLogger(__name__)

GITHUB_SERVICE_NAME = "Samuraizer_GitHub"

class GitHubAuthManager:
    """Manages GitHub authentication processes securely."""
    
    def __init__(self):
        self.access_token: Optional[str] = self.get_access_token()
    
    def authenticate(self):
        """Initiate OAuth authentication flow."""
        # Placeholder for OAuth implementation.
        # This could involve opening a web browser for user authorization
        # and handling the redirect to obtain the access token.
        logger.info("Starting OAuth authentication flow.")
        # Implementation needed.
    
    def set_access_token(self, token: str):
        """Set the GitHub access token securely using keyring."""
        self.access_token = token
        try:
            keyring.set_password(GITHUB_SERVICE_NAME, "access_token", token)
            logger.info("GitHub access token securely stored.")
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to store access token: {e}")
            QMessageBox.critical(None, "Storage Error", "Failed to store access token securely.")
    
    def get_access_token(self) -> Optional[str]:
        """Retrieve the GitHub access token securely from keyring."""
        try:
            token = keyring.get_password(GITHUB_SERVICE_NAME, "access_token")
            if token:
                logger.info("GitHub access token retrieved from secure storage.")
            else:
                logger.info("No GitHub access token found in secure storage.")
            return token
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to retrieve access token: {e}")
            QMessageBox.critical(None, "Retrieval Error", "Failed to retrieve access token securely.")
            return None
    
    def remove_access_token(self):
        """Remove the GitHub access token from secure storage."""
        try:
            keyring.delete_password(GITHUB_SERVICE_NAME, "access_token")
            self.access_token = None
            logger.info("GitHub access token removed from secure storage.")
        except keyring.errors.PasswordDeleteError:
            logger.warning("GitHub access token not found in secure storage.")
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to remove access token: {e}")
            QMessageBox.critical(None, "Removal Error", "Failed to remove access token securely.")
    
    def fetch_authenticated_user(self) -> Optional[Dict]:
        """Fetch the authenticated user's information."""
        if not self.access_token:
            logger.error("Access token not set.")
            return None
        headers = {"Authorization": f"token {self.access_token}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            logger.info("Fetched authenticated user information.")
            return response.json()
        else:
            logger.error(f"Failed to fetch user info: {response.status_code} {response.text}")
            return None

# Example QWidget for entering a personal access token
class TokenInputWidget(QWidget):
    """Widget for entering GitHub personal access token."""
    
    def __init__(self, auth_manager: GitHubAuthManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        info_label = QLabel("Enter your GitHub Personal Access Token:")
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        
        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_token)
        
        layout.addWidget(info_label)
        layout.addWidget(self.token_input)
        layout.addWidget(submit_btn)
        
        self.setLayout(layout)
    
    def submit_token(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Input Error", "Please enter a valid token.")
            return
        # Basic validation of token format
        if not token.startswith("ghp_") or len(token) < 40:
            QMessageBox.warning(self, "Input Error", "Invalid token format.")
            return
        self.auth_manager.set_access_token(token)
        user_info = self.auth_manager.fetch_authenticated_user()
        if user_info:
            QMessageBox.information(self, "Success", f"Authenticated as {user_info.get('login')}")
        else:
            QMessageBox.critical(self, "Authentication Failed", "Failed to authenticate with the provided token.")
