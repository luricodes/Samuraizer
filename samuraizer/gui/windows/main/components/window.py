from pathlib import Path
import logging
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QMessageBox, QApplication
from PyQt6.QtCore import QSize, Qt
from samuraizer.backend.cache.connection_pool import (
    close_all_connections,
    flush_pending_writes,
    get_connection_context,
    initialize_connection_pool,
    set_cache_disabled,
)
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from samuraizer.core.application import initialize_cache_directory
from samuraizer.gui.windows.base.window import BaseWindow
from samuraizer.gui.windows.main.toolbar import MainToolBar
from samuraizer.gui.windows.main.status import MainStatusBar
from samuraizer.gui.windows.main.panels import LeftPanel, RightPanel
from samuraizer.gui.windows.main.components.analysis import AnalysisManager
from samuraizer.gui.windows.main.components.analysis_dependencies import (
    QMessagePresenter,
    UIAnalysisConfigCollector,
    UIAnalysisDisplay,
    UIRepositorySelector,
    UIRepositoryValidator,
    UIStatusReporter,
)
from samuraizer.gui.windows.main.components.ui_state import UIStateManager, AnalysisState
from samuraizer.gui.windows.main.components.dialog_manager import DialogManager
from samuraizer.config.unified import UnifiedConfigManager
from samuraizer.gui.app.theme_manager import ThemeManager
from samuraizer.gui.windows.main.components.run_history_manager import RunHistoryManager
from samuraizer.gui.widgets.run_history import RunHistoryDock, RunHistoryEntry

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
        self._config_manager = UnifiedConfigManager()
        self._applied_theme = ThemeManager.get_saved_theme()
        self._config_manager.add_change_listener(self._handle_config_change)

        # Setup UI components in the correct order
        self.setup_ui()

        # Run history infrastructure
        self.run_history_manager = RunHistoryManager(self)
        self.run_history_dock = self._create_run_history_dock()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.run_history_dock)
        self.run_history_dock.hide()

        # Initialize managers in the correct order
        # UIStateManager must be initialized first as others depend on it
        self.ui_state_manager = UIStateManager(self, self.left_panel, self.right_panel)

        repository_widget = self.left_panel.analysis_options.repository_widget
        repository_selector = UIRepositorySelector(repository_widget)
        repository_validator = UIRepositoryValidator(repository_widget)
        status_reporter = UIStatusReporter(self.status_bar)
        analysis_display = UIAnalysisDisplay(self.right_panel)
        message_presenter = QMessagePresenter(self)
        config_collector = UIAnalysisConfigCollector(self.left_panel, repository_validator)

        self.analysis_manager = AnalysisManager(
            repository_selector=repository_selector,
            repository_validator=repository_validator,
            config_collector=config_collector,
            analysis_display=analysis_display,
            state_controller=self.ui_state_manager,
            status_reporter=status_reporter,
            message_presenter=message_presenter,
        )
        self.dialog_manager = DialogManager(self)

        # Wire up run history interactions
        self._connect_run_history()

        # Set initial UI state
        self.ui_state_manager.set_analysis_state(AnalysisState.IDLE)
        
        self.load_settings()
        self._initialize_cache()
            
        self._initialized = True

    def _initialize_cache(self) -> None:
        """Initialize the cache database connection pool."""
        pool_initialized = False
        try:
            config_manager = UnifiedConfigManager()
            config = config_manager.get_active_profile_config()
            cache_cfg = config.get("cache", {})
            analysis_cfg = config.get("analysis", {})

            cache_path_value = cache_cfg.get("path") or str(Path.cwd() / ".cache")
            cache_dir = Path(str(cache_path_value)).expanduser()

            # Get thread count from analysis settings
            thread_count = int(analysis_cfg.get("threads", 4) or 4)
            cache_disabled = not bool(analysis_cfg.get("cache_enabled", True))

            set_cache_disabled(cache_disabled)

            if cache_disabled:
                cache_db_path = cache_dir / CACHE_DB_FILE
                logger.debug(
                    "Cache setup skipped because caching is disabled (DB path would be %s)",
                    cache_db_path,
                )
            else:
                cache_dir = initialize_cache_directory(cache_dir)
                cache_db_path = cache_dir / CACHE_DB_FILE
                logger.debug("Preparing cache at %s", cache_db_path)

            initialize_connection_pool(
                str(cache_db_path.absolute()),
                thread_count=thread_count,
                force_disable_cache=cache_disabled
            )
            pool_initialized = True

            if cache_disabled:
                logger.info(
                    "Caching is turned off. Analyses will run without storing results locally."
                )
            else:
                logger.info("Caching is enabled. Repeat analyses will run faster.")
                logger.debug(
                    "Local cache ready at %s (worker threads: %s)",
                    cache_db_path.absolute(),
                    thread_count,
                )
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}", exc_info=True)
            if pool_initialized:
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

    def _create_run_history_dock(self) -> RunHistoryDock:
        dock = RunHistoryDock(self)
        dock.requestComparison.connect(self._on_run_history_compare)
        dock.requestOpen.connect(self._on_run_history_open)
        return dock

    def _connect_run_history(self) -> None:
        self.run_history_manager.entryAdded.connect(self.run_history_dock.add_entry)
        self.run_history_manager.entryAdded.connect(self._on_history_entry_added)
        self.run_history_manager.comparisonRequested.connect(self._show_run_comparison)
        self.run_history_manager.comparisonUnavailable.connect(
            self.run_history_dock.notify_comparison_unavailable
        )
