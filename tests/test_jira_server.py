"""
Tests for mcp_servers/jira_server.py

These tests verify the Jira MCP server implementation with both real API and stub modes.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path


class TestShouldUseRealApi:
    """Tests for should_use_real_api()"""
    
    def test_should_use_real_api_returns_true_with_credentials(self, mock_jira_env_vars):
        """
        Test that should_use_real_api returns True when credentials are provided.
        
        Expected behavior:
        - Returns True if JIRA_URL and JIRA_API_TOKEN are set
        - Returns False otherwise
        """
        from mcp_servers.jira_server import should_use_real_api
        
        result = should_use_real_api()
        
        assert result is True
    
    def test_should_use_real_api_returns_false_without_credentials(self, monkeypatch):
        """
        Test that should_use_real_api returns False without credentials.
        
        Expected behavior:
        - Returns False if JIRA_URL or token is missing
        """
        monkeypatch.delenv("JIRA_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        
        from mcp_servers.jira_server import should_use_real_api
        
        result = should_use_real_api()
        
        assert result is False


class TestLoadStubData:
    """Tests for load_stub_data()"""
    
    def test_load_stub_data_from_file(self, mock_stub_data_paths, sample_jira_ticket_data):
        """
        Test that load_stub_data loads from file when path is set.
        
        Expected behavior:
        - Reads JSON from JIRA_STUB_DATA_PATH
        - Returns parsed dictionary
        - Caches loaded data
        """
        from mcp_servers.jira_server import load_stub_data
        
        stub_file = mock_stub_data_paths["jira"]
        stub_data = {
            "tickets": {
                "PROJ-123": sample_jira_ticket_data
            }
        }
        stub_file.write_text(json.dumps(stub_data))
        
        result = load_stub_data()
        
        assert "tickets" in result
        assert "PROJ-123" in result["tickets"]
    
    def test_load_stub_data_uses_defaults_when_no_file(self, monkeypatch):
        """
        Test that load_stub_data uses default stubs when no file specified.
        
        Expected behavior:
        - Returns default minimal stub data
        - Does not raise exception
        """
        monkeypatch.delenv("JIRA_STUB_DATA_PATH", raising=False)
        monkeypatch.delenv("JIRA_STUB_DATA_URL", raising=False)
        
        from mcp_servers.jira_server import load_stub_data
        
        result = load_stub_data()
        
        assert isinstance(result, dict)
        # Should have tickets structure even if empty
        assert "tickets" in result or result == {}


class TestFetchTicketStub:
    """Tests for fetch_ticket_stub()"""
    
    def test_fetch_ticket_stub_returns_ticket_data(self, sample_jira_ticket_data):
        """
        Test that fetch_ticket_stub returns ticket from stub data.
        
        Expected behavior:
        - Looks up ticket by key in stub data
        - Returns ticket dictionary
        - Returns None if not found
        """
        from mcp_servers.jira_server import fetch_ticket_stub
        
        # Mock stub data
        with patch("mcp_servers.jira_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {
                "tickets": {
                    "PROJ-123": sample_jira_ticket_data
                }
            }
            
            result = fetch_ticket_stub("PROJ-123")
            
            assert result == sample_jira_ticket_data
    
    def test_fetch_ticket_stub_returns_none_when_not_found(self):
        """
        Test that fetch_ticket_stub returns None for missing tickets.
        
        Expected behavior:
        - Returns None if ticket key not in stub data
        """
        from mcp_servers.jira_server import fetch_ticket_stub
        
        with patch("mcp_servers.jira_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {"tickets": {}}
            
            result = fetch_ticket_stub("PROJ-999")
            
            assert result is None


class TestGetAcceptanceCriteria:
    """Tests for get_acceptance_criteria() MCP tool"""
    
    @patch("mcp_servers.jira_server.should_use_real_api")
    @patch("mcp_servers.jira_server.fetch_ticket_real_api")
    def test_get_acceptance_criteria_uses_real_api(self, mock_fetch_real, mock_should_use, sample_jira_ticket_data):
        """
        Test that get_acceptance_criteria uses real API when credentials available.
        
        Expected behavior:
        - Calls fetch_ticket_real_api when should_use_real_api returns True
        - Returns ticket data from real API
        """
        from mcp_servers.jira_server import _get_acceptance_criteria_impl as get_acceptance_criteria
        
        mock_should_use.return_value = True
        mock_fetch_real.return_value = sample_jira_ticket_data
        
        result = get_acceptance_criteria("PROJ-123")
        
        assert result == sample_jira_ticket_data
        mock_fetch_real.assert_called_once_with("PROJ-123")
    
    @patch("mcp_servers.jira_server.should_use_real_api")
    @patch("mcp_servers.jira_server.fetch_ticket_stub")
    def test_get_acceptance_criteria_uses_stub(self, mock_fetch_stub, mock_should_use, sample_jira_ticket_data):
        """
        Test that get_acceptance_criteria uses stub data when no credentials.
        
        Expected behavior:
        - Calls fetch_ticket_stub when should_use_real_api returns False
        - Returns ticket data from stub
        """
        from mcp_servers.jira_server import _get_acceptance_criteria_impl as get_acceptance_criteria
        
        mock_should_use.return_value = False
        mock_fetch_stub.return_value = sample_jira_ticket_data
        
        result = get_acceptance_criteria("PROJ-123")
        
        assert result == sample_jira_ticket_data
        mock_fetch_stub.assert_called_once_with("PROJ-123")
    
    @patch("mcp_servers.jira_server.should_use_real_api")
    @patch("mcp_servers.jira_server.fetch_ticket_real_api")
    def test_get_acceptance_criteria_handles_api_errors(self, mock_fetch_real, mock_should_use):
        """
        Test that get_acceptance_criteria handles API errors.
        
        Expected behavior:
        - Raises exception on API errors in real API mode
        - Provides clear error message
        """
        from mcp_servers.jira_server import _get_acceptance_criteria_impl as get_acceptance_criteria
        
        mock_should_use.return_value = True
        mock_fetch_real.side_effect = Exception("Jira API Error")
        
        with pytest.raises(Exception, match="Jira API Error"):
            get_acceptance_criteria("PROJ-123")


class TestGetRelatedTickets:
    """Tests for get_related_tickets() MCP tool"""
    
    @patch("mcp_servers.jira_server.should_use_real_api")
    def test_get_related_tickets_returns_from_stub(self, mock_should_use):
        """
        Test that get_related_tickets returns related tickets from stub data.
        
        Expected behavior:
        - Looks up relatedTickets in stub data
        - Returns list of related ticket dictionaries
        """
        from mcp_servers.jira_server import _get_related_tickets_impl as get_related_tickets
        
        mock_should_use.return_value = False
        
        with patch("mcp_servers.jira_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {
                "tickets": {
                    "PROJ-456": {
                        "key": "PROJ-456",
                        "summary": "Related ticket 1",
                        "issueType": "Story"
                    },
                    "PROJ-789": {
                        "key": "PROJ-789",
                        "summary": "Related ticket 2",
                        "issueType": "Bug"
                    }
                },
                "relatedTickets": {
                    "PROJ-123": ["PROJ-456", "PROJ-789"]
                }
            }
            
            result = get_related_tickets("PROJ-123")
            
            assert isinstance(result, list)
            assert len(result) > 0


class TestCreateJiraMcpServer:
    """Tests for create_jira_mcp_server()"""
    
    def test_create_jira_mcp_server_returns_configured_server(self):
        """
        Test that create_jira_mcp_server returns configured MCP server.
        
        Expected behavior:
        - Returns FastMCP server instance
        - Server has all tools registered
        - Server is ready to use
        """
        from mcp_servers.jira_server import create_jira_mcp_server
        
        server = create_jira_mcp_server()
        
        assert server is not None

