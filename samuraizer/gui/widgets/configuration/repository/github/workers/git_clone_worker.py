# samuraizer/gui/widgets/configuration/repository/github/workers/git_clone_worker.py

import os
import logging
import json
import time
from typing import Optional
from pathlib import Path
from git import Repo
from git.exc import GitCommandError, GitError
from PyQt6.QtCore import QThread, pyqtSignal

from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.backend.cache.cache_operations import get_cached_entry, set_cached_entry
from samuraizer.backend.cache.connection_pool import get_connection_context
from ..exceptions.github_errors import (
    CloneOperationError,
    GitHubAuthenticationError,
    GitHubRepositoryNotFoundError
)

logger = logging.getLogger(__name__)

class GitCloneWorker(QThread):
    """Worker thread for cloning GitHub repositories."""
    
    progress = pyqtSignal(str)               # Signal for progress updates as messages
    progress_percentage = pyqtSignal(int)    # Signal for progress updates as percentage
    error = pyqtSignal(str)                  # Signal for error messages
    finished = pyqtSignal(str)               # Signal emitted with path to cloned repo
    
    def __init__(self, url: str, target_path: str, branch: Optional[str] = None, shallow_clone: bool = False, initialize_submodules: bool = False, max_retries: int = 3, retry_delay: int = 2):
        super().__init__()
        self.url = url
        self.target_path = Path(target_path)
        self.branch = branch
        self.shallow_clone = shallow_clone
        self.initialize_submodules = initialize_submodules
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # in seconds
        self._stop_requested = False
        
    def run(self):
        """Execute the clone operation with retry mechanism."""
        attempt = 0
        while attempt < self.max_retries and not self._stop_requested:
            try:
                attempt += 1
                self.progress.emit(f"Attempt {attempt} to clone repository: {self.url}")
                
                # Check cache first
                repo_path = self._check_cache()
                if repo_path:
                    self.progress.emit("Using cached repository.")
                    self.progress_percentage.emit(100)
                    self.finished.emit(str(repo_path))
                    return
                
                # Ensure target directory exists
                self.target_path.mkdir(parents=True, exist_ok=True)
                
                # Configure git clone options
                clone_kwargs = {
                    'url': self.url,
                    'to_path': str(self.target_path),
                    'progress': self._progress_callback,
                }
                
                if self.branch:
                    clone_kwargs['branch'] = self.branch
                
                if self.shallow_clone:
                    clone_kwargs['depth'] = 1  # Shallow clone
        
                if self.initialize_submodules:
                    clone_kwargs['recursive'] = True  # Initialize submodules
                
                # Perform the clone operation
                self.progress.emit(f"Starting clone operation (Attempt {attempt})...")
                repo = Repo.clone_from(**clone_kwargs)
                
                # Verify the clone was successful
                if not repo or not repo.git_dir:
                    raise CloneOperationError("Failed to clone repository - repository object not created.")
                
                # Cache the cloned repository
                self._cache_repository(repo)
                    
                self.progress.emit("Clone operation completed successfully.")
                self.progress_percentage.emit(100)
                self.finished.emit(str(self.target_path))
                return
                    
            except GitCommandError as e:
                error_msg = str(e)
                logger.error(f"GitCommandError during clone attempt {attempt}: {error_msg}")
                
                if "Authentication failed" in error_msg:
                    self.error.emit("Authentication failed. Please check your credentials.")
                    break  # Do not retry on authentication errors
                elif "Repository not found" in error_msg or "not found" in error_msg:
                    self.error.emit("Repository not found. Please check the URL.")
                    break  # Do not retry on repository not found
                else:
                    self.error.emit(f"Git error on attempt {attempt}: {error_msg}")
                    
            except GitError as e:
                error_msg = str(e)
                logger.error(f"GitError during clone attempt {attempt}: {error_msg}")
                self.error.emit(f"Git error on attempt {attempt}: {error_msg}")
                
            except Exception as e:
                logger.error(f"Clone operation failed on attempt {attempt}: {str(e)}", exc_info=True)
                self.error.emit(f"Clone operation failed on attempt {attempt}: {str(e)}")
            
            if attempt < self.max_retries and not self._stop_requested:
                self.progress.emit(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                
        if attempt == self.max_retries and not self._stop_requested:
            self.error.emit("Exceeded maximum retry attempts. Clone operation failed.")
    
    def _check_cache(self) -> Optional[Path]:
        """Check if repository is already cached."""
        try:
            with get_connection_context() as conn:
                if conn is None:
                    return None
                    
                cache_entry = get_cached_entry(conn, self.url)
                if cache_entry:
                    cached_path = Path(cache_entry['file_info'].get('repo_path'))
                    if cached_path.exists():
                        return cached_path
                return None
        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return None
            
    def _cache_repository(self, repo: Repo):
        """Cache the cloned repository."""
        try:
            # Get repository info
            repo_info = {
                'repo_path': str(self.target_path),
                'branch': self.branch or repo.active_branch.name,
                'last_commit': str(repo.head.commit),
                'remote_url': self.url
            }
            
            # Calculate repository size more efficiently using os.scandir
            total_size = 0
            try:
                for root, dirs, files in os.walk(self.target_path):
                    for f in files:
                        file_path = os.path.join(root, f)
                        if '.git' not in file_path:
                            try:
                                total_size += os.path.getsize(file_path)
                            except OSError:
                                pass
            except Exception as e:
                logger.error(f"Error calculating repository size: {e}")
            
            # Get last modification time
            mtime = 0
            try:
                for root, dirs, files in os.walk(self.target_path):
                    for f in files:
                        file_path = os.path.join(root, f)
                        if '.git' not in file_path:
                            try:
                                file_mtime = os.path.getmtime(file_path)
                                if file_mtime > mtime:
                                    mtime = file_mtime
                            except OSError:
                                pass
            except Exception as e:
                logger.error(f"Error retrieving repository modification time: {e}")
            
            with get_connection_context() as conn:
                if conn is not None:
                    set_cached_entry(
                        conn=conn,
                        file_path=self.url,
                        file_hash=None,  # No need for file hash
                        file_info=repo_info,
                        size=total_size,
                        mtime=mtime
                    )
                    
        except Exception as e:
            logger.error(f"Error caching repository: {e}")
            
    def _progress_callback(self, op_code, cur_count, max_count=None, message=''):
        """Handle progress information from git clone operation."""
        if self._stop_requested:
            raise CloneOperationError("Operation cancelled by user")
            
        if message:
            self.progress.emit(message)
        elif max_count:
            try:
                progress = (cur_count / max_count) * 100
                self.progress.emit(f"Cloning: {progress:.1f}%")
                self.progress_percentage.emit(int(progress))
            except ZeroDivisionError:
                self.progress.emit("Cloning: Progress information unavailable.")
                self.progress_percentage.emit(0)
                    
    def stop(self):
        """Request the worker to stop."""
        self._stop_requested = True
