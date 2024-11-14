from typing import Optional
import logging
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QUrl  # Fixed: QUrl is in QtCore
from PyQt6.QtGui import QDesktopServices  # QDesktopServices remains in QtGui

logger = logging.getLogger(__name__)

class AuthorSection(QWidget):
    """Widget representing the author section of the About dialog."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the author section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Author info
        author = QLabel("Created by Lucas Richert")
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author)
        
        # Contact/Links section
        contact = QLabel("Contact: info@lucasrichert.tech")
        contact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(contact)
        
        # Add links section
        layout.addWidget(self.create_links_section())
        
    def create_links_section(self) -> QWidget:
        """Create the links section with buttons."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # GitHub button
        github_btn = QPushButton("GitHub")
        github_btn.clicked.connect(
            lambda: self.open_url("https://github.com/luricodes/Repository_Analyser_Reworked")
        )
        
        # Documentation button
        docs_btn = QPushButton("Documentation")
        docs_btn.clicked.connect(
            lambda: self.open_url("https://github.com/luricodes/Repository_Analyser_Reworked/blob/main/README.md")
        )
        
        # Add buttons to layout
        layout.addStretch()
        layout.addWidget(github_btn)
        layout.addWidget(docs_btn)
        layout.addStretch()
        
        return container
        
    def open_url(self, url: str) -> None:
        """Open a URL in the default browser."""
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            logger.error(f"Error opening URL {url}: {e}", exc_info=True)
            # We can't directly show error dialog here, so we just log the error
            # The main dialog should handle error reporting
