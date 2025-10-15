from typing import Optional, List
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class DescriptionSection(QWidget):
    """Widget representing the description section of the About dialog."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the description section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Description text
        desc = QLabel(
            "A powerful tool for analyzing repository structures and generating "
            "detailed reports in multiple formats. Features include:"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(desc)
        
        # Feature list
        self.add_features([
            "• Multiple output formats (JSON, YAML, XML, etc.)",
            "• Advanced file analysis capabilities",
            "• Multi-threading support for better performance",
            "• Configurable filtering options",
            "• Comprehensive reporting features"
        ])
        
    def add_features(self, features: List[str]) -> None:
        """Add feature list to the description section.
        
        Args:
            features: List of feature descriptions to display
        """
        layout = self.layout()
        if layout is None:
            return
        for feature in features:
            feature_label = QLabel(feature)
            feature_label.setWordWrap(True)
            layout.addWidget(feature_label)
