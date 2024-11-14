import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
from .formatters.color_formatter import ColorFormatter
from ....utils.color_support import color_support

def setup_logging(
    verbose: bool = False,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    force_color: bool = False
) -> None:
    """
    Set up logging with proper color support and file handling.
    
    Args:
        verbose: Enable debug logging if True
        log_file: Optional path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        force_color: Force color output regardless of terminal support
    """
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        try:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Create rotating file handler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            
            # Use a non-colored formatter for file output
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            logging.info(color_support.success(
                f"Log file initialized: {log_file}"
            ))
            
        except Exception as e:
            logging.error(color_support.error(
                f"Failed to initialize log file: {e}"
            ))

    # Log initial setup information
    if verbose:
        logging.debug(color_support.info("Verbose logging enabled"))
    logging.debug(color_support.info(
        f"Color support: {color_support.supports_color()}"
    ))
