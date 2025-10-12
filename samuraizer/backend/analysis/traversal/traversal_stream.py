from typing import Generator, Dict, Any, List, Set, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from tqdm import tqdm
import logging

from .traversal_core import traverse_and_collect
from ..file_processor import process_file
from ...services.event_service.cancellation import CancellationToken

def get_directory_structure_stream(
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
    cancellation_token: Optional[CancellationToken] = None,
) -> Generator[Dict[str, Any], None, None]:
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
    
    pbar: tqdm = tqdm(
        total=included_files,
        desc="Process files",
        unit="file",
        dynamic_ncols=True
    )

    failed_files: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=threads) as executor:
        future_to_file: Dict[Future[Tuple[str, Any]], Path] = {}
        for file_path in files_to_process:
            if cancellation_token and cancellation_token.is_cancellation_requested():
                break
            future = executor.submit(
                process_file,
                file_path,
                max_file_size,
                include_binary,
                image_extensions,
                encoding=encoding,
                hash_algorithm=hash_algorithm,  # Pass hash_algorithm to process_file
            )
            future_to_file[future] = file_path

        try:
            for future in as_completed(future_to_file):
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    break
                file_path: Path = future_to_file[future]
                try:
                    filename, file_info = future.result()
                    if file_info is not None:
                        try:
                            relative_parent: Path = file_path.parent.relative_to(root_dir)
                        except ValueError:
                            relative_parent = file_path.parent

                        yield {
                            "parent": str(relative_parent),
                            "filename": filename,
                            "info": file_info
                        }
                except Exception as e:
                    logging.error(f"Error when processing the file {file_path}: {e}")
                    yield {
                        "parent": str(file_path.parent.relative_to(root_dir)) if root_dir in file_path.parent.resolve().parents else str(file_path.parent),
                        "filename": file_path.name,
                        "info": {
                            "type": "error",
                            "content": f"Error while processing the file: {str(e)}",
                            "exception_type": type(e).__name__,
                            "exception_message": str(e)
                        }
                    }
                finally:
                    pbar.update(1)
        except KeyboardInterrupt:
            logging.warning("\nCancellation by user during processing. Attempts to terminate running tasks...")
            executor.shutdown(wait=False, cancel_futures=True)
            pbar.close()
            raise

    pbar.close()

    summary: Dict[str, Any] = {
        "total_files": total_files,
        "excluded_files": excluded_files_count,
        "included_files": included_files,
        "excluded_percentage": excluded_percentage,
        "failed_files": failed_files
    }

    if hash_algorithm is not None:
        summary["hash_algorithm"] = hash_algorithm

    if cancellation_token and cancellation_token.is_cancellation_requested():
        summary["stopped_early"] = True

    yield {
        "summary": summary
    }
