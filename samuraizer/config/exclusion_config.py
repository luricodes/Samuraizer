# samuraizer/config/exclusion_config.py

from typing import Dict, Any, Set, Optional, List, Callable, ClassVar
import yaml
from pathlib import Path
import logging
import os
import threading
from colorama import Fore, Style

logger = logging.getLogger(__name__)

class ExclusionConfigError(Exception):
    """Base exception for exclusion configuration errors."""
    pass

class ConfigValidationError(ExclusionConfigError):
    """Raised when configuration validation fails."""
    pass

class ConfigIOError(ExclusionConfigError):
    """Raised when configuration file operations fail."""
    pass

# Default configuration as a frozen constant
DEFAULT_CONFIG: Dict[str, Any] = {
    "exclusions": {
        "folders": [
            "tmp", "node_modules", ".git", "dist", "build", "out", "target",
            "public", "temp", "coverage", "test-results", "reports", ".vscode",
            ".idea", "logs", "assets", "bower_components", ".next", "venv",
            "tests", "__pycache__", ".mypy_cache",
            ".cache", "lib"
        ],
        "files": [
            "config.json", "secret.txt", "package-lock.json", "favicon.ico",
            ".repo_structure_cache",
            ".repo_structure_cache.db", ".gitignore"
        ],
        "patterns": [
            "*.pyc", "*.pyo", "*.pyd", ".DS_Store", "Thumbs.db"
        ]
    },
    "image_extensions": [
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"
    ]
}

