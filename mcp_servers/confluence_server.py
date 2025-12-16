"""
Confluence MCP Server

This module provides a FastMCP server that exposes tools for interacting with Confluence.
The server can operate in two modes:
1. Real API mode: Connects to actual Confluence instance (when credentials provided)
2. Stub mode: Uses stub data from files or default stubs (when no credentials)

The server automatically detects which mode to use based on environment variables.
"""

import os
import json
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError
from fastmcp import FastMCP

# Optional imports for real API mode
try:
    from langchain_community.document_loaders import ConfluenceLoader
except ImportError:
    ConfluenceLoader = None  # type: ignore

try:
    from atlassian import Confluence
except ImportError:
    Confluence = None  # type: ignore

# Initialize FastMCP server
mcp = FastMCP("Confluence MCP Server")

# Global state for stub data
_stub_data: Optional[dict] = None


# ============================================================================
# Configuration Detection
# ============================================================================

def should_use_real_api() -> bool:
    """
    Determine if we should use real Confluence API or stub data.
    
    Checks for CONFLUENCE_URL and CONFLUENCE_API_TOKEN (or CONFLUENCE_BEARER_TOKEN)
    in environment variables. If both are present, uses real API.
    Otherwise, falls back to stub mode.
    
    Returns:
        True if real API should be used, False for stub mode
    """
    confluence_url = os.getenv("CONFLUENCE_URL")
    confluence_token = os.getenv("CONFLUENCE_API_TOKEN") or os.getenv("CONFLUENCE_BEARER_TOKEN")
    
    return bool(confluence_url and confluence_token)


# ============================================================================
# Stub Data Loading
# ============================================================================

