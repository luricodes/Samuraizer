import logging
import sys
from typing import Optional

from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.utils.color_support import color_support


class LoggerState:
    def __init__(self) -> None:
        self.logger = logging.getLogger()
        self.handlers = list(self.logger.handlers)
        self.level = self.logger.level
        self.force_color: Optional[bool] = getattr(color_support, "_force_color", None)

    def restore(self) -> None:
        # Close handlers added during the test to avoid resource leaks
        current_handlers = set(self.logger.handlers)
        original_handlers = set(self.handlers)
        for handler in current_handlers - original_handlers:
            try:
                handler.close()
            except Exception:
                pass

        self.logger.handlers.clear()
        for handler in self.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(self.level)
        color_support.set_force_color(self.force_color)


def test_setup_logging_force_color_true():
    state = LoggerState()
    try:
        setup_logging(force_color=True, preserve_existing_handlers=True)
        assert color_support.supports_color() is True
    finally:
        state.restore()


def test_setup_logging_force_color_false():
    state = LoggerState()
    try:
        setup_logging(force_color=False, preserve_existing_handlers=True)
        assert color_support.supports_color() is False
    finally:
        state.restore()


def test_setup_logging_resets_force_color_when_unspecified():
    state = LoggerState()
    baseline = color_support.supports_color()

    try:
        setup_logging(force_color=not baseline, preserve_existing_handlers=True)
        assert color_support.supports_color() is (not baseline)

        setup_logging(preserve_existing_handlers=True)
        assert color_support.supports_color() is baseline
    finally:
        state.restore()


def test_setup_logging_preserves_handlers_when_requested():
    state = LoggerState()
    sentinel = logging.NullHandler()
    state.logger.addHandler(sentinel)

    try:
        setup_logging(preserve_existing_handlers=True)
        assert sentinel in state.logger.handlers
    finally:
        state.logger.removeHandler(sentinel)
        state.restore()


def test_setup_logging_does_not_override_existing_console_formatter():
    state = LoggerState()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(levelname)s: %(message)s [custom]")
    handler.setFormatter(formatter)
    state.logger.addHandler(handler)

    try:
        setup_logging(preserve_existing_handlers=True)
        assert handler in state.logger.handlers
        assert handler.formatter is formatter
    finally:
        state.logger.removeHandler(handler)
        state.restore()
