"""Component modules for the main window."""
from .analysis import AnalysisManager
from .dialog_manager import DialogManager
from .ui_state import UIStateManager, AnalysisState

__all__ = [
    'AnalysisManager',
    'DialogManager',
    'UIStateManager',
    'AnalysisState'
]