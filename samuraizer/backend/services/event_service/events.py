# samuraizer/common/events.py

"""
Shared event objects for cross-module communication.
This module contains thread-safe events that can be used across
different parts of the application without creating circular dependencies.
"""

import threading
from typing import Final

# Thread-safe event for signalling a global shutdown
shutdown_event: Final[threading.Event] = threading.Event()

__all__ = ['shutdown_event']