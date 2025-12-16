"""
Tests for mcp_servers/chromadb_service.py

These tests verify the ChromaDB service for semantic search.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, Mock
import os


class TestConfluenceChromaService:
    """Tests for ConfluenceChromaService class"""
    
    def test_is_available_returns_false_when_chromadb_not_installed(self, monkeypatch):
        """Test that is_available returns False when ChromaDB is not installed."""
        # Mock the import to fail
        with patch.dict('sys.modules', {'chromadb': None, 'langchain_community.embeddings': None}):
            from mcp_servers.chromadb_service import ConfluenceChromaService
            
            service = ConfluenceChromaService()
            result = service.is_available()
            
            assert result is False
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.LANGCHAIN_CHROMA_AVAILABLE', True)
    def test_is_available_returns_true_when_installed(self):
        """Test that is_available returns True when ChromaDB is installed."""
        from mcp_servers.chromadb_service import ConfluenceChromaService
        
        service = ConfluenceChromaService()
        result = service.is_available()
        
        assert result is True
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.LANGCHAIN_CHROMA_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.OpenAIEmbeddings')
    @patch('mcp_servers.chromadb_service.Chroma')
    def test_search_semantic_returns_empty_when_not_available(self, mock_chroma, mock_embeddings):
        """Test that search_semantic returns empty list when service not available."""
        from mcp_servers.chromadb_service import ConfluenceChromaService
        
        service = ConfluenceChromaService()
        # Mock is_available to return False
        with patch.object(service, 'is_available', return_value=False):
            result = service.search_semantic("test query")
            
            assert result == []
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.LANGCHAIN_CHROMA_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.OpenAIEmbeddings')
    @patch('mcp_servers.chromadb_service.Chroma')
    def test_search_semantic_handles_exceptions(self, mock_chroma, mock_embeddings):
        """Test that search_semantic handles exceptions gracefully."""
        from mcp_servers.chromadb_service import ConfluenceChromaService
        
        service = ConfluenceChromaService()
        with patch.object(service, 'is_available', return_value=True):
            with patch.object(service, '_initialize', side_effect=Exception("Test error")):
                result = service.search_semantic("test query")
                
                assert result == []
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.LANGCHAIN_CHROMA_AVAILABLE', True)
    def test_ingest_page_raises_when_not_available(self):
        """Test that ingest_page raises error when ChromaDB not available."""
        from mcp_servers.chromadb_service import ConfluenceChromaService
        
        service = ConfluenceChromaService()
        with patch.object(service, 'is_available', return_value=False):
            page_data = {
                "id": "123",
                "title": "Test Page",
                "space": {"key": "TEST", "name": "Test Space"},
                "body": {"storage": {"value": "<p>Test content</p>"}}
            }
            
            with pytest.raises(RuntimeError, match="ChromaDB is not available"):
                service.ingest_page(page_data)


class TestGetChromaDbService:
    """Tests for get_chromadb_service() function"""
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', True)
    @patch('mcp_servers.chromadb_service.LANGCHAIN_CHROMA_AVAILABLE', True)
    def test_get_chromadb_service_returns_service_when_available(self):
        """Test that get_chromadb_service returns service when available."""
        from mcp_servers.chromadb_service import get_chromadb_service, _chromadb_service
        
        # Reset global service
        import mcp_servers.chromadb_service
        mcp_servers.chromadb_service._chromadb_service = None
        
        service = get_chromadb_service()
        
        assert service is not None
        assert hasattr(service, 'is_available')
    
    @patch('mcp_servers.chromadb_service.CHROMADB_AVAILABLE', False)
    def test_get_chromadb_service_returns_none_when_not_available(self):
        """Test that get_chromadb_service returns None when ChromaDB not installed."""
        from mcp_servers.chromadb_service import get_chromadb_service, _chromadb_service
        
        # Reset global service
        import mcp_servers.chromadb_service
        mcp_servers.chromadb_service._chromadb_service = None
        
        service = get_chromadb_service()
        
        assert service is None

