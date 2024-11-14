import fnmatch
import logging
import re
from functools import lru_cache
from typing import Pattern, Sequence

from colorama import Fore, Style
from samuraizer.config import ConfigurationManager

# Initialize configuration manager
config_manager = ConfigurationManager()

@lru_cache(maxsize=None)
def compile_regex(pattern: str) -> Pattern:
    """
    Compiles a regex pattern and caches it.

    Args:
        pattern (str): The regex pattern as a string.

    Returns:
        Pattern: The compiled regex pattern.
    """
    return re.compile(pattern)

def get_exclude_patterns() -> list[str]:
    """
    Gets the exclude patterns from the configuration.

    Returns:
        list[str]: List of exclude patterns
    """
    return config_manager.exclusion_config.get_exclude_patterns()

def matches_patterns(filename: str, patterns: Sequence[str] = None) -> bool:
    """
    Checks if the filename matches any of the patterns (Glob or Regex).

    Args:
        filename (str): The name of the file.
        patterns (Sequence[str], optional): A sequence of patterns (Glob or Regex).
            If None, uses patterns from config.

    Returns:
        bool: True if the filename matches any of the patterns, otherwise False.
    """
    if patterns is None:
        patterns = get_exclude_patterns()

    for pattern in patterns:
        if pattern.startswith('regex:'):
            regex: str = pattern[len('regex:'):]
            try:
                compiled: Pattern = compile_regex(regex)
                if compiled.match(filename):
                    return True
            except re.error as e:
                logging.error(
                    f"{Fore.RED}Invalid regex pattern '{regex}': {e}{Style.RESET_ALL}"
                )
        else:
            if fnmatch.fnmatch(filename, pattern):
                return True
    return False
