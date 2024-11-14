# samuraizer/gui/windows/types.py

"""Type definitions for window components."""

from typing import Protocol, TypeVar, Union, Optional
from PyQt6.QtWidgets import QWidget

class ThemeToggleProtocol(Protocol):
    """Protocol for theme toggle functionality."""
    def __call__(self, theme: Optional[str] = None) -> None: ...

class WindowProtocol(Protocol):
    """Protocol defining the interface for window implementations."""
    toggle_theme: ThemeToggleProtocol

    def show(self) -> None: ...
    def hide(self) -> None: ...
    def close(self) -> None: ...

ParentWidget = TypeVar('ParentWidget', bound=QWidget)