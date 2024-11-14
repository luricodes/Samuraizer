# samuraizer/backend/services/config_services.py

"""
This module serves as a bridge between the old and new configuration system.
It uses the new ConfigurationManager to provide configuration values.
"""

from samuraizer.config import ConfigurationManager

# Initialize configuration manager
config_manager = ConfigurationManager()

# Database configuration
CACHE_DB_FILE = '.repo_structure_cache.db'

# Default maximum file size in megabytes
DEFAULT_MAX_FILE_SIZE_MB = 50

# Get configuration values from the manager
DEFAULT_EXCLUDED_FOLDERS = config_manager.exclusion_config.get_excluded_folders()
DEFAULT_EXCLUDED_FILES = config_manager.exclusion_config.get_excluded_files()
DEFAULT_IMAGE_EXTENSIONS = config_manager.exclusion_config.get_image_extensions()

# Re-export all constants for backward compatibility
__all__ = [
    'CACHE_DB_FILE',
    'DEFAULT_MAX_FILE_SIZE_MB',
    'DEFAULT_EXCLUDED_FOLDERS',
    'DEFAULT_EXCLUDED_FILES',
    'DEFAULT_IMAGE_EXTENSIONS',
    'config_manager'  # Export config_manager for direct access
]
