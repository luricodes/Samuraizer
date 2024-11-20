import logging
from pathlib import Path
import sys

def setup_logging() -> None:
    """Configure application logging."""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels; handlers will filter appropriately
    
    # Remove existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Formatter for FileHandler (includes timestamp, name, level, and message)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Formatter for StreamHandler (only level and message, no tracebacks)
    stream_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # FileHandler to log all messages to a file
    file_handler = logging.FileHandler(log_dir / "samuraizer_gui.log", encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log all levels to the file
    file_handler.setFormatter(file_formatter)
    
    # StreamHandler to output warnings and errors to the console (GUI log panel) without tracebacks
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.WARNING)  # Only warnings and above to the console
    stream_handler.setFormatter(stream_formatter)
    
    # Add handlers to the root logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
