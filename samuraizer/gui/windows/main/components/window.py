from pathlib import Path
import logging
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QMessageBox
from PyQt6.QtCore import QSize, QSettings
from samuraizer.backend.cache.connection_pool import (
    initialize_connection_pool, close_all_connections, get_connection_context
)
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from samuraizer.core.application import initialize_cache_directory
from samuraizer.gui.windows.base.window import BaseWindow
from samuraizer.gui.windows.main.toolbar import MainToolBar
from samuraizer.gui.windows.main.status import MainStatusBar
from samuraizer.gui.windows.main.panels import LeftPanel, RightPanel
from samuraizer.gui.windows.main.components.analysis import AnalysisManager
from samuraizer.gui.windows.main.components.ui_state import UIStateManager, AnalysisState
from samuraizer.gui.windows.main.components.dialog_manager import DialogManager
from samuraizer.config.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)

class MainWindow(BaseWindow):
    def __init__(self):
        super().__init__(
            title="Samuraizer",
            min_size=QSize(1200, 800),
            settings_prefix="main_window"
        )
        
        # Initialize toggle_theme as a no-op until it's properly set
        self.toggle_theme = lambda theme=None: None

        # Setup UI components in the correct order
        self.setup_ui()
        
        # Initialize managers in the correct order
        # UIStateManager must be initialized first as others depend on it
        self.ui_state_manager = UIStateManager(self, self.left_panel, self.right_panel)
        self.analysis_manager = AnalysisManager(self, self.left_panel, self.right_panel)
        self.dialog_manager = DialogManager(self)
        
        # Set initial UI state
        self.ui_state_manager.set_analysis_state(AnalysisState.IDLE)
        
        self.load_settings()
        self._initialize_cache()
            
        self._initialized = True

    def _initialize_cache(self) -> None:
        """Initialize the cache database connection pool."""
        pool = None
        try:
            # Get cache path from settings or use default
            settings = QSettings()
            cache_path = settings.value("settings/cache_path", "")
            if not cache_path:
                default_cache_path = Path.cwd() / ".cache"
                cache_path = str(default_cache_path)
                # Save the default path to settings
                settings.setValue("settings/cache_path", cache_path)
                settings.sync()
                logger.info(f"Set default cache path in settings: {cache_path}")
            
            cache_dir = Path(cache_path)
            cache_dir = initialize_cache_directory(cache_dir)
            cache_db_path = cache_dir / CACHE_DB_FILE
            
            logger.info(f"Initializing cache at: {cache_db_path}")
            
            # Get thread count from analysis settings
            thread_count = settings.value("analysis/thread_count", 4, int)
            cache_disabled = settings.value("settings/disable_cache", False, bool)
            
            pool = initialize_connection_pool(
                str(cache_db_path.absolute()),
                thread_count=thread_count,
                force_disable_cache=cache_disabled
            )
            logger.info(f"Connection pool initialized with cache at: {cache_db_path.absolute()}")
            logger.info(f"Cache settings - Disabled: {cache_disabled}, Thread Count: {thread_count}")
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}", exc_info=True)
            if pool:
                try:
                    close_all_connections()
                except Exception as cleanup_error:
                    logger.error(f"Error during connection cleanup: {cleanup_error}")
            QMessageBox.critical(self, "Error", f"Failed to initialize database: {str(e)}")

    def setup_ui(self) -> None:
        """Set up the main window UI."""
        try:
            self._create_central_widget()
            self._create_toolbars()
            self._create_panels()
        except Exception as e:
            logger.error(f"Error setting up main window UI: {e}", exc_info=True)
            raise

    def _create_central_widget(self) -> None:
        """Create and set up the central widget."""
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")  # Set object name for styling
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for clean look

    def _create_toolbars(self) -> None:
        """Create toolbar and status bar."""
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)
        self.status_bar = MainStatusBar(self)
        self.setStatusBar(self.status_bar)

    def _create_panels(self) -> None:
        """Create and set up main panels."""
        self.left_panel = LeftPanel(self)
        self.right_panel = RightPanel(self)
        self.main_layout.addWidget(self.left_panel, 1)
        self.main_layout.addWidget(self.right_panel, 2)

    # Public interface methods delegated to managers
    def open_repository(self) -> None:
        """Open a repository for analysis."""
        self.analysis_manager.open_repository()

    def start_analysis(self) -> None:
        """Start the repository analysis."""
        self.analysis_manager.start_analysis()

    def stop_analysis(self) -> None:
        """Stop the current analysis."""
        self.analysis_manager.stop_analysis()

    def show_settings(self) -> None:
        """Show the settings dialog."""
        self.dialog_manager.show_settings()

    def show_about(self) -> None:
        """Show the about dialog."""
        self.dialog_manager.show_about()

    def toggle_theme_to(self, theme: str) -> None:
        """Handle theme toggle to specific theme."""
        if self.toggle_theme and callable(self.toggle_theme):
            self.toggle_theme(theme)

    def get_connection_context(self):
        """Get the connection context for database operations."""
        return get_connection_context()

    def closeEvent(self, event) -> None:
        """Handle window closure."""
        try:
            # Stop any running analysis first
            if hasattr(self, 'analysis_manager'):
                self.analysis_manager.cleanup()

            # Close database connections
            try:
                close_all_connections()
                logger.info("All database connections closed successfully")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}", exc_info=True)
                
            # Clean up ConfigurationManager
            try:
                ConfigurationManager.cleanup()
                logger.info("Configuration manager cleaned up successfully")
            except Exception as e:
                logger.error(f"Error cleaning up configuration manager: {e}", exc_info=True)
                
            # Call parent's closeEvent to save window settings
            super().closeEvent(event)
            
            # Accept the event to ensure the window closes
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during window closure: {e}", exc_info=True)
            # Ensure the window closes even if there's an error
            event.accept()
