"""Panel components for the main window."""
from .left_panel import LeftPanel
from .right_panel import RightPanel
from .base import BasePanel
from .log_panel import LogPanel
from .details_panel import LLMConfigDialog

__all__ = ['LeftPanel', 'RightPanel', 'BasePanel', 'LogPanel', 'LLMConfigDialog']