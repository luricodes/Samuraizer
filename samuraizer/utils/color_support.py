# samuraizer/utils/color_support.py

import os
import sys
from typing import Optional
from functools import lru_cache
from colorama import init as colorama_init, Fore, Back, Style, AnsiToWin32

class ColorSupport:
    """Manages color support detection and application."""
    
    def __init__(self):
        self._initialized = False
        self._force_color: Optional[bool] = None
        self._setup_color_support()

    def _setup_color_support(self) -> None:
        """Initialize color support with proper platform detection."""
        if self._initialized:
            return

        # Determine if colors should be forced or disabled
        force_color = os.environ.get('FORCE_COLOR', '').lower()
        no_color = os.environ.get('NO_COLOR') is not None
        
        if no_color:
            self._force_color = False
        elif force_color in ('1', 'true', 'yes'):
            self._force_color = True
        
        # Initialize colorama with appropriate settings
        colorama_init(
            strip=not self.supports_color(),
            convert=True,
            wrap=True,
            autoreset=True
        )
        
        self._initialized = True

    @lru_cache(maxsize=1)
    def supports_color(self) -> bool:
        """Determine if the current environment supports color output."""
        if self._force_color is not None:
            return self._force_color

        # Check for specific terminal types
        term = os.environ.get('TERM', '').lower()
        colorterm = os.environ.get('COLORTERM', '').lower()
        
        if 'dumb' in term:
            return False

        # Platform specific checks
        plat = sys.platform
        if plat == 'win32':
            return (
                'ANSICON' in os.environ or
                'WT_SESSION' in os.environ or  # Windows Terminal
                'ConEmuANSI' in os.environ or  # ConEmu
                os.environ.get('TERM_PROGRAM', '') == 'vscode'  # VS Code terminal
            )

        # Check if running in a proper terminal
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            return True

        # Check for known color-supporting environments
        return bool(
            colorterm or
            term in ('xterm-color', 'xterm-256color', 'screen', 'screen-256color')
        )

    def colored(self, text: str, color: Optional[str] = None, 
                background: Optional[str] = None, 
                bright: bool = False) -> str:
        """
        Apply color to text if supported.
        
        Args:
            text: The text to color
            color: Foreground color (Fore.*)
            background: Background color (Back.*)
            bright: Whether to apply bright style
        
        Returns:
            Colored text if supported, original text otherwise
        """
        if not self.supports_color() or not text:
            return text

        result = []
        if bright:
            result.append(Style.BRIGHT)
        if color:
            result.append(color)
        if background:
            result.append(background)
            
        result.append(str(text))
        result.append(Style.RESET_ALL)
        
        return ''.join(result)

    def error(self, text: str) -> str:
        """Format text as error message."""
        return self.colored(text, Fore.RED)

    def warning(self, text: str) -> str:
        """Format text as warning message."""
        return self.colored(text, Fore.YELLOW)

    def success(self, text: str) -> str:
        """Format text as success message."""
        return self.colored(text, Fore.GREEN)

    def info(self, text: str) -> str:
        """Format text as info message."""
        return self.colored(text, Fore.CYAN)

# Global instance
color_support = ColorSupport()
