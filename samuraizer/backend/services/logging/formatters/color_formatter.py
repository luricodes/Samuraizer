# samuraizer/logging/color_formatter.py

import logging
import datetime
from typing import Dict, Any
from colorama import Fore, Style
from .....utils.color_support import color_support

class ColorFormatter(logging.Formatter):
    """
    A logging formatter that applies colors consistently and safely.
    """
    
    # Define colors for different log levels
    LEVEL_COLORS: Dict[int, str] = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }
    
    # Define styles for different log components
    LEVEL_STYLES: Dict[str, Dict[str, Any]] = {
        'DEBUG': {'color': Fore.CYAN},
        'INFO': {'color': Fore.GREEN},
        'WARNING': {'color': Fore.YELLOW, 'bright': True},
        'ERROR': {'color': Fore.RED, 'bright': True},
        'CRITICAL': {'color': Fore.MAGENTA, 'bright': True},
    }

    def __init__(
        self,
        fmt: str = None,
        datefmt: str = None,
        style: str = '%',
        validate: bool = True
    ):
        super().__init__(
            fmt or self._get_default_format(),
            datefmt or self._get_default_datefmt(),
            style,
            validate
        )

    @staticmethod
    def _get_default_format() -> str:
        """Get the default log format."""
        return '%(asctime)s [%(levelname)s] %(message)s'

    @staticmethod
    def _get_default_datefmt() -> str:
        """Get the default date format."""
        return '%Y-%m-%d %H:%M:%S'

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors if supported.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log message string
        """
        # Save original values
        orig_msg = record.msg
        orig_levelname = record.levelname

        try:
            # Apply color to level name
            if color_support.supports_color():
                style = self.LEVEL_STYLES.get(record.levelname, {})
                record.levelname = color_support.colored(
                    record.levelname,
                    color=style.get('color'),
                    bright=style.get('bright', False)
                )

                # Apply color to message based on level
                if isinstance(record.msg, str):
                    color = self.LEVEL_COLORS.get(record.levelno)
                    if color:
                        record.msg = color_support.colored(record.msg, color)

            return super().format(record)
        finally:
            # Restore original values
            record.msg = orig_msg
            record.levelname = orig_levelname

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        """
        Format the time with millisecond precision.
        
        Args:
            record: The log record
            datefmt: Optional date format string
            
        Returns:
            Formatted timestamp string
        """
        ct = datetime.datetime.fromtimestamp(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            s = ct.strftime(self._get_default_datefmt())
        return s
