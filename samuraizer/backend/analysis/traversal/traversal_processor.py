from typing import Any, Dict, List, Set, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from tqdm import tqdm
from pathlib import Path
import logging
import sys
import io

from .traversal_core import traverse_and_collect
from ..file_processor import process_file
from ...services.event_service.cancellation import CancellationToken

def get_directory_structure(
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: List[str],
    threads: int,
    encoding: str = 'utf-8',
    hash_algorithm: Optional[str] = "xxhash",
    progress_callback: Optional[Callable[[int], None]] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:

    dir_structure: Dict[str, Any] = {}

    files_to_process, included_files, excluded_files_count = traverse_and_collect(
        root_dir,
        excluded_folders,
        excluded_files,
        exclude_patterns,
        follow_symlinks,
        cancellation_token=cancellation_token,
    )
    total_files: int = included_files + excluded_files_count
    excluded_percentage: float = (excluded_files_count / total_files * 100) if total_files else 0.0

    logging.debug(f"Total number of files: {total_files}")
    logging.debug(f"Excluded files: {excluded_files_count} ({excluded_percentage:.2f}%)")
    logging.debug(f"Processed files: {included_files}")
    
    # Create a fallback file object if sys.stdout is None or not available
    file_out = sys.stdout if hasattr(sys, 'stdout') and sys.stdout is not None else io.StringIO()
    
    pbar: tqdm = tqdm(
        total=included_files,
        desc="Process files",
        unit="file",
        dynamic_ncols=True,
        file=file_out
    )

    failed_files: List[Dict[str, str]] = []
    processed_count: int = 0  # Track processed files for progress updates

    with ThreadPoolExecutor(max_workers=threads) as executor:
        future_to_file: Dict[Future[Tuple[str, Any]], Path] = {}
        try:
            for file_path in files_to_process:
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    # Cancel all pending futures when stop is requested
                    for future in future_to_file.keys():
                        future.cancel()
                    break
                future = executor.submit(
                    process_file,
                    file_path,
                    max_file_size,
                    include_binary,
                    image_extensions,
                    encoding=encoding,
                    hash_algorithm=hash_algorithm,  # Pass the hash_algorithm parameter
                )
                future_to_file[future] = file_path
        except KeyboardInterrupt:
            logging.warning("\nCancellation by user. Attempts to terminate running tasks...")
            for future in future_to_file.keys():
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            pbar.close()
            raise
        except Exception as e:
            logging.error(f"Unexpected error during submission of tasks: {e}")
            for future in future_to_file.keys():
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            pbar.close()
            raise

        try:
            for future in as_completed(future_to_file):
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    # Cancel remaining futures when stop is requested
                    for remaining_future in future_to_file.keys():
                        if not remaining_future.done():
                            remaining_future.cancel()
                    break
                
                file_path: Path = future_to_file[future]
                try:
                    # Only process result if the future wasn't cancelled
                    if not future.cancelled():
                        filename, file_info = future.result()
                        if file_info is not None:
                            try:
                                relative_parent: Path = file_path.parent.relative_to(root_dir)
                            except ValueError:
                                relative_parent = file_path.parent

                            current: Dict[str, Any] = dir_structure
                            for part in relative_parent.parts:
                                current = current.setdefault(part, {})
                            current[filename] = file_info
                except Exception as e:
                    if not future.cancelled():  # Only log errors for non-cancelled futures
                        try:
                            relative_parent: Path = file_path.parent.relative_to(root_dir)
                        except ValueError:
                            relative_parent = file_path.parent

                        current: Dict[str, Any] = dir_structure
                        for part in relative_parent.parts:
                            current = current.setdefault(part, {})
                        current[
                            file_path.name
                        ] = {
                            "type": "error",
                            "content": f"Errors during processing: {str(e)}"
                        }
                        logging.error(f"Error when processing the file {file_path}: {e}")
                        failed_files.append(
                            {"file": str(file_path), "error": str(e)}
                        )
                finally:
                    if not future.cancelled():  # Only update progress for completed tasks
                        processed_count += 1
                        pbar.update(1)
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(processed_count)

        except KeyboardInterrupt:
            logging.warning("\nCancellation by user during processing. Attempts to terminate running tasks...")
            for future in future_to_file.keys():
                if not future.done():
                    future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            pbar.close()
            raise

    pbar.close()

    # If analysis was stopped, adjust the summary
    if cancellation_token and cancellation_token.is_cancellation_requested():
        # Count completed futures that weren't cancelled
        completed_files = sum(1 for future in future_to_file.keys() if future.done() and not future.cancelled())
        logging.info(f"Analysis was stopped. {completed_files} files were processed.")
        included_files = completed_files

    summary: Dict[str, Any] = {
        "total_files": total_files,
        "excluded_files": excluded_files_count,
        "included_files": included_files,
        "excluded_percentage": excluded_percentage,
        "failed_files": failed_files,
        "stopped_early": bool(cancellation_token and cancellation_token.is_cancellation_requested())
    }

    if hash_algorithm is not None:
        summary["hash_algorithm"] = hash_algorithm

    # Keep summary logs at INFO level since they provide important overview information
    logging.info("Analysis Summary:")
    logging.info(f"  Processed files: {included_files}")
    logging.info(f"  Excluded files: {excluded_files_count} ({excluded_percentage:.2f}%)")
    if len(failed_files) > 0:
        logging.info(f"  Failed files: {len(failed_files)}")
    if cancellation_token and cancellation_token.is_cancellation_requested():
        logging.info("  Analysis was stopped before completion")
    if hash_algorithm is not None:
        logging.info(f"  Hash algorithm used: {hash_algorithm}")

    return dir_structure, summary