<<<<<<< ours
<<<<<<< ours
=======
        self.run_history_manager.activeEntryChanged.connect(self.run_history_dock.set_active_entry)
>>>>>>> theirs
=======
        self.run_history_manager.activeEntryChanged.connect(self.run_history_dock.set_active_entry)
>>>>>>> theirs
        self.right_panel.attach_run_history_manager(self.run_history_manager)

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

    # ------------------------------------------------------------------
    def _on_run_history_compare(self, entry_id: str) -> None:
        self.run_history_manager.request_comparison(entry_id)
        if self.run_history_dock.isHidden():
            self.run_history_dock.show()
        self.run_history_dock.raise_()

    def _on_run_history_open(self, entry_id: str) -> None:
        self.run_history_manager.request_open(entry_id)
        if self.run_history_dock.isHidden():
            self.run_history_dock.show()

    def _show_run_comparison(self, reference: RunHistoryEntry, target: RunHistoryEntry) -> None:
        if self.run_history_dock.isHidden():
            self.run_history_dock.show()
        self.run_history_dock.raise_()
        self.run_history_dock.show_comparison(reference, target)

    def _on_history_entry_added(self, _entry: RunHistoryEntry) -> None:
        if self.run_history_dock.isHidden():
            self.run_history_dock.show()

    def closeEvent(self, event) -> None:
        """Handle window closure."""
        try:
            # Stop any running analysis first
            if hasattr(self, 'analysis_manager'):
                self.analysis_manager.cleanup()

            # Close database connections
            try:
                flush_pending_writes()
                close_all_connections()
                logger.info("All database connections closed successfully")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}", exc_info=True)
                
            # Clean up configuration manager
            try:
                try:
                    self._config_manager.remove_change_listener(self._handle_config_change)
                except Exception as exc:
                    logger.debug("Unable to detach config listener during close: %s", exc)
                self._config_manager.cleanup()
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

    # ------------------------------------------------------------------
    # Configuration synchronisation
    # ------------------------------------------------------------------

    def _handle_config_change(self) -> None:
        self._sync_theme_from_config()

    def _sync_theme_from_config(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        try:
            theme = ThemeManager.get_saved_theme()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to read theme from configuration: %s", exc)
            return
        if not theme or theme == self._applied_theme:
            return
        try:
            ThemeManager.apply_theme(app, theme, persist=False)
            self._applied_theme = theme
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to apply theme from configuration: %s", exc)
