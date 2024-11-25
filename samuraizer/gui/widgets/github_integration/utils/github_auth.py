# samuraizer/gui/widgets/configuration/repository/github/utils/github_auth.py

import logging
import re
import requests
import keyring
from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

GITHUB_SERVICE_NAME = "Samuraizer_GitHub"
KEYRING_USERNAME = "access_token"

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
        """Set the GitHub access token securely using keyring.

        Args:
            token (str): The personal access token to store.
        """
        self.access_token = token
        try:
            keyring.set_password(GITHUB_SERVICE_NAME, KEYRING_USERNAME, token)
            logger.info("GitHub access token securely stored.")
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to store access token: {e}")
            QMessageBox.critical(None, "Storage Error", "Failed to store access token securely.")

    def get_access_token(self) -> Optional[str]:
        """Retrieve the GitHub access token securely from keyring.

        Returns:
            Optional[str]: The retrieved access token or None if not found.
        """
        try:
            token = keyring.get_password(GITHUB_SERVICE_NAME, KEYRING_USERNAME)
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
            keyring.delete_password(GITHUB_SERVICE_NAME, KEYRING_USERNAME)
            self.access_token = None
            logger.info("GitHub access token removed from secure storage.")
        except keyring.errors.PasswordDeleteError:
            logger.warning("GitHub access token not found in secure storage.")
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to remove access token: {e}")
            QMessageBox.critical(None, "Removal Error", "Failed to remove access token securely.")

    def fetch_authenticated_user(self) -> Optional[Dict]:
        """Fetch the authenticated user's information.

        Returns:
            Optional[Dict]: A dictionary containing user information or None if failed.
        """
        if not self.access_token:
            logger.error("Access token not set.")
            QMessageBox.critical(None, "Authentication Error", "Access token is not set.")
            return None
        headers = {"Authorization": f"token {self.access_token}"}
        try:
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            response.raise_for_status()
            logger.info("Fetched authenticated user information.")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching user info: {http_err}")
            QMessageBox.critical(None, "HTTP Error", f"Failed to fetch user info: {http_err}")
        except requests.exceptions.Timeout:
            logger.error("Request timed out while fetching user info.")
            QMessageBox.critical(None, "Timeout Error", "Request timed out while fetching user info.")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception occurred while fetching user info: {req_err}")
            QMessageBox.critical(None, "Request Error", f"Failed to fetch user info: {req_err}")
        except Exception as e:
            logger.exception(f"Unexpected error while fetching user info: {e}")
            QMessageBox.critical(None, "Unexpected Error", f"An unexpected error occurred: {e}")
        return None

class TokenInputWidget(QWidget):
    """Widget for entering GitHub personal access token."""

    def __init__(self, auth_manager: GitHubAuthManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.initUI()

    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("GitHub Authentication")
        self.setFixedSize(400, 200)
        layout = QVBoxLayout()

        info_label = QLabel(
            "Enter your GitHub Personal Access Token:\n"
            "You can generate a token at https://github.com/settings/tokens.\n"
            "Ensure it has the necessary scopes for repository access."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        layout.addWidget(self.token_input)

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_token)
        layout.addWidget(submit_btn)

        self.setLayout(layout)

    def submit_token(self):
        """Handle the submission of the personal access token."""
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Input Error", "Please enter a valid token.")
            logger.warning("Token submission attempted with empty input.")
            return
        # Basic validation of token format
        if not re.match(r'^ghp_[A-Za-z0-9]{36}$', token):
            QMessageBox.warning(self, "Input Error", "Invalid token format. Please check your token.")
            logger.warning(f"Invalid token format entered: {token}")
            return
        self.auth_manager.set_access_token(token)
        user_info = self.auth_manager.fetch_authenticated_user()
        if user_info:
            QMessageBox.information(self, "Success", f"Authenticated as {user_info.get('login')}")
            self.close()
        else:
            QMessageBox.critical(self, "Authentication Failed", "Failed to authenticate with the provided token.")
            logger.error("Authentication failed with the provided token.")