class ExclusionConfig:
    """Manages user-defined exclusion configurations."""
    
    _lock: ClassVar[threading.Lock] = threading.Lock()
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the exclusion configuration manager."""
        self._change_callbacks: List[Callable[[], None]] = []
        self.config_dir = config_dir or self._get_default_config_dir()
        self.config_file = self.config_dir / "exclusions.yaml"
        # Initialize with default config first
        self.config = DEFAULT_CONFIG.copy()
        # Then try to load from file
        try:
            loaded_config = self._load_or_create_config()
            if loaded_config:
                self.config = loaded_config
        except Exception as e:
            logger.error(f"Failed to load config, using defaults: {e}")
        
    def validate_configuration(self) -> bool:
        """Validate the current configuration structure and types."""
        try:
            if not hasattr(self, 'config'):
                raise ConfigValidationError("Configuration not initialized")
                
            if 'exclusions' not in self.config:
                raise ConfigValidationError("Missing 'exclusions' section")
                
            if not isinstance(self.config['exclusions'].get('folders', []), list):
                raise ConfigValidationError("'folders' must be a list")
                
            if not isinstance(self.config['exclusions'].get('files', []), list):
                raise ConfigValidationError("'files' must be a list")
                
            if not isinstance(self.config['exclusions'].get('patterns', []), list):
                raise ConfigValidationError("'patterns' must be a list")
                
            if not isinstance(self.config.get('image_extensions', []), list):
                raise ConfigValidationError("'image_extensions' must be a list")
                
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
            
    def _get_default_config_dir(self) -> Path:
        """Get the default configuration directory based on the platform."""
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('APPDATA', '')) / "Samuraizer"
        else:  # Unix-like
            base_dir = Path.home() / ".config" / "Samuraizer"
            
        return base_dir
        
    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigIOError(f"Failed to create config directory: {e}")
            
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing config or create default one if it doesn't exist."""
        try:
            # Use a timeout to prevent hanging
            acquired = self._lock.acquire(timeout=2.0)
            if not acquired:
                logger.warning("Could not acquire lock for loading config, using defaults")
                return DEFAULT_CONFIG.copy()

            try:
                self._ensure_config_dir()
                
                if not self.config_file.exists():
                    return self._create_default_config()
                    
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        
                    merged_config = self._merge_with_defaults(config or {})
                    if not self.validate_configuration():
                        logger.warning("Invalid configuration loaded, using defaults")
                        return DEFAULT_CONFIG.copy()
                        
                    return merged_config
                    
                except Exception as e:
                    raise ConfigIOError(f"Error loading config file: {e}")
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in load_or_create_config: {e}")
            return DEFAULT_CONFIG.copy()
                
    def _create_default_config(self) -> Dict[str, Any]:
        """Create and save the default configuration file."""
        try:
            self._save_config_to_file(DEFAULT_CONFIG)
            logger.info(f"Created default config file at: {self.config_file}")
            return DEFAULT_CONFIG.copy()
        except Exception as e:
            raise ConfigIOError(f"Failed to create default config: {e}")
            
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge loaded config with defaults to ensure all required fields exist."""
        merged = DEFAULT_CONFIG.copy()
        
        if 'exclusions' in config:
            if 'folders' in config['exclusions']:
                merged['exclusions']['folders'] = list(set(config['exclusions']['folders']))
            if 'files' in config['exclusions']:
                merged['exclusions']['files'] = list(set(config['exclusions']['files']))
            if 'patterns' in config['exclusions']:
                merged['exclusions']['patterns'] = list(set(config['exclusions']['patterns']))
                
        if 'image_extensions' in config:
            merged['image_extensions'] = list(set(config['image_extensions']))
            
        return merged

    def get_excluded_folders(self) -> Set[str]:
        """Get the set of excluded folder names."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for get_excluded_folders")
                return set(DEFAULT_CONFIG['exclusions']['folders'])
            try:
                return set(self.config['exclusions']['folders'])
            finally:
                self._lock.release()
        except Exception:
            return set(DEFAULT_CONFIG['exclusions']['folders'])
        
    def get_excluded_files(self) -> Set[str]:
        """Get the set of excluded file names."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for get_excluded_files")
                return set(DEFAULT_CONFIG['exclusions']['files'])
            try:
                return set(self.config['exclusions']['files'])
            finally:
                self._lock.release()
        except Exception:
            return set(DEFAULT_CONFIG['exclusions']['files'])
        
    def get_exclude_patterns(self) -> List[str]:
        """Get the list of exclusion patterns."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for get_exclude_patterns")
                return DEFAULT_CONFIG['exclusions']['patterns'].copy()
            try:
                return self.config['exclusions']['patterns'].copy()
            finally:
                self._lock.release()
        except Exception:
            return DEFAULT_CONFIG['exclusions']['patterns'].copy()
        
    def get_image_extensions(self) -> Set[str]:
        """Get the set of image file extensions."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for get_image_extensions")
                return set(DEFAULT_CONFIG['image_extensions'])
            try:
                return set(self.config['image_extensions'])
            finally:
                self._lock.release()
        except Exception:
            return set(DEFAULT_CONFIG['image_extensions'])

    def add_excluded_folder(self, folder: str) -> None:
        """Add a folder to the exclusion list."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for add_excluded_folder")
                return
            try:
                if folder not in self.config['exclusions']['folders']:
                    self.config['exclusions']['folders'].append(folder)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in add_excluded_folder: {e}")
            
    def add_excluded_file(self, file: str) -> None:
        """Add a file to the exclusion list."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for add_excluded_file")
                return
            try:
                if file not in self.config['exclusions']['files']:
                    self.config['exclusions']['files'].append(file)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in add_excluded_file: {e}")
            
    def add_exclude_pattern(self, pattern: str) -> None:
        """Add an exclusion pattern."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for add_exclude_pattern")
                return
            try:
                if pattern not in self.config['exclusions']['patterns']:
                    self.config['exclusions']['patterns'].append(pattern)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in add_exclude_pattern: {e}")
            
    def add_image_extension(self, extension: str) -> None:
        """Add an image file extension."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for add_image_extension")
                return
            try:
                if not extension.startswith('.'):
                    extension = f".{extension}"
                if extension not in self.config['image_extensions']:
                    self.config['image_extensions'].append(extension)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in add_image_extension: {e}")
            
    def remove_excluded_folder(self, folder: str) -> None:
        """Remove a folder from the exclusion list."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for remove_excluded_folder")
                return
            try:
                if folder in self.config['exclusions']['folders']:
                    self.config['exclusions']['folders'].remove(folder)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in remove_excluded_folder: {e}")
            
    def remove_excluded_file(self, file: str) -> None:
        """Remove a file from the exclusion list."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for remove_excluded_file")
                return
            try:
                if file in self.config['exclusions']['files']:
                    self.config['exclusions']['files'].remove(file)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in remove_excluded_file: {e}")
            
    def remove_exclude_pattern(self, pattern: str) -> None:
        """Remove an exclusion pattern."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for remove_exclude_pattern")
                return
            try:
                if pattern in self.config['exclusions']['patterns']:
                    self.config['exclusions']['patterns'].remove(pattern)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in remove_exclude_pattern: {e}")
            
    def remove_image_extension(self, extension: str) -> None:
        """Remove an image file extension."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for remove_image_extension")
                return
            try:
                if not extension.startswith('.'):
                    extension = f".{extension}"
                if extension in self.config['image_extensions']:
                    self.config['image_extensions'].remove(extension)
                    self._save_config()
                    self._notify_change()
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in remove_image_extension: {e}")

    def _save_config_to_file(self, config_data: Dict[str, Any]) -> None:
        """Save configuration data to file with proper resource handling."""
        temp_file = self.config_file.with_suffix('.yaml.tmp')
        try:
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            # Rename temporary file to actual config file
            # This ensures atomic write operation
            temp_file.replace(self.config_file)
            
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise ConfigIOError(f"Failed to save configuration: {e}")

    def _save_config(self) -> None:
        """Save the current configuration to file."""
        try:
            if not self.validate_configuration():
                raise ConfigValidationError("Invalid configuration state")
                
            self._save_config_to_file(self.config)
            logger.debug("Configuration saved successfully")
        except Exception as e:
            raise ConfigIOError(f"Failed to save configuration: {e}")
            
    def reset_to_defaults(self) -> None:
        """Reset the configuration to default values."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for reset_to_defaults")
                return
            try:
                self.config = DEFAULT_CONFIG.copy()
                self._save_config()
                self._notify_change()
                logger.info("Configuration reset to defaults")
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in reset_to_defaults: {e}")

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        """Add a callback to be notified of configuration changes."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for add_change_listener")
                return
            try:
                if callback not in self._change_callbacks:
                    self._change_callbacks.append(callback)
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in add_change_listener: {e}")

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        """Remove a change notification callback."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for remove_change_listener")
                return
            try:
                if callback in self._change_callbacks:
                    self._change_callbacks.remove(callback)
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in remove_change_listener: {e}")

    def _notify_change(self) -> None:
        """Notify all registered callbacks of configuration changes."""
        callbacks = self._change_callbacks.copy()
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            acquired = self._lock.acquire(timeout=1.0)
            if not acquired:
                logger.warning("Could not acquire lock for cleanup, proceeding without lock")
                self._force_cleanup()
                return
            try:
                self._save_config()
                self._change_callbacks.clear()
            except Exception as e:
                logger.error(f"Error during ExclusionConfig cleanup: {e}")
            finally:
                self._lock.release()
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            self._force_cleanup()

    def _force_cleanup(self) -> None:
        """Force cleanup when normal cleanup fails."""
        try:
            self._change_callbacks.clear()
        except Exception as e:
            logger.error(f"Error during forced cleanup: {e}")
