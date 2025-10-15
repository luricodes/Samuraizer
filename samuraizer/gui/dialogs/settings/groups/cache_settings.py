# samuraizer/gui/dialogs/components/settings/groups/cache_settings.py

from typing import Optional, TYPE_CHECKING, cast
import logging
import os
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QSpinBox,
    QCheckBox, QPushButton, QFileDialog,
    QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from samuraizer.backend.cache.connection_pool import set_cache_disabled
from samuraizer.backend.services.config_services import CACHE_DB_FILE
from ..base import BaseSettingsGroup

if TYPE_CHECKING:
    from ..settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

class CacheSettingsGroup(BaseSettingsGroup):
    """Group for cache-related settings."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        self._showing_cache_warning = False
        self._initial_cache_state: Optional[bool] = None
        super().__init__("Cache Settings", parent)

    def _get_settings_dialog(self) -> Optional['SettingsDialog']:
        try:
            from ..settings_dialog import SettingsDialog  # Local import to avoid circular
        except Exception:  # pragma: no cover - defensive
            return None

        parent = self.parent()
        while parent is not None:
            if isinstance(parent, SettingsDialog):
                return cast('SettingsDialog', parent)
            parent = parent.parent()
        return None

    def _show_parent_error(self, title: str, message: str) -> None:
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.show_error(title, message)

    def setup_ui(self) -> None:
        """Set up the cache settings UI."""
        try:
            layout = QFormLayout()
            layout.setSpacing(10)
            
            # Create warning label for cache disable
            self.cache_warning = QLabel(
                "Warning: Disabling the cache will significantly impact performance"
            )
            self.cache_warning.setStyleSheet("color: #FFA500;")  # Orange warning color
            self.cache_warning.setWordWrap(True)
            self.cache_warning.setFont(QFont("Segoe UI", 9))
            self.cache_warning.hide()  # Initially hidden
            layout.addRow(self.cache_warning)
            
            # Disable cache checkbox
            self.disable_cache = QCheckBox()
            self.disable_cache.setToolTip(
                "Disable file analysis caching.\n"
                "WARNING: This will significantly reduce performance running an Analysis multiple times!"
            )
            self.disable_cache.stateChanged.connect(self.on_cache_state_changed)
            layout.addRow("Disable caching:", self.disable_cache)
            
            # Cache cleanup interval
            self.cache_cleanup = QSpinBox()
            self.cache_cleanup.setRange(1, 30)
            self.cache_cleanup.setSuffix(" days")
            self.cache_cleanup.setToolTip("Number of days before cache cleanup")
            layout.addRow("Cache cleanup interval:", self.cache_cleanup)

            # Max cache size setting
            self.max_cache_size = QSpinBox()
            self.max_cache_size.setRange(100, 10000)  # 100MB to 10GB
            self.max_cache_size.setSuffix(" MB")
            self.max_cache_size.setToolTip("Maximum size of the cache in megabytes")
            layout.addRow("Max cache size:", self.max_cache_size)

            # Current cache size label
            self.current_cache_size = QLabel()
            self.current_cache_size.setStyleSheet("color: gray;")
            self.current_cache_size.setFont(QFont("Segoe UI", 9))
            layout.addRow("Current cache size:", self.current_cache_size)
            
            # Cache location with buttons in horizontal layout
            cache_layout = QHBoxLayout()
            
            self.cache_path = QPushButton("Select Path...")
            self.cache_path.clicked.connect(self.select_cache_path)
            cache_layout.addWidget(self.cache_path)
            
            self.reset_cache_btn = QPushButton("Reset to Default")
            self.reset_cache_btn.setToolTip("Reset cache path to default location")
            self.reset_cache_btn.clicked.connect(self.reset_cache_path)
            cache_layout.addWidget(self.reset_cache_btn)
            
            layout.addRow("Cache location:", cache_layout)
            
            self.cache_path_label = QLabel()
            self.cache_path_label.setFont(QFont("Segoe UI", 9))
            layout.addRow("", self.cache_path_label)
            
            self.setLayout(layout)
            
            # Update current cache size
            self.update_current_cache_size()
            
        except Exception as e:
            logger.error(f"Error setting up cache settings UI: {e}", exc_info=True)
            raise

    def get_cache_db_path(self) -> Path:
        """Get the path to the cache database file."""
        try:
            cache_path = self.cache_path_label.text()
            if cache_path.startswith("Using default:"):
                cache_path = cache_path.replace("Using default: ", "").strip()
            elif not cache_path:
                cache_path = str(Path.cwd() / ".cache")
            
            return Path(cache_path) / CACHE_DB_FILE
        except Exception as e:
            logger.error(f"Error getting cache DB path: {e}")
            return Path.cwd() / ".cache" / CACHE_DB_FILE

    def update_current_cache_size(self) -> None:
        """Update the current cache size display."""
        try:
            if self.disable_cache.isChecked():
                self.current_cache_size.setText("Cache disabled")
                return

            db_path = self.get_cache_db_path()
            if db_path.exists():
                # Get the main DB file size
                size_mb = db_path.stat().st_size / (1024 * 1024)
                
                # Also check for WAL and SHM files
                wal_path = db_path.with_suffix('.db-wal')
                shm_path = db_path.with_suffix('.db-shm')
                
                if wal_path.exists():
                    size_mb += wal_path.stat().st_size / (1024 * 1024)
                if shm_path.exists():
                    size_mb += shm_path.stat().st_size / (1024 * 1024)
                
                self.current_cache_size.setText(f"{size_mb:.2f} MB")
            else:
                self.current_cache_size.setText("0.00 MB")
        except Exception as e:
            logger.error(f"Error updating cache size: {e}")
            self.current_cache_size.setText("Error getting size")

    def reset_cache_path(self) -> None:
        """Reset the cache path to default location."""
        try:
            # Clear the actual path
            self.cache_path_label.clear()
            
            # Remove explicit override so the default applies
            self.config_manager.set_value("cache.path", None)

            cache_cfg = self.config_manager.get_active_profile_config().get("cache", {})
            default_path = cache_cfg.get("path") or str(Path.cwd() / ".cache")
            resolved_default = Path(str(default_path)).expanduser()
            self.cache_path_label.setText(f"Using default: {resolved_default}")
            
            # Show confirmation
            QMessageBox.information(
                self,
                "Cache Path Reset",
                f"Cache path has been reset to default location:\n{resolved_default}"
            )

            logger.warning(f"Cache path reset to default: {resolved_default}")
            logger.warning(f"Takes effect after program restart")

            # Update cache size display
            self.update_current_cache_size()
            
        except Exception as e:
            logger.error(f"Error resetting cache path: {e}")
            self._show_parent_error(
                "Reset Error",
                f"Failed to reset cache path: {str(e)}"
            )

    def select_cache_path(self) -> None:
        """Open dialog to select cache directory."""
        try:
            # Get current cache path or default to home directory
            cache_cfg = self.config_manager.get_active_profile_config().get("cache", {})
            current_cache = cache_cfg.get("path") or str(Path.home())
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "Select Cache Directory",
                current_cache,
                QFileDialog.Option.ShowDirsOnly
            )
            
            if dir_path:
                cache_path = Path(dir_path)
                # Try to create the directory if it doesn't exist
                try:
                    cache_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self._show_parent_error(
                        "Path Error",
                        f"Could not create cache directory: {str(e)}"
                    )
                    return

                # Check if directory is writable
                if not os.access(cache_path, os.W_OK):
                    self._show_parent_error(
                        "Permission Error",
                        "Selected directory is not writable"
                    )
                    return

                # Get absolute path
                try:
                    abs_path = str(cache_path.resolve())
                    self.cache_path_label.setText(abs_path)
                    logger.warning(f"Cache path updated: {abs_path}")
                    logger.warning("Takes effect after program restart")
                    self.config_manager.set_value("cache.path", abs_path)
                    # Update cache size display
                    self.update_current_cache_size()
                except Exception as e:
                    logger.error(f"Error resolving cache path: {e}")
                    # Fall back to original path if resolution fails
                    fallback_path = str(cache_path)
                    self.cache_path_label.setText(fallback_path)
                    self.config_manager.set_value("cache.path", fallback_path)

        except Exception as e:
            logger.error(f"Error selecting cache path: {e}", exc_info=True)
            self._show_parent_error("Path Selection Error", str(e))

    def on_cache_state_changed(self, state: int) -> None:
        """Handle cache disable/enable state changes."""
        try:
            cache_disabled = state == Qt.CheckState.Checked.value
            
            # Only show warning and confirmation when actively changing to disabled state
            # and it's different from the initial state
            if (cache_disabled and 
                not self._showing_cache_warning and 
                self._initial_cache_state != cache_disabled):
                
                self._showing_cache_warning = True
                # Show confirmation dialog when disabling cache
                result = QMessageBox.warning(
                    self,
                    "Disable Caching",
                    "Disabling the cache will significantly impact performance. "
                    "Are you sure you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                self._showing_cache_warning = False
                
                if result == QMessageBox.StandardButton.No:
                    self.disable_cache.blockSignals(True)  # Prevent recursion
                    self.disable_cache.setChecked(False)
                    self.disable_cache.blockSignals(False)
                    cache_disabled = False
            
            # Propagate runtime cache state immediately
            set_cache_disabled(cache_disabled)
            self.config_manager.set_value("analysis.cache_enabled", not cache_disabled)
            
            # Show/hide warning
            self.cache_warning.setVisible(cache_disabled)
            
            # Enable/disable cache controls
            self.cache_cleanup.setEnabled(not cache_disabled)
            self.cache_path.setEnabled(not cache_disabled)
            self.cache_path_label.setEnabled(not cache_disabled)
            self.reset_cache_btn.setEnabled(not cache_disabled)
            self.max_cache_size.setEnabled(not cache_disabled)
            
            # Update cache size display
            self.update_current_cache_size()

        except Exception as e:
            logger.error(f"Error handling cache state change: {e}", exc_info=True)
            self._show_parent_error("Settings Error", str(e))

    def load_settings(self) -> None:
        """Load cache settings."""
        try:
            config = self.config_manager.get_active_profile_config()
            analysis_cfg = config.get("analysis", {})
            cache_cfg = config.get("cache", {})

            self.disable_cache.blockSignals(True)

            disable_cache = not bool(analysis_cfg.get("cache_enabled", True))

            cleanup_days = int(cache_cfg.get("cleanup_days", 30) or 30)
            self.cache_cleanup.setValue(cleanup_days)

            size_limit = int(cache_cfg.get("size_limit_mb", 1000) or 1000)
            self.max_cache_size.setValue(size_limit)

            cache_path = cache_cfg.get("path") or str(Path.cwd() / ".cache")
            if cache_path:
                self.cache_path_label.setText(str(cache_path))
            else:
                default_path = Path.cwd() / ".cache"
                self.cache_path_label.setText(f"Using default: {default_path}")

            self._initial_cache_state = disable_cache
            self.disable_cache.setChecked(disable_cache)

            self.cache_warning.setVisible(disable_cache)
            self.cache_cleanup.setEnabled(not disable_cache)
            self.cache_path.setEnabled(not disable_cache)
            self.cache_path_label.setEnabled(not disable_cache)
            self.reset_cache_btn.setEnabled(not disable_cache)
            self.max_cache_size.setEnabled(not disable_cache)

            self.update_current_cache_size()
            self.disable_cache.blockSignals(False)

        except Exception as e:
            logger.error(f"Error loading cache settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save cache settings."""
        try:
            cache_disabled = self.disable_cache.isChecked()
            self.config_manager.set_value("analysis.cache_enabled", not cache_disabled)
            self.config_manager.set_value("cache.cleanup_days", self.cache_cleanup.value())
            self.config_manager.set_value("cache.size_limit_mb", self.max_cache_size.value())
            cache_path_display = self.cache_path_label.text().strip()
            if cache_path_display.startswith("Using default:") or not cache_path_display:
                self.config_manager.set_value("cache.path", None)
            else:
                try:
                    resolved_path = str(Path(cache_path_display).expanduser().resolve())
                except Exception as path_error:
                    logger.error("Error resolving cache path: %s", path_error)
                    resolved_path = cache_path_display
                self.config_manager.set_value("cache.path", resolved_path)
                
        except Exception as e:
            logger.error(f"Error saving cache settings: {e}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate cache settings."""
        try:
            # Validate cache path if cache is enabled and path is set
            if not self.disable_cache.isChecked():
                cache_path_text = self.cache_path_label.text()
                
                # Skip validation for default path display
                if cache_path_text.startswith("Using default:"):
                    # Extract the actual path from the text
                    cache_path_text = cache_path_text.replace("Using default: ", "").strip()
                    
                if cache_path_text:
                    cache_path = Path(cache_path_text)
                    if not cache_path.exists():
                        try:
                            cache_path.mkdir(parents=True, exist_ok=True)
                            logger.debug(f"Created cache directory: {cache_path}")
                        except Exception as e:
                            raise ValueError(
                                f"Cannot create cache directory: {str(e)}"
                            )
                    elif not cache_path.is_dir():
                        raise ValueError("Cache path exists but is not a directory")
                    elif not os.access(cache_path, os.W_OK):
                        raise ValueError("Cache directory is not writable")
            
            logger.debug("Cache settings validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Cache settings validation error: {e}", exc_info=True)
            self._show_parent_error("Validation Error", str(e))
            return False
