"""
GitHub MCP Server

This module provides a FastMCP server that exposes tools for interacting with GitHub.
The server uses PyGithub to fetch PR details, post comments, and interact with the GitHub API.

This is a REAL implementation that connects to the actual GitHub API.
"""

import os
import time
import logging
from typing import Optional
from github import Github
from github.GithubException import (
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
    BadCredentialsException,
)
from fastmcp import FastMCP

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("GitHub MCP Server")


# ============================================================================
# Helper Functions
# ============================================================================

def get_github_client() -> Github:
    """
    Initialize and return a GitHub client.
    
    This function creates a PyGithub client using the GITHUB_TOKEN
    from environment variables. The token is required for all API calls.
    
    This approach is CI-agnostic and works with all CI systems:
    - GitHub Actions: Use ${{ secrets.GITHUB_TOKEN }} (auto-provided)
    - Jenkins: Set as environment variable or credentials
    - GitLab CI: Set as CI/CD variable
    - CircleCI: Set as environment variable
    - Azure DevOps: Set as pipeline variable
    - Any CI: Just set GITHUB_TOKEN environment variable
    
    Returns:
        Authenticated GitHub client
        
    Raises:
        ValueError: If GITHUB_TOKEN is not set
        BadCredentialsException: If token is invalid
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    # Use new auth API to avoid deprecation warning
    try:
        from github import Auth
        auth = Auth.Token(token)
        client = Github(auth=auth)
    except ImportError:
        # Fallback for older PyGithub versions
        client = Github(token)
    
    # Note: Credential verification is done lazily on first API call
    # This avoids unnecessary API calls during initialization
    # and allows for better test mocking
    
    return client


def handle_github_exception(e: Exception, operation: str) -> Exception:
    """
    Handle GitHub API exceptions with appropriate error messages.
    
    This function provides better error messages for common GitHub API errors
    and handles rate limiting with retry information.
    
    Args:
        e: The exception raised by PyGithub
        operation: Description of the operation that failed
        
    Returns:
        Exception with improved error message
    """
    if isinstance(e, RateLimitExceededException):
        reset_time = e.headers.get("X-RateLimit-Reset", "unknown")
        return Exception(
            f"GitHub API rate limit exceeded for {operation}. "
            f"Rate limit resets at: {reset_time}. "
            f"Consider using a token with higher rate limits or implementing retry logic."
        )
    elif isinstance(e, BadCredentialsException):
        return Exception(
            f"GitHub authentication failed for {operation}. "
            f"Please check that GITHUB_TOKEN is valid and has appropriate permissions."
        )
    elif isinstance(e, UnknownObjectException):
        return Exception(
            f"GitHub resource not found for {operation}. "
            f"The PR, repository, or resource may not exist or you may not have access."
        )
    elif isinstance(e, GithubException):
        return Exception(
            f"GitHub API error during {operation}: {e.status} - {e.data.get('message', str(e))}"
        )
    else:
        return Exception(f"Unexpected error during {operation}: {str(e)}")


def retry_on_rate_limit(func, max_retries: int = 3, base_delay: int = 60):
    """
    Retry a function call if it raises a RateLimitExceededException.
    
    This decorator/helper handles GitHub API rate limiting by waiting
    for the rate limit to reset before retrying.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will use rate limit reset time if available)
        
    Returns:
        Function result
        
    Raises:
        RateLimitExceededException: If rate limit persists after retries
    """
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitExceededException as e:
            if attempt == max_retries - 1:
                raise
            
            # Try to get reset time from exception headers
            reset_time = e.headers.get("X-RateLimit-Reset", None)
            if reset_time:
                wait_time = max(int(reset_time) - int(time.time()), base_delay)
            else:
                wait_time = base_delay * (attempt + 1)
            
            print(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait_time)
    
    raise RateLimitExceededException(403, {"message": "Rate limit exceeded"}, {})


def parse_pr_url(pr_url: str) -> tuple[str, int]:
    """
    Parse a GitHub PR URL to extract repository and PR number.
    
    This function extracts the repository owner, name, and PR number
    from a GitHub PR URL (e.g., https://github.com/owner/repo/pull/123).
    
    Args:
        pr_url: Full URL of the pull request
        
    Returns:
        Tuple of (repository path, PR number)
        
    Raises:
        ValueError: If URL format is invalid
    """
    import re
    
    # Remove trailing slash if present
    pr_url = pr_url.rstrip('/')
    
    # Pattern: https://github.com/owner/repo/pull/123
    pattern = r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
    match = re.match(pattern, pr_url)
    
    if not match:
        raise ValueError(f"Invalid PR URL format: {pr_url}. Expected format: https://github.com/owner/repo/pull/123")
    
    owner, repo, pr_number = match.groups()
    repo_path = f"{owner}/{repo}"
    
    return repo_path, int(pr_number)


# ============================================================================
# MCP Tools (Exposed to Agent)
# ============================================================================

def _get_pr_details_impl(pr_url: str) -> dict:
    """
    Get comprehensive details about a pull request.
    
    This tool fetches all relevant PR information including:
    - PR diff (unified diff format)
    - PR description and title
    - Author information
    - Files changed with line-by-line changes
    - Commit history
    - Labels and reviewers
    - Status (open, closed, merged)
    - Base and head branches
    
    This is the primary tool the agent uses to understand what code
    needs to be reviewed.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        pr_url: Full URL of the pull request (e.g., https://github.com/owner/repo/pull/123)
        
    Returns:
        Dictionary containing all PR details:
        {
            "url": str,
            "number": int,
            "title": str,
            "description": str,
            "author": {"login": str, "name": str, "email": str},
            "state": str,
            "base_branch": str,
            "head_branch": str,
            "diff": str,
            "files": [{"path": str, "additions": int, "deletions": int, "patch": str}],
            "commits": [{"sha": str, "message": str, "author": str}],
            "labels": [str],
            "reviewers": [{"login": str, "state": str}],
            "created_at": str,
            "updated_at": str
        }
        
    Raises:
        Exception: If PR cannot be fetched or token is invalid
    """
    repo_path, pr_number = parse_pr_url(pr_url)
    client = get_github_client()
    repo = client.get_repo(repo_path)
    pr = repo.get_pull(pr_number)
    
    # Get file changes (needed for both files list and diff construction)
    files = []
    for file in pr.get_files():
        files.append({
            "path": file.filename,
            "additions": file.additions,
            "deletions": file.deletions,
            "patch": file.patch or ""
        })
    
    # Get author information
    author = pr.user
    author_info = {
        "login": author.login,
        "name": author.name or author.login,
        "email": author.email or ""
    }
    
    # Get commit history
    commits = []
    for commit in pr.get_commits():
        commits.append({
            "sha": commit.sha,
            "message": commit.commit.message.split('\n')[0],  # First line only
            "author": commit.commit.author.name if commit.commit.author else ""
        })
    
    # Get labels
    labels = [label.name for label in pr.get_labels()]
    
    # Get reviewers (requested reviewers)
    reviewers = []
    try:
        review_requests = pr.get_review_requests()
        # get_review_requests returns a tuple: (users, teams)
        if review_requests and len(review_requests) > 0:
            requested_users = review_requests[0]  # First element is users
            for reviewer in requested_users:
                reviewers.append({
                    "login": reviewer.login,
                    "state": "requested"
                })
    except Exception:
        # If review requests can't be fetched, continue without reviewers
        pass
    
    # Construct unified diff from file patches
    # PyGithub doesn't provide pr.diff directly, so we build it from file patches
    diff_parts = []
    for file_info in files:
        if file_info["patch"]:
            # Add file header for unified diff format
            diff_parts.append(f"diff --git a/{file_info['path']} b/{file_info['path']}")
            diff_parts.append(f"--- a/{file_info['path']}")
            diff_parts.append(f"+++ b/{file_info['path']}")
            diff_parts.append(file_info["patch"])
    
    diff = "\n".join(diff_parts) if diff_parts else ""
    
    return {
        "url": pr.html_url,
        "number": pr.number,
        "title": pr.title,
        "description": pr.body or "",
        "author": author_info,
        "state": pr.state,
        "base_branch": pr.base.ref,
        "head_branch": pr.head.ref,
        "diff": diff,
        "files": files,
        "commits": commits,
        "labels": labels,
        "reviewers": reviewers,
        "created_at": pr.created_at.isoformat() if pr.created_at else "",
        "updated_at": pr.updated_at.isoformat() if pr.updated_at else ""
    }


@mcp.tool()
def get_pr_details(pr_url: str) -> dict:
    """MCP tool wrapper for get_pr_details."""
    return _get_pr_details_impl(pr_url)


def _post_review_comment_impl(pr_url: str, comment: str, path: Optional[str] = None, 
                       line: Optional[int] = None) -> dict:
    """
    Post a review comment to a pull request.
    
    This tool posts a comment to a PR. It can post:
    - General PR comments (no path/line)
    - File-level comments (path only)
    - Line-specific comments (path + line)
    
    The agent uses this tool to post its review feedback after analysis.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        pr_url: Full URL of the pull request
        comment: Comment text to post
        path: Optional file path for file/line-specific comments
        line: Optional line number for line-specific comments
        
    Returns:
        Dictionary with comment details:
        {
            "id": int,
            "url": str,
            "created_at": str,
            "body": str
        }
        
    Raises:
        Exception: If comment cannot be posted
    """
    repo_path, pr_number = parse_pr_url(pr_url)
    client = get_github_client()
    
    try:
        repo = client.get_repo(repo_path)
        pr = repo.get_pull(pr_number)
    except Exception as e:
        raise handle_github_exception(e, f"posting comment to PR {pr_number}")
    
    if path and line:
        # Line-specific comment
        # Find the commit SHA for the head of the PR
        commit_sha = pr.head.sha
        
        # Create a review comment on a specific line
        # PyGithub API: create_review_comment(body, commit, path, line)
        review_comment = pr.create_review_comment(
            comment,
            commit_sha,
            path,
            line
        )
    elif path:
        # File-level comment - post as general comment with file reference
        comment_with_file = f"**File: {path}**\n\n{comment}"
        review_comment = pr.create_issue_comment(comment_with_file)
    else:
        # General PR comment
        review_comment = pr.create_issue_comment(comment)
    
    return {
        "id": review_comment.id,
        "url": review_comment.html_url,
        "created_at": review_comment.created_at.isoformat() if review_comment.created_at else "",
        "body": review_comment.body
    }


@mcp.tool()
def post_review_comment(pr_url: str, comment: str, path: Optional[str] = None, 
                       line: Optional[int] = None) -> dict:
    """MCP tool wrapper for post_review_comment."""
    return _post_review_comment_impl(pr_url, comment, path, line)


def _delete_previous_comments_impl(pr_url: str, marker: str = "<!-- AUTO_REVIEW -->") -> dict:
    """
    Delete prior bot comments for a PR that contain a marker.
    
    This is useful when re-running automated reviews so stale comments are
    removed before posting new ones. Only comments authored by the current
    authenticated user are deleted to avoid touching human feedback.
    """
    repo_path, pr_number = parse_pr_url(pr_url)
    client = get_github_client()
    
    try:
        current_user_login = client.get_user().login
    except Exception:
        current_user_login = None
    
    repo = client.get_repo(repo_path)
    pr = repo.get_pull(pr_number)
    
    deleted_issue = 0
    deleted_review = 0
    
    def should_delete(comment_body: str, author_login: Optional[str]) -> bool:
        if marker not in (comment_body or ""):
            return False
        if current_user_login and author_login:
            return author_login == current_user_login
        # If we can't determine the current user, be conservative and do not delete
        return False
    
    for comment in pr.get_issue_comments():
        try:
            if should_delete(comment.body, getattr(comment.user, "login", None)):
                comment.delete()
                deleted_issue += 1
        except Exception as e:
            logger.warning(f"Failed to delete issue comment {getattr(comment, 'id', 'unknown')}: {e}")
    
    for comment in pr.get_review_comments():
        try:
            if should_delete(comment.body, getattr(comment.user, "login", None)):
                comment.delete()
                deleted_review += 1
        except Exception as e:
            logger.warning(f"Failed to delete review comment {getattr(comment, 'id', 'unknown')}: {e}")
    
    return {
        "deleted_issue_comments": deleted_issue,
        "deleted_review_comments": deleted_review
    }


@mcp.tool()
def delete_previous_comments(pr_url: str, marker: str = "<!-- AUTO_REVIEW -->") -> dict:
    """MCP tool wrapper for deleting previous bot comments with a marker."""
    return _delete_previous_comments_impl(pr_url, marker)


def _submit_review_impl(pr_url: str, event: str, body: str = "", comments: Optional[list[dict]] = None) -> dict:
    """
    Submit a review for a pull request with approval, request changes, or comment.
    
    This tool submits a formal review to a PR. Unlike individual comments,
    a review can approve the PR, request changes (block it), or just comment.
    
    Note: GitHub Actions cannot approve PRs. If event is "APPROVE", it will
    be automatically converted to "COMMENT" to avoid errors.
    
    The agent can use this to:
    - Approve PRs that meet all requirements (converted to COMMENT in GitHub Actions)
    - Request changes for PRs with issues
    - Submit a review with multiple comments at once
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        pr_url: Full URL of the pull request
        event: Review event type - "APPROVE", "REQUEST_CHANGES", or "COMMENT"
        body: Optional review summary/body text
        comments: Optional list of review comments (line-specific comments)
                  Each dict should have: "path", "line", "body"
        
    Returns:
        Dictionary with review details:
        {
            "id": int,
            "state": str,
            "body": str,
            "submitted_at": str,
            "url": str
        }
        
    Raises:
        ValueError: If event is not one of: APPROVE, REQUEST_CHANGES, COMMENT
        Exception: If review cannot be submitted
    """
    if event not in ["APPROVE", "REQUEST_CHANGES", "COMMENT"]:
        raise ValueError(f"Invalid event: {event}. Must be APPROVE, REQUEST_CHANGES, or COMMENT")
    
    # GitHub Actions cannot approve PRs - convert APPROVE to COMMENT
    # Check if we're running in GitHub Actions by checking for GITHUB_ACTIONS env var
    if event == "APPROVE" and os.getenv("GITHUB_ACTIONS"):
        logger.warning("GitHub Actions cannot approve PRs. Converting APPROVE to COMMENT.")
        event = "COMMENT"
        if body:
            body = f"✅ Code looks good! (Note: GitHub Actions cannot approve PRs)\n\n{body}"
        else:
            body = "✅ Code looks good! (Note: GitHub Actions cannot approve PRs)"
    
    repo_path, pr_number = parse_pr_url(pr_url)
    client = get_github_client()
    
    try:
        repo = client.get_repo(repo_path)
        pr = repo.get_pull(pr_number)
    except Exception as e:
        raise handle_github_exception(e, f"submitting review for PR {pr_number}")
    
    # Convert comments format if provided
    review_comments = None
    if comments:
        review_comments = []
        commit_sha = pr.head.sha
        for comment in comments:
            if "path" in comment and "line" in comment:
                review_comments.append({
                    "path": comment["path"],
                    "line": comment.get("line"),
                    "body": comment.get("body", "")
                })
    
    # Submit the review
    review = pr.create_review(
        body=body,
        event=event,
        comments=review_comments or []
    )
    
    return {
        "id": review.id,
        "state": review.state,
        "body": review.body or "",
        "submitted_at": review.submitted_at.isoformat() if review.submitted_at else "",
        "url": review.html_url
    }


@mcp.tool()
def submit_review(pr_url: str, event: str, body: str = "", comments: Optional[list[dict]] = None) -> dict:
    """MCP tool wrapper for submit_review."""
    return _submit_review_impl(pr_url, event, body, comments)


def _post_review_comments_impl(pr_url: str, comments: list[dict]) -> dict:
    """
    Post multiple review comments to a pull request.
    
    This tool posts a batch of comments to a PR. It's more efficient
    than posting comments one by one and allows the agent to post
    all review feedback in a single operation.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        pr_url: Full URL of the pull request
        comments: List of comment dictionaries, each with:
            - "body": str (required)
            - "path": str (optional)
            - "line": int (optional)
            - "side": str (optional, "LEFT" or "RIGHT")
            
    Returns:
        Dictionary with posting results:
        {
            "posted": int,
            "failed": int,
            "comments": [{"id": int, "url": str}]
        }
        
    Raises:
        Exception: If comments cannot be posted
    """
    repo_path, pr_number = parse_pr_url(pr_url)
    client = get_github_client()
    
    try:
        repo = client.get_repo(repo_path)
        pr = repo.get_pull(pr_number)
    except Exception as e:
        raise handle_github_exception(e, f"posting comments to PR {pr_number}")
    
    posted = 0
    failed = 0
    posted_comments = []
    
    for comment_data in comments:
        try:
            body = comment_data.get("body", "")
            path = comment_data.get("path")
            line = comment_data.get("line")
            
            if path and line:
                # Line-specific comment
                commit_sha = pr.head.sha
                # PyGithub API: create_review_comment(body, commit, path, line)
                review_comment = pr.create_review_comment(
                    body,
                    commit_sha,
                    path,
                    line
                )
            elif path:
                # File-level comment
                comment_with_file = f"**File: {path}**\n\n{body}"
                review_comment = pr.create_issue_comment(comment_with_file)
            else:
                # General comment
                review_comment = pr.create_issue_comment(body)
            
            posted_comments.append({
                "id": review_comment.id,
                "url": review_comment.html_url
            })
            posted += 1
        except Exception as e:
            failed += 1
            # Log error but continue with other comments
            print(f"Failed to post comment: {e}")
    
    return {
        "posted": posted,
        "failed": failed,
        "comments": posted_comments
    }


@mcp.tool()
def post_review_comments(pr_url: str, comments: list[dict]) -> dict:
    """MCP tool wrapper for post_review_comments."""
    return _post_review_comments_impl(pr_url, comments)


# ============================================================================
# Server Initialization
# ============================================================================

def create_github_mcp_server() -> FastMCP:
    """
    Create and return a configured GitHub MCP server instance.
    
    This function initializes the MCP server with all tools registered.
    The server can then be used by the agent to interact with GitHub.
    
    Returns:
        Configured FastMCP server instance
    """
    # Validate GITHUB_TOKEN exists
    if not os.getenv("GITHUB_TOKEN"):
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    return mcp


# Export implementation functions for testing
# The @mcp.tool() decorator wraps functions, so tests use the _impl versions
__all__ = [
    "get_github_client",
    "parse_pr_url",
    "handle_github_exception",
    "retry_on_rate_limit",
    "get_pr_details",  # MCP tool (wrapped)
    "_get_pr_details_impl",  # Implementation (for testing)
    "post_review_comment",  # MCP tool (wrapped)
    "_post_review_comment_impl",  # Implementation (for testing)
    "submit_review",  # MCP tool (wrapped)
    "_submit_review_impl",  # Implementation (for testing)
    "post_review_comments",  # MCP tool (wrapped)
    "_post_review_comments_impl",  # Implementation (for testing)
    "delete_previous_comments",  # MCP tool (wrapped)
    "_delete_previous_comments_impl",  # Implementation (for testing)
    "create_github_mcp_server",
    "mcp",
]


if __name__ == "__main__":
    # For testing: run the server directly
    # TODO: Initialize and run MCP server
    pass

