import logging
from pathlib import Path
import sys

def setup_logging() -> None:
    """Configure application logging."""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "samuraizer_gui.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
