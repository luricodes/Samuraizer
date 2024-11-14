"""Main window components."""
from .components.window import MainWindow
from .toolbar import MainToolBar
from .status import MainStatusBar
from .panels import LeftPanel, RightPanel

__all__ = [
    'MainWindow',
    'MainToolBar',
    'MainStatusBar',
    'LeftPanel',
    'RightPanel'
]