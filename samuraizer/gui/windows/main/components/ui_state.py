from typing import Optional
import logging
from enum import Enum, auto
from typing import TYPE_CHECKING
from samuraizer.gui.windows.base.window import BaseWindow
if TYPE_CHECKING:
    from samuraizer.gui.windows.main.panels import LeftPanel, RightPanel

logger = logging.getLogger(__name__)

class AnalysisState(Enum):
    """Enumeration of possible analysis states."""
    IDLE = auto()
    RUNNING = auto()
    COMPLETED = auto()
    ERROR = auto()

class UIStateManager:
    """Manages UI state and updates."""
    
    def __init__(self, parent: 'BaseWindow', left_panel: 'LeftPanel', right_panel: 'RightPanel'):
        self.parent = parent
        self.left_panel = left_panel
        self.right_panel = right_panel
        self._analysis_state = AnalysisState.IDLE

    def set_analysis_state(self, state: AnalysisState) -> None:
        """Update analysis state and trigger UI updates."""
        self._analysis_state = state
        self._update_ui_for_state()

    def _update_ui_for_state(self) -> None:
        """Update UI elements based on current analysis state."""
        try:
            if self._analysis_state == AnalysisState.RUNNING:
                self.left_panel.analyze_btn.setEnabled(False)
                self.left_panel.stop_btn.setEnabled(True)
                self.right_panel.showProgress()
                self.parent.status_bar.showMessage("Analysis in progress...")
            elif self._analysis_state == AnalysisState.COMPLETED:
                self.left_panel.analyze_btn.setEnabled(True)
                self.left_panel.stop_btn.setEnabled(False)
                self.right_panel.hideProgress()
                self.parent.status_bar.showMessage("Analysis completed successfully")
            elif self._analysis_state == AnalysisState.ERROR:
                self.left_panel.analyze_btn.setEnabled(True)
                self.left_panel.stop_btn.setEnabled(False)
                self.right_panel.hideProgress()
            else:  # IDLE
                self.left_panel.analyze_btn.setEnabled(True)
                self.left_panel.stop_btn.setEnabled(False)
                self.right_panel.hideProgress()
                self.parent.status_bar.showMessage("Ready")
        except Exception as e:
            logger.error(f"Error updating UI state: {e}", exc_info=True)