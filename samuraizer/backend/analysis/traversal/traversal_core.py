from pathlib import Path
from typing import List, Set, Tuple
import logging
from colorama import Fore, Style

from ....backend.services.pattern_service import matches_patterns
from ...services.event_service.events import shutdown_event

def traverse_and_collect(
    root_dir: Path,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    exclude_patterns: List[str],
    follow_symlinks: bool
) -> Tuple[List[Path], int, int]:
    paths: List[Path] = []
    included = 0
    excluded = 0
    visited_paths: Set[Path] = set()

    stack = [root_dir]

    while stack:
        if shutdown_event.is_set():
            logging.debug("Traversal aborted due to shutdown event.")
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
                if shutdown_event.is_set():
                    logging.debug("Traversal aborted due to shutdown event.")
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
                        excluded += 1
                        continue
                    paths.append(entry)
                    included += 1
        except PermissionError as e:
            logging.warning(
                f"{Fore.YELLOW}Could not read directory: {current_dir} - {e}{Style.RESET_ALL}"
            )
        except Exception as e:
            logging.error(
                f"{Fore.RED}Errors when passing through {current_dir}: {e}{Style.RESET_ALL}"
            )

    return paths, included, excluded
