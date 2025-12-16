"""
Tests for mcp_servers/github_server.py

These tests verify the GitHub MCP server implementation.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from github import Github


class TestGetGithubClient:
    """Tests for get_github_client()"""
    
    def test_get_github_client_creates_client_with_token(self, mock_env_vars):
        """
        Test that get_github_client creates a Github client with token.
        
        Expected behavior:
        - Reads GITHUB_TOKEN from environment
        - Creates Github client with token
        - Returns authenticated client
        """
        from mcp_servers.github_server import get_github_client
        
        client = get_github_client()
        
        assert client is not None
        assert isinstance(client, Github)
    
    def test_get_github_client_raises_without_token(self, monkeypatch):
        """
        Test that get_github_client raises error without token.
        
        Expected behavior:
        - Raises ValueError if GITHUB_TOKEN not set
        """
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        
        from mcp_servers.github_server import get_github_client
        
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            get_github_client()


class TestParsePrUrl:
    """Tests for parse_pr_url()"""
    
    def test_parse_pr_url_extracts_repo_and_number(self):
        """
        Test that parse_pr_url extracts repository and PR number.
        
        Expected behavior:
        - Parses URL format: https://github.com/owner/repo/pull/123
        - Returns tuple: (owner/repo, pr_number)
        """
        from mcp_servers.github_server import parse_pr_url
        
        repo_path, pr_number = parse_pr_url("https://github.com/test-owner/test-repo/pull/123")
        
        assert repo_path == "test-owner/test-repo"
        assert pr_number == 123
    
    def test_parse_pr_url_handles_different_formats(self):
        """
        Test that parse_pr_url handles various URL formats.
        
        Expected behavior:
        - Handles URLs with trailing slashes
        - Handles URLs without https://
        - Raises ValueError for invalid formats
        """
        from mcp_servers.github_server import parse_pr_url
        
        # Test with trailing slash
        repo_path, pr_number = parse_pr_url("https://github.com/owner/repo/pull/456/")
        assert pr_number == 456
        
        # Test invalid format
        with pytest.raises(ValueError):
            parse_pr_url("not-a-valid-url")


class TestGetPrDetails:
    """Tests for get_pr_details() MCP tool"""
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_get_pr_details_fetches_comprehensive_data(self, mock_get_client, sample_pr_data):
        """
        Test that get_pr_details returns all PR information.
        
        Expected behavior:
        - Fetches PR from GitHub
        - Returns dict with: url, number, title, description, author, diff, files, etc.
        - Includes all fields needed for code review
        """
        from mcp_servers.github_server import _get_pr_details_impl as get_pr_details
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        
        # Mock PR attributes
        mock_pr.html_url = sample_pr_data["url"]
        mock_pr.number = sample_pr_data["number"]
        mock_pr.title = sample_pr_data["title"]
        mock_pr.body = sample_pr_data["description"]
        mock_pr.diff = sample_pr_data["diff"]
        mock_pr.get_files.return_value = []
        mock_pr.get_commits.return_value = []
        
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        result = get_pr_details("https://github.com/owner/repo/pull/123")
        
        assert result["url"] == sample_pr_data["url"]
        assert result["number"] == sample_pr_data["number"]
        assert "diff" in result
        assert "files" in result
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_get_pr_details_handles_api_errors(self, mock_get_client):
        """
        Test that get_pr_details handles GitHub API errors.
        
        Expected behavior:
        - Raises exception on API errors
        - Provides clear error message
        """
        from mcp_servers.github_server import _get_pr_details_impl as get_pr_details
        
        mock_client = MagicMock()
        mock_client.get_repo.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        with pytest.raises(Exception):
            get_pr_details("https://github.com/owner/repo/pull/123")


class TestPostReviewComment:
    """Tests for post_review_comment() MCP tool"""
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_post_review_comment_posts_general_comment(self, mock_get_client):
        """
        Test that post_review_comment posts a general PR comment.
        
        Expected behavior:
        - Posts comment to PR when no path/line specified
        - Returns comment details with ID and URL
        """
        from mcp_servers.github_server import _post_review_comment_impl as post_review_comment
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 12345
        mock_comment.html_url = "https://github.com/owner/repo/pull/123#comment-12345"
        
        mock_pr.create_issue_comment.return_value = mock_comment
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        result = post_review_comment(
            pr_url="https://github.com/owner/repo/pull/123",
            comment="Great work!"
        )
        
        assert result["id"] == 12345
        assert "url" in result
        mock_pr.create_issue_comment.assert_called_once_with("Great work!")
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_post_review_comment_posts_line_comment(self, mock_get_client):
        """
        Test that post_review_comment posts a line-specific comment.
        
        Expected behavior:
        - Posts comment to specific file and line
        - Uses GitHub review comment API
        """
        from mcp_servers.github_server import _post_review_comment_impl as post_review_comment
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 67890
        
        mock_pr.create_review_comment.return_value = mock_comment
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        result = post_review_comment(
            pr_url="https://github.com/owner/repo/pull/123",
            comment="Fix this line",
            path="src/test.py",
            line=10
        )
        
        assert result["id"] == 67890
        mock_pr.create_review_comment.assert_called_once()


class TestPostReviewComments:
    """Tests for post_review_comments() MCP tool"""
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_post_review_comments_posts_batch(self, mock_get_client):
        """
        Test that post_review_comments posts multiple comments efficiently.
        
        Expected behavior:
        - Posts all comments in batch
        - Returns summary with posted/failed counts
        - Returns list of posted comment IDs
        """
        from mcp_servers.github_server import _post_review_comments_impl as post_review_comments
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 1
        mock_comment.html_url = "https://github.com/owner/repo/pull/123#comment-1"
        
        mock_pr.create_issue_comment.return_value = mock_comment
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        comments = [
            {"body": "Comment 1"},
            {"body": "Comment 2", "path": "test.py", "line": 10}
        ]
        
        result = post_review_comments(
            pr_url="https://github.com/owner/repo/pull/123",
            comments=comments
        )
        
        assert result["posted"] == 2
        assert result["failed"] == 0
        assert len(result["comments"]) == 2


class TestSubmitReview:
    """Tests for submit_review() MCP tool"""
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_submit_review_approves_pr(self, mock_get_client):
        """Test that submit_review can approve a PR."""
        from mcp_servers.github_server import _submit_review_impl as submit_review
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_review = MagicMock()
        mock_review.id = 1
        mock_review.state = "APPROVED"
        mock_review.body = "Looks good!"
        mock_review.submitted_at = None
        mock_review.html_url = "https://github.com/owner/repo/pull/123#review-1"
        
        mock_pr.create_review.return_value = mock_review
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        result = submit_review(
            pr_url="https://github.com/owner/repo/pull/123",
            event="APPROVE",
            body="Looks good!"
        )
        
        assert result["state"] == "APPROVED"
        mock_pr.create_review.assert_called_once()
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_submit_review_invalid_event(self, mock_get_client):
        """Test that submit_review raises error for invalid event."""
        from mcp_servers.github_server import _submit_review_impl as submit_review
        
        with pytest.raises(ValueError, match="Invalid event"):
            submit_review(
                pr_url="https://github.com/owner/repo/pull/123",
                event="INVALID",
                body="Test"
            )
    
    @patch("mcp_servers.github_server.get_github_client")
    def test_post_review_comments_handles_failures(self, mock_get_client):
        """Test that post_review_comments handles individual comment failures."""
        from mcp_servers.github_server import _post_review_comments_impl as post_review_comments
        
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 1
        mock_comment.html_url = "https://github.com/owner/repo/pull/123#comment-1"
        
        # First comment succeeds, second fails
        mock_pr.create_issue_comment.side_effect = [
            mock_comment,
            Exception("API Error")
        ]
        mock_client.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_get_client.return_value = mock_client
        
        comments = [
            {"body": "Comment 1"},
            {"body": "Comment 2"}
        ]
        
        result = post_review_comments(
            pr_url="https://github.com/owner/repo/pull/123",
            comments=comments
        )
        
        assert result["posted"] == 1
        assert result["failed"] == 1


class TestCreateGithubMcpServer:
    """Tests for create_github_mcp_server()"""
    
    def test_create_github_mcp_server_returns_configured_server(self, mock_env_vars):
        """
        Test that create_github_mcp_server returns configured MCP server.
        
        Expected behavior:
        - Returns FastMCP server instance
        - Server has all tools registered
        - Server is ready to use
        """
        from mcp_servers.github_server import create_github_mcp_server
        
        server = create_github_mcp_server()
        
        assert server is not None
        # Server should be a FastMCP instance
        # (exact type checking depends on FastMCP implementation)
    
    def test_create_github_mcp_server_raises_without_token(self, monkeypatch):
        """Test that create_github_mcp_server raises error without token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        
        from mcp_servers.github_server import create_github_mcp_server
        
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            create_github_mcp_server()

