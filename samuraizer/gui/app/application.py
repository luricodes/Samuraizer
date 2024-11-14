 # QApplication setup and configuration
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from .theme_manager import ThemeManager
from .logger import setup_logging

logger = logging.getLogger(__name__)

def setup_application() -> QApplication:
    """Initialize and configure the Qt Application."""
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Samuraizer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Lucas Richert")
    app.setOrganizationDomain("lucasrichert.tech")
    
    return app

def run_application(window_class) -> None:
    """
    Main application entry point.
    
    Args:
        window_class: The main window class to instantiate
    """
    try:
        # Set up logging first
        setup_logging()
        
        # Initialize the Qt Application
        app = setup_application()
        
        # Set up the application style
        ThemeManager.setup_style(app)
        
        # Create main window
        window = window_class()
        
        # Set up theme toggle function
        def theme_toggle():
            ThemeManager.toggle_theme(app, window)
        
        # Assign the theme toggle function to the window
        window.toggle_theme = theme_toggle
        
        # Show the window
        window.show()
        
        # Start the event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        sys.exit(1)
