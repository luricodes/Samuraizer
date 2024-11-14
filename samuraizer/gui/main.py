# samuraizer/gui/main.py
#!/usr/bin/env python3
import sys
import logging
from .app.application import setup_application
from .app.logger import setup_logging
from .app.theme_manager import ThemeManager
from .windows import MainWindow

def main() -> None:
    """Main application entry point."""
    try:
        # Set up logging first
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Initialize the Qt Application
        app = setup_application()
        
        # Set up the application style
        ThemeManager.setup_style(app)
        
        # Create main window
        window = MainWindow()
        
        # Set up theme toggle function
        def theme_toggle(theme=None):
            ThemeManager.toggle_theme(app, window, theme)
        
        # Assign the theme toggle function to the window
        window.toggle_theme = theme_toggle
        
        # Show the window
        window.show()
        
        # Start the event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
