import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def reload_module(module_name: str) -> ModuleType:
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_cli_parser_import_does_not_clear_existing_root_handlers():
    root_logger = logging.getLogger()
    sentinel_handler = logging.NullHandler()
    root_logger.addHandler(sentinel_handler)
    try:
        before_handlers = list(root_logger.handlers)
        reload_module("samuraizer.cli.parser")
        after_handlers = list(root_logger.handlers)
        assert after_handlers == before_handlers
    finally:
        root_logger.removeHandler(sentinel_handler)
