import datetime
from datetime import timezone, tzinfo
import logging
from typing import Any, Optional

def format_timestamp(timestamp: Any, target_tz: Optional[tzinfo] = None) -> str:
    """
    Formats a timestamp in ISO 8601 format.
    
    Args:
        timestamp: Unix timestamp to format
        target_tz: Optional target timezone. If None, uses UTC.
    
    Returns:
        Formatted timestamp string in ISO format with timezone information
    """
    if isinstance(timestamp, (int, float)):
        try:
            # First convert to UTC datetime
            utc_dt = datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc)
            
            # If target timezone specified, convert to it
            if target_tz:
                local_dt = utc_dt.astimezone(target_tz)
                return local_dt.isoformat()
            
            # Otherwise return UTC time
            return utc_dt.isoformat()
        except (OSError, OverflowError, ValueError):
            logging.warning(f"Invalid timestamp: {timestamp}")
            return ""
    return ""

def get_system_timezone() -> tzinfo:
    """
    Get the system's local timezone.
    
    Returns:
        The system's timezone
    """
    tz = datetime.datetime.now(timezone.utc).astimezone().tzinfo
    return tz if tz is not None else timezone.utc
