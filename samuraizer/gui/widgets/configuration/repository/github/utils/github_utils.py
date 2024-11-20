# samuraizer/gui/widgets/configuration/repository/github/utils/github_utils.py

import re
import logging
from urllib.parse import urlparse
from typing import Optional, Dict
import requests
from requests.exceptions import RequestException, Timeout, HTTPError

from .github_auth import GitHubAuthManager

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"

def is_valid_github_url(url: str) -> bool:
    """Check if the URL is a valid GitHub repository URL."""
    if not url:
        logger.debug("Empty URL provided for validation.")
        return False

    try:
        # Handle SSH URLs
        ssh_pattern = r'^git@github\.com:(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(\.git)?$'
        https_pattern = r'^https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(\.git)?$'

        if re.match(ssh_pattern, url):
            logger.debug(f"URL matches SSH pattern: {url}")
            return True
        elif re.match(https_pattern, url):
            logger.debug(f"URL matches HTTPS pattern: {url}")
            return True
        else:
            logger.debug(f"URL does not match GitHub patterns: {url}")
            return False

    except Exception as e:
        logger.error(f"Error validating GitHub URL '{url}': {e}")
        return False

def fetch_repo_info(url: str, auth_manager: Optional[GitHubAuthManager] = None) -> Optional[Dict]:
    """Fetch repository information from GitHub API.

    Args:
        url (str): The GitHub repository URL.
        auth_manager (Optional[GitHubAuthManager]): Authentication manager for GitHub.

    Returns:
        Optional[Dict]: Dictionary containing repository information or None if failed.
    """
    try:
        owner, repo = _parse_github_url(url)
        if not owner or not repo:
            logger.error(f"Unable to parse owner and repo from URL: {url}")
            return None

        # Make API request
        api_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"
        headers = {}
        if auth_manager:
            token = auth_manager.get_access_token()
            if token:
                headers['Authorization'] = f'token {token}'

        logger.debug(f"Fetching repository info from API: {api_url}")
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        repo_data = response.json()
        logger.info(f"Successfully fetched repository info for {owner}/{repo}")
        return {
            'name': repo_data.get('name'),
            'description': repo_data.get('description'),
            'default_branch': repo_data.get('default_branch'),
            'size': repo_data.get('size'),
            'stars': repo_data.get('stargazers_count'),
            'forks': repo_data.get('forks_count'),
            'owner': repo_data.get('owner', {}).get('login'),
            'clone_url': repo_data.get('clone_url'),
            'ssh_url': repo_data.get('ssh_url')
        }

    except HTTPError as http_err:
        if http_err.response.status_code == 403:
            logger.error(f"Access forbidden or rate limited when fetching repo info for URL '{url}': {http_err}")
        elif http_err.response.status_code == 404:
            logger.error(f"Repository not found for URL '{url}': {http_err}")
        else:
            logger.error(f"HTTP error occurred when fetching repo info for URL '{url}': {http_err}")
    except Timeout:
        logger.error(f"Request timed out when fetching repo info for URL '{url}'")
    except RequestException as req_err:
        logger.error(f"Request exception occurred when fetching repo info for URL '{url}': {req_err}")
    except Exception as e:
        logger.exception(f"Unexpected error when fetching repo info for URL '{url}': {e}")

    return None

def get_repo_branches(url: str, auth_manager: Optional[GitHubAuthManager] = None) -> Optional[list]:
    """Fetch repository branches from GitHub API.

    Args:
        url (str): The GitHub repository URL.
        auth_manager (Optional[GitHubAuthManager]): Authentication manager for GitHub.

    Returns:
        Optional[list]: List of branch names or None if failed.
    """
    try:
        owner, repo = _parse_github_url(url)
        if not owner or not repo:
            logger.error(f"Unable to parse owner and repo from URL: {url}")
            return None

        # Make API request
        api_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/branches"
        headers = {}
        if auth_manager:
            token = auth_manager.get_access_token()
            if token:
                headers['Authorization'] = f'token {token}'

        logger.debug(f"Fetching repository branches from API: {api_url}")
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        branches_data = response.json()
        branches = [branch['name'] for branch in branches_data]
        logger.info(f"Successfully fetched branches for {owner}/{repo}: {branches}")
        return branches

    except HTTPError as http_err:
        if http_err.response.status_code == 403:
            logger.error(f"Access forbidden or rate limited when fetching branches for URL '{url}': {http_err}")
        elif http_err.response.status_code == 404:
            logger.error(f"Repository not found when fetching branches for URL '{url}': {http_err}")
        else:
            logger.error(f"HTTP error occurred when fetching branches for URL '{url}': {http_err}")
    except Timeout:
        logger.error(f"Request timed out when fetching branches for URL '{url}'")
    except RequestException as req_err:
        logger.error(f"Request exception occurred when fetching branches for URL '{url}': {req_err}")
    except Exception as e:
        logger.exception(f"Unexpected error when fetching branches for URL '{url}': {e}")

    return None

def _parse_github_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Parse GitHub URL to extract owner and repository name.

    Args:
        url (str): The GitHub repository URL.

    Returns:
        Tuple[Optional[str], Optional[str]]: Owner and repository name.
    """
    try:
        ssh_pattern = r'^git@github\.com:(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(\.git)?$'
        https_pattern = r'^https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(\.git)?$'

        ssh_match = re.match(ssh_pattern, url)
        if ssh_match:
            owner = ssh_match.group('owner')
            repo = ssh_match.group('repo').rstrip('.git')
            logger.debug(f"Parsed SSH URL. Owner: {owner}, Repo: {repo}")
            return owner, repo

        https_match = re.match(https_pattern, url)
        if https_match:
            owner = https_match.group('owner')
            repo = https_match.group('repo').rstrip('.git')
            logger.debug(f"Parsed HTTPS URL. Owner: {owner}, Repo: {repo}")
            return owner, repo

        logger.warning(f"URL does not match expected GitHub patterns: {url}")
        return None, None

    except Exception as e:
        logger.error(f"Error parsing GitHub URL '{url}': {e}")
        return None, None
