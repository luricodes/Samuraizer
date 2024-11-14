# samuraizer/gui/widgets/options/repository/repository_selection.py

from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)

class RepositorySelectionWidget(QWidget):
    """Widget for selecting the repository directory."""
    
    pathChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface."""
        layout = QHBoxLayout(self)
        
        # Repository path input
        self.repo_path = QLineEdit()
        self.repo_path.setPlaceholderText("Select repository directory...")
        self.repo_path.textChanged.connect(self.onPathChanged)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browseRepository)
        browse_btn.setMaximumWidth(100)
        
        layout.addWidget(self.repo_path)
        layout.addWidget(browse_btn)
        
        group = QGroupBox("Repository Selection")
        group.setLayout(layout)
        
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(group)
        self.setLayout(main_layout)
    
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