def load_stub_data() -> dict:
    """
    Load stub data from file, URL, or use defaults.
    
    This function tries to load stub data in this order:
    1. From CONFLUENCE_STUB_DATA_PATH (local file)
    2. From CONFLUENCE_STUB_DATA_URL (remote URL)
    3. Default minimal stubs (built-in)
    
    Returns:
        Dictionary containing stub Confluence page data
    """
    global _stub_data
    
    # Try loading from file path first
    stub_path = os.getenv("CONFLUENCE_STUB_DATA_PATH")
    if stub_path:
        try:
            path = Path(stub_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    _stub_data = json.load(f)
                    return _stub_data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load stub data from {stub_path}: {e}")
    
    # Try loading from URL
    stub_url = os.getenv("CONFLUENCE_STUB_DATA_URL")
    if stub_url:
        try:
            with urlopen(stub_url) as response:
                _stub_data = json.loads(response.read().decode('utf-8'))
                return _stub_data
        except (URLError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load stub data from {stub_url}: {e}")
    
    # Return default minimal stubs
    _stub_data = {
        "pages": {},
        "spaces": {}
    }
    return _stub_data


def get_stub_data() -> dict:
    """
    Get stub data, loading it if necessary.
    
    This is a convenience function that ensures stub data is loaded
    before returning it. Uses lazy loading to avoid loading until needed.
    
    Returns:
        Dictionary containing stub Confluence page data
    """
    global _stub_data
    
    if _stub_data is None:
        _stub_data = load_stub_data()
    
    return _stub_data


# ============================================================================
# Real API Functions
# ============================================================================

def get_confluence_loader():
    """
    Initialize and return a LangChain ConfluenceLoader.
    
    This function creates a ConfluenceLoader using credentials from
    environment variables. Only called when real API mode is enabled.
    Uses LangChain's built-in ConfluenceLoader for consistency with
    the rest of the LangChain-based project.
    
    Returns:
        Configured ConfluenceLoader instance
        
    Raises:
        ValueError: If required credentials are missing
        ImportError: If langchain-community library is not installed
    """
    if ConfluenceLoader is None:
        raise ImportError(
            "langchain-community library is required for real API mode. "
            "Install it with: pip install langchain-community"
        )
    
    confluence_url = os.getenv("CONFLUENCE_URL")
    confluence_email = os.getenv("CONFLUENCE_EMAIL")
    confluence_token = os.getenv("CONFLUENCE_API_TOKEN") or os.getenv("CONFLUENCE_BEARER_TOKEN")
    
    if not confluence_url:
        raise ValueError("CONFLUENCE_URL environment variable is required for real API mode")
    if not confluence_token:
        raise ValueError("CONFLUENCE_API_TOKEN or CONFLUENCE_BEARER_TOKEN is required for real API mode")
    
    # ConfluenceLoader requires username and api_key
    # If email is not provided, we'll use a placeholder (some Confluence instances allow this)
    username = confluence_email or "api_user"
    
    return ConfluenceLoader(
        url=confluence_url,
        username=username,
        api_key=confluence_token,
        include_attachments=False,  # We don't need attachments for code review context
    )


def _get_confluence_client_from_loader():
    """
    Get the underlying Confluence client from ConfluenceLoader.
    
    ConfluenceLoader wraps atlassian-python-api's Confluence client.
    This helper function extracts the client for direct API access when needed.
    
    Returns:
        Confluence client instance
        
    Raises:
        ImportError: If atlassian library is not installed
    """
    if Confluence is None:
        raise ImportError(
            "atlassian library is required for real API mode. "
            "Install it with: pip install atlassian-python-api"
        )
    
    confluence_url = os.getenv("CONFLUENCE_URL")
    confluence_email = os.getenv("CONFLUENCE_EMAIL")
    confluence_token = os.getenv("CONFLUENCE_API_TOKEN") or os.getenv("CONFLUENCE_BEARER_TOKEN")
    username = confluence_email or "api_user"
    
    return Confluence(
        url=confluence_url,
        username=username,
        password=confluence_token
    )


def fetch_page_real_api(page_id: str) -> dict:
    """
    Fetch page data from real Confluence API using LangChain's ConfluenceLoader.
    
    This function uses LangChain's ConfluenceLoader for authentication consistency,
    but accesses the underlying Confluence client for page-by-ID operations since
    ConfluenceLoader is optimized for space-based loading.
    
    Args:
        page_id: Confluence page ID (e.g., "123456")
        
    Returns:
        Dictionary containing page data matching stub format
        
    Raises:
        Exception: If API call fails
    """
    # Initialize loader to ensure credentials are validated
    # (This ensures we're using LangChain's consistent auth approach)
    get_confluence_loader()
    
    # Use the underlying client for page-by-ID access
    # ConfluenceLoader is great for space-based loading, but for specific pages
    # we use the client directly
    client = _get_confluence_client_from_loader()
    
    page = client.get_page_by_id(page_id, expand='body.storage,version,space')
    space = page.get('space', {})
    
    return {
        "id": page.get('id', page_id),
        "title": page.get('title', ''),
        "space": {
            "key": space.get('key', ''),
            "name": space.get('name', '')
        },
        "body": {
            "storage": {
                "value": page.get('body', {}).get('storage', {}).get('value', '')
            }
        },
        "version": {
            "number": page.get('version', {}).get('number', 1)
        },
        "created": page.get('history', {}).get('createdDate', ''),
        "updated": page.get('version', {}).get('when', '')
    }


# ============================================================================
# Stub Data Functions
# ============================================================================

def fetch_page_stub(page_id: str) -> Optional[dict]:
    """
    Fetch page data from stub data.
    
    This function looks up page information in the loaded stub data.
    Used when real API is not available or configured.
    
    Args:
        page_id: Confluence page ID (e.g., "123456")
        
    Returns:
        Dictionary containing page data, or None if not found
    """
    stub_data = get_stub_data()
    pages = stub_data.get("pages", {})
    
    # Look up page by ID
    return pages.get(page_id)


# ============================================================================
# MCP Tools (Exposed to Agent)
# ============================================================================

def _get_domain_context_impl(confluence_page_id: str) -> dict:
    """
    Get domain context and documentation from Confluence.
    
    This tool fetches page content and related information from Confluence.
    It automatically uses real API if credentials are provided, otherwise
    falls back to stub data.
    
    The agent uses this to understand domain-specific guidelines, architecture
    patterns, and documentation that should inform the code review.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        confluence_page_id: Confluence page ID (e.g., "123456")
        
    Returns:
        Dictionary containing page information:
        {
            "id": str,
            "title": str,
            "space": {"key": str, "name": str},
            "body": {"storage": {"value": str}},  # HTML content
            "version": {"number": int},
            "created": str,
            "updated": str
        }
        
    Raises:
        Exception: If page cannot be fetched (in real API mode)
    """
    if should_use_real_api():
        return fetch_page_real_api(confluence_page_id)
    else:
        page_data = fetch_page_stub(confluence_page_id)
        if page_data is None:
            # Return minimal stub if page not found
            return {
                "id": confluence_page_id,
                "title": f"Page {confluence_page_id} (not found in stub data)",
                "space": {"key": "UNKNOWN", "name": "Unknown"},
                "body": {"storage": {"value": ""}},
                "version": {"number": 1},
                "created": "",
                "updated": ""
            }
        return page_data


@mcp.tool()
def get_domain_context(confluence_page_id: str) -> dict:
    """MCP tool wrapper for get_domain_context."""
    return _get_domain_context_impl(confluence_page_id)


def _search_documentation_semantic_impl(query: str, limit: int = 5, min_similarity: float = 0.7) -> list[dict]:
    """
    Search Confluence documentation using semantic similarity via ChromaDB.
    
    This tool uses ChromaDB to find relevant Confluence pages based on
    semantic meaning rather than just keyword matching. It's particularly
    useful when the agent needs to find relevant documentation based on
    code changes or PR context.
    
    **Note**: This requires ChromaDB to be set up and populated with
    Confluence pages. If ChromaDB is not available, returns empty list.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        query: Natural language query describing what documentation is needed
        limit: Maximum number of results to return (default: 5)
        min_similarity: Minimum similarity score (0.0-1.0, default: 0.7)
        
    Returns:
        List of relevant Confluence pages with similarity scores:
        [
            {
                "id": str,
                "title": str,
                "space": {"key": str, "name": str},
                "excerpt": str,
                "similarity_score": float,
                "url": str
            }
        ]
    """
    try:
        from mcp_servers.chromadb_service import get_chromadb_service
        
        service = get_chromadb_service()
        if not service:
            # ChromaDB not available, return empty list
            return []
        
        return service.search_semantic(query, limit=limit, min_similarity=min_similarity)
    except Exception as e:
        print(f"Warning: Semantic search failed: {e}")
        return []


@mcp.tool()
def search_documentation_semantic(query: str, limit: int = 5, min_similarity: float = 0.7) -> list[dict]:
    """MCP tool wrapper for search_documentation_semantic."""
    return _search_documentation_semantic_impl(query, limit, min_similarity)


def _search_documentation_impl(query: str, limit: int = 10) -> list[dict]:
    """
    Search Confluence for relevant documentation.
    
    This tool searches Confluence pages based on a query string.
    The agent can use this to find relevant documentation when it doesn't
    have a specific page ID.
    
    Currently uses keyword-based search (CQL for real API, text matching for stubs).
    
    **Future Enhancement**: See docs/chromadb-integration.md for plans to add
    semantic search using ChromaDB when page IDs are not specified. This would
    enable finding relevant documentation based on semantic similarity rather
    than just keyword matching.
    
    Implementation function (called by MCP tool wrapper).
    
    Args:
        query: Search query string
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        List of page dictionaries matching the search, each with:
        {
            "id": str,
            "title": str,
            "space": {"key": str, "name": str},
            "excerpt": str,  # Snippet of matching content
            "url": str
        }
    """
    if should_use_real_api():
        # Use ConfluenceLoader for auth validation, then underlying client for search
        # ConfluenceLoader doesn't have built-in search, so we use CQL via the client
        try:
            # Initialize loader to ensure credentials are validated
            get_confluence_loader()
            
            # Use the underlying client for CQL search
            client = _get_confluence_client_from_loader()
            confluence_url = os.getenv("CONFLUENCE_URL")
            
            # Use CQL (Confluence Query Language) to search
            # CQL format: text ~ "query" or title ~ "query"
            cql_query = f'text ~ "{query}" OR title ~ "{query}"'
            search_results = client.cql(cql_query, limit=limit)
            
            results = []
            for result in search_results.get('results', []):
                page_id = result.get('content', {}).get('id', '')
                title = result.get('content', {}).get('title', '')
                space_key = result.get('content', {}).get('space', {}).get('key', '')
                space_name = result.get('content', {}).get('space', {}).get('name', '')
                
                # Get excerpt from the result
                excerpt = result.get('excerpt', '')[:200] + "..." if len(result.get('excerpt', '')) > 200 else result.get('excerpt', '')
                
                results.append({
                    "id": page_id,
                    "title": title,
                    "space": {
                        "key": space_key,
                        "name": space_name
                    },
                    "excerpt": excerpt,
                    "url": f"{confluence_url}/pages/viewpage.action?pageId={page_id}"
                })
            
            return results
        except Exception as e:
            # If search fails, return empty list
            print(f"Warning: Confluence search failed: {e}")
            return []
    
    # Stub mode: simple text search in stub data
    stub_data = get_stub_data()
    pages = stub_data.get("pages", {})
    query_lower = query.lower()
    
    results = []
    for page_id, page in pages.items():
        # Search in title and body
        title = page.get("title", "").lower()
        body = page.get("body", {}).get("storage", {}).get("value", "").lower()
        
        if query_lower in title or query_lower in body:
            # Extract excerpt (first 200 chars of body)
            body_text = page.get("body", {}).get("storage", {}).get("value", "")
            excerpt = body_text[:200] + "..." if len(body_text) > 200 else body_text
            
            space = page.get("space", {})
            results.append({
                "id": page_id,
                "title": page.get("title", ""),
                "space": {
                    "key": space.get("key", ""),
                    "name": space.get("name", "")
                },
                "excerpt": excerpt,
                "url": f"https://confluence.example.com/pages/viewpage.action?pageId={page_id}"
            })
            
            if len(results) >= limit:
                break
    
    return results


@mcp.tool()
def search_documentation(query: str, limit: int = 10) -> list[dict]:
    """MCP tool wrapper for search_documentation."""
    return _search_documentation_impl(query, limit)


# ============================================================================
# Server Initialization
# ============================================================================

def create_confluence_mcp_server() -> FastMCP:
    """
    Create and return a configured Confluence MCP server instance.
    
    This function initializes the MCP server and determines which mode
    (real API or stub) to use based on environment variables.
    
    Returns:
        Configured FastMCP server instance
    """
    use_real_api = should_use_real_api()
    
    if use_real_api:
        print("Confluence MCP Server: Using real Confluence API")
    else:
        print("Confluence MCP Server: Using stub data mode")
        # Preload stub data if in stub mode
        get_stub_data()
    
    return mcp


# Export implementation functions for testing
__all__ = [
    "should_use_real_api",
    "load_stub_data",
    "get_stub_data",
    "get_confluence_loader",
    "fetch_page_real_api",
    "fetch_page_stub",
    "get_domain_context",  # MCP tool (wrapped)
    "_get_domain_context_impl",  # Implementation (for testing)
    "search_documentation",  # MCP tool (wrapped)
    "_search_documentation_impl",  # Implementation (for testing)
    "search_documentation_semantic",  # MCP tool (wrapped)
    "_search_documentation_semantic_impl",  # Implementation (for testing)
    "create_confluence_mcp_server",
    "mcp",
]


if __name__ == "__main__":
    # For testing: run the server directly
    # TODO: Initialize and run MCP server
    pass

