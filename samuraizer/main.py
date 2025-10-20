from samuraizer.core.application import run as cli_run
from samuraizer.gui.main import main as gui_main
import sys

__all__ = ["run"]

def run():
    """
    Main entry point that handles both CLI and GUI modes.
    - When run with arguments, operates in CLI mode
    - When run without arguments (e.g. double-clicked), launches GUI
    """
    if len(sys.argv) == 1:  # No arguments provided (e.g. double-clicked)
        gui_main()
    else:
        cli_run()

if __name__ == "__main__":
    run()
