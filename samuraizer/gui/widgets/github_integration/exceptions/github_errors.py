# samuraizer/gui/widgets/configuration/repository/github/exceptions/github_errors.py

class CloneOperationError(Exception):
    """Exception raised when a GitHub repository clone operation fails."""
    pass

class GitHubValidationError(Exception):
    """Exception raised when GitHub repository validation fails."""
    pass

class GitHubAuthenticationError(Exception):
    """Exception raised when GitHub authentication fails."""
    pass

class GitHubRateLimitError(Exception):
    """Exception raised when GitHub API rate limit is exceeded."""
    pass

class GitHubRepositoryNotFoundError(Exception):
    """Exception raised when a GitHub repository is not found."""
    pass
