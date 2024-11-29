from typing import Dict, Any
import logging
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

class BasePanel(QWidget):
    """Base class for panels with common functionality."""
    
    def __init__(self) -> None:
        super().__init__()
        
    def setup_ui(self) -> None:
        """Set up the panel UI."""
        raise NotImplementedError
        
    def validate_inputs(self) -> bool:
        """Validate panel inputs."""
        return True
        
    def get_configuration(self) -> Dict[str, Any]:
        """Get panel configuration."""
        raise NotImplementedError
