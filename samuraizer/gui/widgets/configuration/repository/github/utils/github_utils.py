# samuraizer/gui/widgets/configuration/repository/github/utils/github_utils.py

import re
import logging
from urllib.parse import urlparse
from typing import Optional, Dict

import requests

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"

def is_valid_github_url(url: str) -> bool:
    """Check if the URL is a valid GitHub repository URL."""
    if not url:
        return False

    try:
        # Handle SSH URLs
        if url.startswith('git@github.com:'):
            path = url.split('git@github.com:')[1]
            path_parts = path.strip('/').split('/')
        else:
            # Handle HTTPS URLs
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            if parsed.netloc.lower() != "github.com":
                return False
            path_parts = parsed.path.strip('/').split('/')

        # Check path structure (username/repository)
        if len(path_parts) < 2:
            return False

        # Validate username and repository name format
        username, repo = path_parts[:2]
        if not re.match(r'^[\w-]+$', username):
            return False
        if not re.match(r'^[\w-]+(?:\.git)?$', repo):
            return False

        return True

    except Exception as e:
        logger.error(f"Error validating GitHub URL: {e}")
        return False

def fetch_repo_info(url: str) -> Optional[Dict]:
    """Fetch repository information from GitHub API."""
    try:
        # Handle SSH URLs
        if url.startswith('git@github.com:'):
            path = url.split('git@github.com:')[1]
            path_parts = path.strip('/').split('/')
        else:
            # Handle HTTPS URLs
            path_parts = urlparse(url).path.strip('/').split('/')

        if len(path_parts) >= 2:
            owner, repo = path_parts[:2]
            # Remove .git extension if present
            repo = repo.replace('.git', '')

            # Make API request
            api_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"
            response = requests.get(api_url)
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    'name': repo_data['name'],
                    'description': repo_data.get('description'),
                    'default_branch': repo_data['default_branch'],
                    'size': repo_data['size'],
                    'stars': repo_data['stargazers_count'],
                    'forks': repo_data['forks_count'],
                    'owner': repo_data['owner']['login'],
                    'clone_url': repo_data['clone_url'],
                    'ssh_url': repo_data['ssh_url']
                }
            else:
                logger.error(f"GitHub API responded with status code {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching repo info: {e}")
        return None

def get_repo_branches(url: str) -> Optional[list]:
    """Fetch repository branches from GitHub API."""
    try:
        # Handle SSH URLs
        if url.startswith('git@github.com:'):
            path = url.split('git@github.com:')[1]
            path_parts = path.strip('/').split('/')
        else:
            # Handle HTTPS URLs
            path_parts = urlparse(url).path.strip('/').split('/')

        if len(path_parts) >= 2:
            owner, repo = path_parts[:2]
            # Remove .git extension if present
            repo = repo.replace('.git', '')

            # Make API request
            api_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/branches"
            response = requests.get(api_url)
            if response.status_code == 200:
                branches = response.json()
                return [branch['name'] for branch in branches]
            else:
                logger.error(f"GitHub API responded with status code {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching repo branches: {e}")
        return None
