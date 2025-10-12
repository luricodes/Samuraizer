from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Set, Tuple, List
import logging
from colorama import Fore, Style

from ....backend.services.pattern_service import matches_patterns
from ...services.event_service.cancellation import CancellationToken


@dataclass
class TraversalCounters:
    """Mutable counters that track traversal statistics."""

    included: int = 0
    excluded: int = 0


def traverse_and_collect(
    root_dir: Path,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    exclude_patterns: List[str],
    follow_symlinks: bool,
    cancellation_token: Optional[CancellationToken] = None,
) -> Tuple[Iterator[Path], TraversalCounters]:
    """Yield files found during traversal while tracking statistics.

    Returns a tuple with a generator that lazily yields ``Path`` objects for
    every file that should be analysed and a :class:`TraversalCounters`
    instance with live statistics.  This avoids materialising the full list of
    files in memory and enables progressive processing of very large
    repositories.
    """

    counters = TraversalCounters()
    visited_paths: Set[Path] = set()

    def _iterator() -> Iterator[Path]:
        stack = [root_dir]

        while stack:
            if cancellation_token and cancellation_token.is_cancellation_requested():
                logging.debug("Traversal aborted due to cancellation request.")
                break

            current_dir = stack.pop()
            try:
                if follow_symlinks:
                    resolved_dir = current_dir.resolve()
                    if resolved_dir in visited_paths:
                        logging.warning(
                            f"{Fore.RED}Circular symbolic link found: {current_dir}{Style.RESET_ALL}"
                        )
                        continue
                    visited_paths.add(resolved_dir)
            except Exception as e:
                logging.error(
                    f"{Fore.RED}Error when resolving {current_dir}: {e}{Style.RESET_ALL}"
                )
                continue

            try:
                for entry in current_dir.iterdir():
                    if cancellation_token and cancellation_token.is_cancellation_requested():
                        logging.debug("Traversal aborted due to cancellation request.")
                        break

                    if entry.is_dir():
                        if (
                            entry.name in excluded_folders
                            or matches_patterns(entry.name, exclude_patterns)
                        ):
                            logging.debug(
                                f"{Fore.CYAN}Exclude folders: {entry}{Style.RESET_ALL}"
                            )
                            continue
                        stack.append(entry)
                    elif entry.is_file():
                        if (
                            entry.name in excluded_files
                            or matches_patterns(entry.name, exclude_patterns)
                        ):
                            logging.debug(
                                f"{Fore.YELLOW}Exclude file: {entry}{Style.RESET_ALL}"
                            )
                            counters.excluded += 1
                            continue
                        counters.included += 1
                        yield entry
            except PermissionError as e:
                logging.warning(
                    f"{Fore.YELLOW}Could not read directory: {current_dir} - {e}{Style.RESET_ALL}"
                )
            except Exception as e:
                logging.error(
                    f"{Fore.RED}Errors when passing through {current_dir}: {e}{Style.RESET_ALL}"
                )

    return _iterator(), counters
