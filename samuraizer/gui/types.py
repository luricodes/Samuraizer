# samuraizer/gui/types.py

from typing import Protocol, TypeVar, Dict, Any, Optional
from PyQt6.QtWidgets import QWidget

class MainWindowProtocol(Protocol):
    """Protocol defining the interface for MainWindow"""
    def get_connection_context(self) -> Any: ...
    def show_error(self, title: str, message: str) -> None: ...
    def toggle_theme(self, theme: Optional[str] = None) -> None: ...

class PanelProtocol(Protocol):
    """Base protocol for panel interfaces"""
    def setup_ui(self) -> None: ...
    def validate_inputs(self) -> bool: ...
    def get_configuration(self) -> Dict[str, Any]: ...

# Type variables for generic typing
WindowType = TypeVar('WindowType', bound='MainWindowProtocol')
WidgetType = TypeVar('WidgetType', bound=QWidget)
