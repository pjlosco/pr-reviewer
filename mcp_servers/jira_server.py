"""
Jira MCP Server

This module provides a FastMCP server that exposes tools for interacting with Jira.
The server can operate in two modes:
1. Real API mode: Connects to actual Jira instance (when credentials provided)
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

# Initialize FastMCP server
mcp = FastMCP("Jira MCP Server")

# Global state for stub data
_stub_data: Optional[dict] = None


# ============================================================================
# Configuration Detection
# ============================================================================

def should_use_real_api() -> bool:
    """
    Determine if we should use real Jira API or stub data.
    
    Checks for JIRA_URL and JIRA_API_TOKEN (or JIRA_BEARER_TOKEN) in
    environment variables. If both are present, uses real API.
    Otherwise, falls back to stub mode.
    
    Returns:
        True if real API should be used, False for stub mode
    """
    jira_url = os.getenv("JIRA_URL")
    jira_token = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_BEARER_TOKEN")
    
    return bool(jira_url and jira_token)


# ============================================================================
# Stub Data Loading
# ============================================================================

def load_stub_data() -> dict:
    """
    Load stub data from file, URL, or use defaults.
    
    This function tries to load stub data in this order:
    1. From JIRA_STUB_DATA_PATH (local file)
    2. From JIRA_STUB_DATA_URL (remote URL)
    3. Default minimal stubs (built-in)
    
    Returns:
        Dictionary containing stub Jira ticket data
    """
    global _stub_data
    
    # Try loading from file path first
    stub_path = os.getenv("JIRA_STUB_DATA_PATH")
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
    stub_url = os.getenv("JIRA_STUB_DATA_URL")
    if stub_url:
        try:
            with urlopen(stub_url) as response:
                _stub_data = json.loads(response.read().decode('utf-8'))
                return _stub_data
        except (URLError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load stub data from {stub_url}: {e}")
    
    # Return default minimal stubs
    _stub_data = {
        "tickets": {},
        "relatedTickets": {}
    }
    return _stub_data


def get_stub_data() -> dict:
    """
    Get stub data, loading it if necessary.
    
    This is a convenience function that ensures stub data is loaded
    before returning it. Uses lazy loading to avoid loading until needed.
    
    Returns:
        Dictionary containing stub Jira ticket data
    """
    global _stub_data
    
    if _stub_data is None:
        _stub_data = load_stub_data()
    
    return _stub_data


# ============================================================================
# Real API Functions
# ============================================================================

def get_jira_client():
    """
    Initialize and return a Jira API client.
    
    This function creates a Jira client using credentials from
    environment variables. Only called when real API mode is enabled.
    
    Returns:
        Authenticated Jira client
        
    Raises:
        ValueError: If required credentials are missing
        ImportError: If jira library is not installed
    """
    try:
        from jira import JIRA
    except ImportError:
        raise ImportError(
            "jira library is required for real API mode. "
            "Install it with: pip install jira"
        )
    
    jira_url = os.getenv("JIRA_URL")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_BEARER_TOKEN")
    
    if not jira_url:
        raise ValueError("JIRA_URL environment variable is required for real API mode")
    if not jira_token:
        raise ValueError("JIRA_API_TOKEN or JIRA_BEARER_TOKEN is required for real API mode")
    
    # Use basic auth with email + API token
    # Jira API tokens are used with basic auth (email + token as password)
    if jira_email:
        return JIRA(server=jira_url, basic_auth=(jira_email, jira_token))
    else:
        # If no email, try token auth (for bearer tokens)
        return JIRA(server=jira_url, token_auth=jira_token)


def fetch_ticket_real_api(ticket_id: str) -> dict:
    """
    Fetch ticket data from real Jira API.
    
    This function makes an actual API call to Jira to retrieve
    ticket information. Only used when real API mode is enabled.
    
    Args:
        ticket_id: Jira ticket ID (e.g., "PROJ-123")
        
    Returns:
        Dictionary containing ticket data matching stub format
        
    Raises:
        Exception: If API call fails
    """
    client = get_jira_client()
    issue = client.issue(ticket_id)
    
    # Transform Jira API response to match stub data format
    assignee = None
    if issue.fields.assignee:
        assignee = {
            "displayName": issue.fields.assignee.displayName,
            "emailAddress": getattr(issue.fields.assignee, 'emailAddress', '')
        }
    
    # Extract acceptance criteria from description or custom field
    acceptance_criteria = []
    description = issue.fields.description or ""
    
    # Try to parse acceptance criteria (common formats)
    # Look for "Acceptance Criteria:" or "AC:" sections
    if "Acceptance Criteria" in description or "AC:" in description:
        # Simple parsing - could be enhanced
        lines = description.split('\n')
        in_ac_section = False
        for line in lines:
            if "Acceptance Criteria" in line or "AC:" in line:
                in_ac_section = True
                continue
            if in_ac_section and line.strip():
                if line.strip().startswith('-') or line.strip().startswith('*'):
                    acceptance_criteria.append(line.strip().lstrip('-* '))
                elif line.strip() and not line.strip().startswith('#'):
                    acceptance_criteria.append(line.strip())
    
    # Get labels
    labels = list(issue.fields.labels) if hasattr(issue.fields, 'labels') and issue.fields.labels else []
    
    return {
        "id": str(issue.id),
        "key": issue.key,
        "summary": issue.fields.summary,
        "description": description,
        "status": str(issue.fields.status),
        "assignee": assignee,
        "acceptanceCriteria": acceptance_criteria,
        "labels": labels,
        "issueType": str(issue.fields.issuetype),
        "priority": str(issue.fields.priority) if hasattr(issue.fields, 'priority') and issue.fields.priority else "Unknown",
        "created": issue.fields.created if hasattr(issue.fields, 'created') else "",
        "updated": issue.fields.updated if hasattr(issue.fields, 'updated') else ""
    }


# ============================================================================
# Stub Data Functions
# ============================================================================

def fetch_ticket_stub(ticket_id: str) -> Optional[dict]:
    """
    Fetch ticket data from stub data.
    
    This function looks up ticket information in the loaded stub data.
    Used when real API is not available or configured.
    
    Args:
        ticket_id: Jira ticket ID (e.g., "PROJ-123")
        
    Returns:
        Dictionary containing ticket data, or None if not found
    """
    stub_data = get_stub_data()
    tickets = stub_data.get("tickets", {})
    
    # Look up ticket by key (e.g., "PROJ-123")
    return tickets.get(ticket_id)


# ============================================================================
# MCP Tools (Exposed to Agent)
# ============================================================================

def _get_acceptance_criteria_impl(jira_ticket_id: str) -> dict:
    """
    Get acceptance criteria and ticket context from Jira.
    
    This tool fetches acceptance criteria and other ticket information
    from Jira. It automatically uses real API if credentials are provided,
    otherwise falls back to stub data.
    
    The agent uses this to understand what requirements the PR should meet
    and tailor the review accordingly.
    
    Args:
        jira_ticket_id: Jira ticket ID (e.g., "PROJ-123")
        
    Returns:
        Dictionary containing ticket information:
        {
            "id": str,
            "key": str,
            "summary": str,
            "description": str,
            "status": str,
            "assignee": {"displayName": str, "emailAddress": str},
            "acceptanceCriteria": [str],
            "labels": [str],
            "issueType": str,
            "priority": str,
            "created": str,
            "updated": str
        }
        
    Raises:
        Exception: If ticket cannot be fetched (in real API mode)
    """
    if should_use_real_api():
        return fetch_ticket_real_api(jira_ticket_id)
    else:
        ticket_data = fetch_ticket_stub(jira_ticket_id)
        if ticket_data is None:
            # Return minimal stub if ticket not found
            return {
                "id": "",
                "key": jira_ticket_id,
                "summary": f"Ticket {jira_ticket_id} (not found in stub data)",
                "description": "",
                "status": "Unknown",
                "assignee": None,
                "acceptanceCriteria": [],
                "labels": [],
                "issueType": "Unknown",
                "priority": "Unknown",
                "created": "",
                "updated": ""
            }
        return ticket_data


@mcp.tool()
def get_acceptance_criteria(jira_ticket_id: str) -> dict:
    """MCP tool wrapper for get_acceptance_criteria."""
    return _get_acceptance_criteria_impl(jira_ticket_id)


def _get_related_tickets_impl(jira_ticket_id: str) -> list[dict]:
    """
    Get related tickets (linked tickets, epics, stories, bugs).
    
    This tool fetches tickets that are related to the given ticket,
    such as linked tickets, parent epics, or related stories.
    
    The agent can use this to understand the broader context of the
    work being done in the PR.
    
    Args:
        jira_ticket_id: Jira ticket ID (e.g., "PROJ-123")
        
    Returns:
        List of related ticket dictionaries, each with:
        {
            "key": str,
            "summary": str,
            "issueType": str,
            "linkType": str  # e.g., "relates to", "blocks", "epic"
        }
    """
    if should_use_real_api():
        # TODO: Implement real API call for related tickets
        # For now, return empty list in real API mode
        return []
    
    # Stub mode: look up in stub data
    stub_data = get_stub_data()
    related_tickets = stub_data.get("relatedTickets", {})
    related_keys = related_tickets.get(jira_ticket_id, [])
    
    # Build list of related ticket info
    result = []
    tickets = stub_data.get("tickets", {})
    
    for related_key in related_keys:
        related_ticket = tickets.get(related_key)
        if related_ticket:
            result.append({
                "key": related_ticket.get("key", related_key),
                "summary": related_ticket.get("summary", ""),
                "issueType": related_ticket.get("issueType", "Unknown"),
                "linkType": "relates to"  # Default link type in stub mode
            })
    
    return result


@mcp.tool()
def get_related_tickets(jira_ticket_id: str) -> list[dict]:
    """MCP tool wrapper for get_related_tickets."""
    return _get_related_tickets_impl(jira_ticket_id)


# ============================================================================
# Server Initialization
# ============================================================================

def create_jira_mcp_server() -> FastMCP:
    """
    Create and return a configured Jira MCP server instance.
    
    This function initializes the MCP server and determines which mode
    (real API or stub) to use based on environment variables.
    
    Returns:
        Configured FastMCP server instance
    """
    use_real_api = should_use_real_api()
    
    if use_real_api:
        print("Jira MCP Server: Using real Jira API")
    else:
        print("Jira MCP Server: Using stub data mode")
        # Preload stub data if in stub mode
        get_stub_data()
    
    return mcp


# Export implementation functions for testing
__all__ = [
    "should_use_real_api",
    "load_stub_data",
    "get_stub_data",
    "get_jira_client",
    "fetch_ticket_real_api",
    "fetch_ticket_stub",
    "get_acceptance_criteria",  # MCP tool (wrapped)
    "_get_acceptance_criteria_impl",  # Implementation (for testing)
    "get_related_tickets",  # MCP tool (wrapped)
    "_get_related_tickets_impl",  # Implementation (for testing)
    "create_jira_mcp_server",
    "mcp",
]


if __name__ == "__main__":
    # For testing: run the server directly
    # TODO: Initialize and run MCP server
    pass

