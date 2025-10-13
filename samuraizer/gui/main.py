#!/usr/bin/env python3
from .app.application import run_application
from .windows import MainWindow

def main() -> None:
    """Main application entry point."""
    run_application(MainWindow)

if __name__ == "__main__":
    main()
