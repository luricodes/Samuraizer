# samuraizer/config/config_manager.py

import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Set, List, ClassVar, Callable, TypeVar, Generic
from .exclusion_config import ExclusionConfig

logger = logging.getLogger(__name__)

# Custom exceptions for better error handling
class ConfigError(Exception):
    """Base exception for configuration errors"""
    pass

class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails"""
    pass

class ConfigSaveError(ConfigError):
    """Raised when configuration save fails"""
    pass

# Type variable for GUI widget types
WidgetType = TypeVar('WidgetType')

class ConfigurationManager(Generic[WidgetType]):
    """Manages configuration across GUI and CLI interfaces."""
    
    _instance: ClassVar[Optional['ConfigurationManager']] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    
    def __new__(cls) -> 'ConfigurationManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigurationManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the configuration manager."""
        if self._initialized:
            return
            
        with self._lock:
            # Core components
            self.exclusion_config = ExclusionConfig()
            self._change_callbacks: List[Callable[[], None]] = []
            self._initialized = True
    
    @classmethod
    def cleanup(cls) -> None:
        """Clean up the singleton instance."""
        try:
            # Use a timeout to prevent hanging
            acquired = cls._lock.acquire(timeout=2.0)
            if not acquired:
                logger.warning("Could not acquire lock for cleanup, forcing cleanup")
                cls._force_cleanup()
                return

            try:
                if cls._instance is not None:
                    try:
                        # Clean up ExclusionConfig first
                        if hasattr(cls._instance, 'exclusion_config'):
                            cls._instance.exclusion_config.cleanup()
                        
                        # Clear callbacks
                        if hasattr(cls._instance, '_change_callbacks'):
                            cls._instance._change_callbacks.clear()
                        
                        # Reset initialization flag
                        cls._instance._initialized = False
                        
                        # Clear the instance
                        cls._instance = None
                        
                        logger.debug("ConfigurationManager cleaned up successfully")
                    except Exception as e:
                        logger.error(f"Error during ConfigurationManager cleanup: {e}")
                        # Even if cleanup fails, ensure instance is reset
                        cls._instance = None
            finally:
                cls._lock.release()
        except Exception as e:
            logger.error(f"Error during cleanup process: {e}")
            cls._force_cleanup()

    @classmethod
    def _force_cleanup(cls) -> None:
        """Force cleanup when normal cleanup fails."""
        try:
            if cls._instance is not None:
                if hasattr(cls._instance, '_change_callbacks'):
                    cls._instance._change_callbacks.clear()
                cls._instance._initialized = False
                cls._instance = None
            logger.warning("Forced cleanup completed")
        except Exception as e:
            logger.error(f"Error during forced cleanup: {e}")
    
    def validate_configuration(self) -> bool:
        """Validate the current configuration state."""
        try:
            # Validate excluded folders
            excluded_folders = self.exclusion_config.get_excluded_folders()
            if not isinstance(excluded_folders, set):
                raise ConfigValidationError("Excluded folders must be a set")
            
            # Validate excluded files
            excluded_files = self.exclusion_config.get_excluded_files()
            if not isinstance(excluded_files, set):
                raise ConfigValidationError("Excluded files must be a set")
            
            # Validate patterns
            patterns = self.exclusion_config.get_exclude_patterns()
            if not isinstance(patterns, list):
                raise ConfigValidationError("Exclude patterns must be a list")
            
            # Validate image extensions
            image_exts = self.exclusion_config.get_image_extensions()
            if not isinstance(image_exts, set):
                raise ConfigValidationError("Image extensions must be a set")
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_merged_exclusions(self, 
                            additional_folders: Optional[Set[str]] = None,
                            additional_files: Optional[Set[str]] = None,
                            additional_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get merged exclusions from config file and additional inputs."""
        if not self.validate_configuration():
            raise ConfigValidationError("Invalid configuration state")
            
        with self._lock:
            try:
                config_folders = self.exclusion_config.get_excluded_folders()
                config_files = self.exclusion_config.get_excluded_files()
                config_patterns = self.exclusion_config.get_exclude_patterns()
                
                # Merge with additional exclusions if provided
                excluded_folders = config_folders | (additional_folders or set())
                excluded_files = config_files | (additional_files or set())
                exclude_patterns = list(set(config_patterns + (additional_patterns or [])))
                
                return {
                    'excluded_folders': excluded_folders,
                    'excluded_files': excluded_files,
                    'exclude_patterns': exclude_patterns,
                    'image_extensions': self.exclusion_config.get_image_extensions()
                }
            except Exception as e:
                raise ConfigError(f"Error merging exclusions: {e}")
    
    def update_gui_filters(self, file_filters_widget: WidgetType) -> None:
        """Update GUI filter widgets with current config values."""
        with self._lock:
            try:
                if not hasattr(file_filters_widget, 'folders_list') or \
                   not hasattr(file_filters_widget, 'files_list') or \
                   not hasattr(file_filters_widget, 'patterns_list') or \
                   not hasattr(file_filters_widget, 'image_list'):
                    raise ConfigError("Invalid widget structure")
                
                # Update excluded folders
                excluded_folders = self.exclusion_config.get_excluded_folders()
                file_filters_widget.folders_list.setItems(excluded_folders)
                
                # Update excluded files
                excluded_files = self.exclusion_config.get_excluded_files()
                file_filters_widget.files_list.setItems(excluded_files)
                
                # Update patterns
                exclude_patterns = self.exclusion_config.get_exclude_patterns()
                file_filters_widget.patterns_list.setPatterns(exclude_patterns)
                
                # Update image extensions
                image_extensions = self.exclusion_config.get_image_extensions()
                file_filters_widget.image_list.setItems(image_extensions)
                
                logger.debug("GUI filters updated from config file")
                self._notify_change()
                
            except Exception as e:
                logger.error(f"Failed to update GUI filters: {e}")
                raise ConfigError(f"Failed to update GUI filters: {e}")
    
    def save_gui_filters(self, file_filters_widget: WidgetType) -> None:
        """Save current GUI filter settings to config file."""
        with self._lock:
            try:
                if not hasattr(file_filters_widget, 'get_configuration'):
                    raise ConfigError("Invalid widget: missing get_configuration method")
                
                # Get current GUI values
                current_config = file_filters_widget.get_configuration()
                
                # Validate configuration structure
                required_keys = {'excluded_folders', 'excluded_files', 'exclude_patterns', 'image_extensions'}
                if not all(key in current_config for key in required_keys):
                    raise ConfigValidationError("Missing required configuration keys")
                
                # Clear existing configuration
                self.exclusion_config.config['exclusions']['folders'] = []
                self.exclusion_config.config['exclusions']['files'] = []
                self.exclusion_config.config['exclusions']['patterns'] = []
                self.exclusion_config.config['image_extensions'] = []
                
                # Update exclusion config
                for folder in current_config['excluded_folders']:
                    self.exclusion_config.add_excluded_folder(folder)
                    
                for file in current_config['excluded_files']:
                    self.exclusion_config.add_excluded_file(file)
                    
                for pattern in current_config['exclude_patterns']:
                    self.exclusion_config.add_exclude_pattern(pattern)
                    
                for extension in current_config['image_extensions']:
                    self.exclusion_config.add_image_extension(extension)
                    
                # Save changes
                self.exclusion_config._save_config()
                logger.debug("GUI filters saved to config file")
                self._notify_change()
                
            except Exception as e:
                logger.error(f"Failed to save GUI filters: {e}")
                raise ConfigSaveError(f"Failed to save GUI filters: {e}")
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        with self._lock:
            try:
                self.exclusion_config.reset_to_defaults()
                logger.info("Configuration reset to defaults")
                self._notify_change()
            except Exception as e:
                logger.error(f"Failed to reset configuration: {e}")
                raise ConfigError(f"Failed to reset configuration: {e}")
    
    def add_change_listener(self, callback: Callable[[], None]) -> None:
        """Add a callback to be notified of configuration changes."""
        with self._lock:
            if callback not in self._change_callbacks:
                self._change_callbacks.append(callback)
    
    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        """Remove a change notification callback."""
        with self._lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
    
    def _notify_change(self) -> None:
        """Notify all registered callbacks of configuration changes."""
        for callback in self._change_callbacks[:]:  # Create a copy to avoid modification during iteration
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")
