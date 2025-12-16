"""
Pytest configuration and shared fixtures

This file contains pytest fixtures that are shared across all test files.
"""

import os
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any


# ============================================================================
# Environment Variable Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Mock environment variables for testing.
    
    Sets up common environment variables needed for tests.
    Can be overridden in individual tests.
    """
    env_vars = {
        "GITHUB_TOKEN": "test_github_token",
        "OPENAI_API_KEY": "test_openai_key",
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "gpt-3.5-turbo",
        "LLM_TEMPERATURE": "0.7",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def mock_jira_env_vars(monkeypatch):
    """Mock Jira environment variables for real API mode."""
    monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test_jira_token")


@pytest.fixture
def mock_confluence_env_vars(monkeypatch):
    """Mock Confluence environment variables for real API mode."""
    monkeypatch.setenv("CONFLUENCE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "test@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "test_confluence_token")


@pytest.fixture
def mock_stub_data_paths(monkeypatch, tmp_path):
    """Mock stub data file paths pointing to temporary test files."""
    jira_stub = tmp_path / "jira-stubs.json"
    confluence_stub = tmp_path / "confluence-stubs.json"
    
    monkeypatch.setenv("JIRA_STUB_DATA_PATH", str(jira_stub))
    monkeypatch.setenv("CONFLUENCE_STUB_DATA_PATH", str(confluence_stub))
    
    return {
        "jira": jira_stub,
        "confluence": confluence_stub
    }


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_pr_url():
    """Sample PR URL for testing."""
    return "https://github.com/test-owner/test-repo/pull/123"


@pytest.fixture
def sample_pr_data():
    """Sample PR data structure matching GitHub API response."""
    return {
        "url": "https://github.com/test-owner/test-repo/pull/123",
        "number": 123,
        "title": "Test PR Title",
        "description": "This PR fixes PROJ-123",
        "author": {
            "login": "test-author",
            "name": "Test Author",
            "email": "author@example.com"
        },
        "state": "open",
        "base_branch": "main",
        "head_branch": "feature-branch",
        "diff": "@@ -1,3 +1,5 @@\n line1\n+new line\n+another line\n",
        "files": [
            {
                "path": "src/test.py",
                "additions": 10,
                "deletions": 2,
                "patch": "@@ -1,3 +1,5 @@\n line1\n+new line\n"
            }
        ],
        "commits": [
            {
                "sha": "abc123",
                "message": "Add new feature",
                "author": "Test Author"
            }
        ],
        "labels": ["bug", "PROJ-123"],
        "reviewers": [],
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T14:30:00Z"
    }


@pytest.fixture
def sample_jira_ticket_data():
    """Sample Jira ticket data matching stub format."""
    return {
        "id": "12345",
        "key": "PROJ-123",
        "summary": "Implement user authentication",
        "description": "Add OAuth2 authentication flow",
        "status": "In Progress",
        "assignee": {
            "displayName": "John Doe",
            "emailAddress": "john@example.com"
        },
        "acceptanceCriteria": [
            "User can log in with OAuth2",
            "Session is maintained for 24 hours",
            "Logout functionality works correctly"
        ],
        "labels": ["authentication", "security"],
        "issueType": "Story",
        "priority": "High",
        "created": "2024-01-15T10:00:00.000Z",
        "updated": "2024-01-20T14:30:00.000Z"
    }


@pytest.fixture
def sample_confluence_page_data():
    """Sample Confluence page data matching stub format."""
    return {
        "id": "123456",
        "title": "Authentication Architecture",
        "space": {
            "key": "ENG",
            "name": "Engineering"
        },
        "body": {
            "storage": {
                "value": "<p>Our authentication system uses OAuth2...</p>"
            }
        },
        "version": {
            "number": 3
        },
        "created": "2024-01-10T09:00:00.000Z",
        "updated": "2024-01-18T15:20:00.000Z"
    }


@pytest.fixture
def sample_agent_state(sample_pr_url):
    """Sample AgentState for testing."""
    from agent.review_agent import AgentState
    return {
        "pr_url": sample_pr_url,
        "pr_details": None,
        "jira_ticket_id": None,
        "confluence_page_id": None,
        "jira_context": None,
        "confluence_context": None,
        "review_analysis": None,
        "review_comments": None,
        "error": None,
        "status": "initialized"
    }


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_github_client():
    """Mock GitHub client for testing."""
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_pr = MagicMock()
    
    mock_client.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    
    return mock_client


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Mock LLM response"
    mock_llm.invoke.return_value = mock_response
    return mock_llm


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    mock_server = MagicMock()
    return mock_server

