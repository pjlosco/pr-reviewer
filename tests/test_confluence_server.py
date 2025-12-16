"""
Tests for mcp_servers/confluence_server.py

These tests verify the Confluence MCP server implementation with both real API and stub modes.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch


class TestShouldUseRealApi:
    """Tests for should_use_real_api()"""
    
    def test_should_use_real_api_returns_true_with_credentials(self, mock_confluence_env_vars):
        """
        Test that should_use_real_api returns True when credentials are provided.
        
        Expected behavior:
        - Returns True if CONFLUENCE_URL and CONFLUENCE_API_TOKEN are set
        - Returns False otherwise
        """
        from mcp_servers.confluence_server import should_use_real_api
        
        result = should_use_real_api()
        
        assert result is True
    
    def test_should_use_real_api_returns_false_without_credentials(self, monkeypatch):
        """
        Test that should_use_real_api returns False without credentials.
        
        Expected behavior:
        - Returns False if CONFLUENCE_URL or token is missing
        """
        monkeypatch.delenv("CONFLUENCE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        
        from mcp_servers.confluence_server import should_use_real_api
        
        result = should_use_real_api()
        
        assert result is False


class TestLoadStubData:
    """Tests for load_stub_data()"""
    
    def test_load_stub_data_from_file(self, mock_stub_data_paths, sample_confluence_page_data):
        """
        Test that load_stub_data loads from file when path is set.
        
        Expected behavior:
        - Reads JSON from CONFLUENCE_STUB_DATA_PATH
        - Returns parsed dictionary
        - Caches loaded data
        """
        from mcp_servers.confluence_server import load_stub_data
        
        stub_file = mock_stub_data_paths["confluence"]
        stub_data = {
            "pages": {
                "123456": sample_confluence_page_data
            }
        }
        stub_file.write_text(json.dumps(stub_data))
        
        result = load_stub_data()
        
        assert "pages" in result
        assert "123456" in result["pages"]


class TestFetchPageStub:
    """Tests for fetch_page_stub()"""
    
    def test_fetch_page_stub_returns_page_data(self, sample_confluence_page_data):
        """
        Test that fetch_page_stub returns page from stub data.
        
        Expected behavior:
        - Looks up page by ID in stub data
        - Returns page dictionary
        - Returns None if not found
        """
        from mcp_servers.confluence_server import fetch_page_stub
        
        with patch("mcp_servers.confluence_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {
                "pages": {
                    "123456": sample_confluence_page_data
                }
            }
            
            result = fetch_page_stub("123456")
            
            assert result == sample_confluence_page_data
    
    def test_fetch_page_stub_returns_none_when_not_found(self):
        """
        Test that fetch_page_stub returns None for missing pages.
        
        Expected behavior:
        - Returns None if page ID not in stub data
        """
        from mcp_servers.confluence_server import fetch_page_stub
        
        with patch("mcp_servers.confluence_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {"pages": {}}
            
            result = fetch_page_stub("999999")
            
            assert result is None


class TestGetDomainContext:
    """Tests for get_domain_context() MCP tool"""
    
    @patch("mcp_servers.confluence_server.should_use_real_api")
    @patch("mcp_servers.confluence_server.fetch_page_real_api")
    def test_get_domain_context_uses_real_api(self, mock_fetch_real, mock_should_use, sample_confluence_page_data):
        """
        Test that get_domain_context uses real API when credentials available.
        
        Expected behavior:
        - Calls fetch_page_real_api when should_use_real_api returns True
        - Returns page data from real API
        """
        from mcp_servers.confluence_server import _get_domain_context_impl as get_domain_context
        
        mock_should_use.return_value = True
        mock_fetch_real.return_value = sample_confluence_page_data
        
        result = get_domain_context("123456")
        
        assert result == sample_confluence_page_data
        mock_fetch_real.assert_called_once_with("123456")
    
    @patch("mcp_servers.confluence_server.should_use_real_api")
    @patch("mcp_servers.confluence_server.fetch_page_stub")
    def test_get_domain_context_uses_stub(self, mock_fetch_stub, mock_should_use, sample_confluence_page_data):
        """
        Test that get_domain_context uses stub data when no credentials.
        
        Expected behavior:
        - Calls fetch_page_stub when should_use_real_api returns False
        - Returns page data from stub
        """
        from mcp_servers.confluence_server import _get_domain_context_impl as get_domain_context
        
        mock_should_use.return_value = False
        mock_fetch_stub.return_value = sample_confluence_page_data
        
        result = get_domain_context("123456")
        
        assert result == sample_confluence_page_data
        mock_fetch_stub.assert_called_once_with("123456")


class TestSearchDocumentation:
    """Tests for search_documentation() MCP tool"""
    
    @patch("mcp_servers.confluence_server.should_use_real_api")
    def test_search_documentation_returns_matching_pages(self, mock_should_use):
        """
        Test that search_documentation returns pages matching query.
        
        Expected behavior:
        - Searches stub data or real API for matching pages
        - Returns list of page dictionaries
        - Limits results to specified limit
        """
        from mcp_servers.confluence_server import _search_documentation_impl as search_documentation
        
        mock_should_use.return_value = False
        
        with patch("mcp_servers.confluence_server.get_stub_data") as mock_get_stub:
            mock_get_stub.return_value = {
                "pages": {
                    "123456": {
                        "id": "123456",
                        "title": "Authentication Guide",
                        "body": {"storage": {"value": "OAuth2 authentication"}}
                    }
                }
            }
            
            result = search_documentation("authentication", limit=5)
            
            assert isinstance(result, list)
            assert len(result) <= 5


class TestSearchDocumentationSemantic:
    """Tests for search_documentation_semantic() MCP tool"""
    
    def test_search_documentation_semantic_returns_empty_when_chromadb_not_available(self):
        """
        Test that search_documentation_semantic returns empty list when ChromaDB not available.
        
        Expected behavior:
        - Returns empty list if ChromaDB service is not available
        - Does not raise exceptions
        """
        from mcp_servers.confluence_server import _search_documentation_semantic_impl as search_semantic
        
        with patch("mcp_servers.chromadb_service.get_chromadb_service", return_value=None):
            result = search_semantic("test query", limit=5, min_similarity=0.7)
            
            assert result == []
    
    def test_search_documentation_semantic_handles_exceptions(self):
        """
        Test that search_documentation_semantic handles exceptions gracefully.
        
        Expected behavior:
        - Catches exceptions and returns empty list
        - Does not propagate errors
        """
        from mcp_servers.confluence_server import _search_documentation_semantic_impl as search_semantic
        
        with patch("mcp_servers.chromadb_service.get_chromadb_service", side_effect=Exception("Test error")):
            result = search_semantic("test query", limit=5, min_similarity=0.7)
            
            assert result == []
    
    def test_search_documentation_semantic_calls_service(self):
        """
        Test that search_documentation_semantic calls ChromaDB service.
        
        Expected behavior:
        - Gets ChromaDB service
        - Calls search_semantic on service
        - Returns formatted results
        """
        from mcp_servers.confluence_server import _search_documentation_semantic_impl as search_semantic
        
        mock_service = MagicMock()
        mock_service.search_semantic.return_value = [
            {
                "id": "123456",
                "title": "Test Page",
                "space": {"key": "TEST", "name": "Test Space"},
                "excerpt": "Test excerpt",
                "similarity_score": 0.85,
                "url": "https://confluence.example.com/page/123456"
            }
        ]
        
        with patch("mcp_servers.chromadb_service.get_chromadb_service", return_value=mock_service):
            result = search_semantic("test query", limit=5, min_similarity=0.7)
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "123456"
            mock_service.search_semantic.assert_called_once_with("test query", limit=5, min_similarity=0.7)


class TestCreateConfluenceMcpServer:
    """Tests for create_confluence_mcp_server()"""
    
    def test_create_confluence_mcp_server_returns_configured_server(self):
        """
        Test that create_confluence_mcp_server returns configured MCP server.
        
        Expected behavior:
        - Returns FastMCP server instance
        - Server has all tools registered
        - Server is ready to use
        """
        from mcp_servers.confluence_server import create_confluence_mcp_server
        
        server = create_confluence_mcp_server()
        
        assert server is not None

