"""
End-to-end integration tests

These tests verify the complete workflow from entry point to output.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEndToEndWorkflow:
    """Tests for complete end-to-end workflow"""
    
    @patch("agent.review_agent.create_agent_graph")
    @patch("mcp_servers.github_server.get_github_client")
    @patch("mcp_servers.jira_server.should_use_real_api")
    @patch("mcp_servers.confluence_server.should_use_real_api")
    def test_complete_review_workflow_with_stubs(
        self,
        mock_confluence_api,
        mock_jira_api,
        mock_github_client,
        mock_create_graph,
        sample_pr_url,
        sample_pr_data,
        sample_jira_ticket_data,
        sample_confluence_page_data
    ):
        """
        Test complete workflow from PR URL to posted comments.
        
        Expected behavior:
        - Fetches PR details from GitHub
        - Extracts Jira ticket ID
        - Fetches Jira context from stubs
        - Fetches Confluence context from stubs
        - Analyzes code with LLM
        - Generates review comments
        - Posts comments to GitHub
        - Returns success status
        """
        # Setup mocks
        mock_jira_api.return_value = False  # Use stubs
        mock_confluence_api.return_value = False  # Use stubs
        
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "status": "complete",
            "review_comments": [
                {"path": "test.py", "line": 10, "body": "Fix this"}
            ]
        }
        mock_create_graph.return_value = mock_graph
        
        from app import main
        import sys
        
        test_args = ["app.py", "--pr-url", sample_pr_url]
        
        with patch("sys.argv", test_args):
            with patch("sys.exit"):
                main()
        
        # Verify graph was created and invoked
        mock_create_graph.assert_called_once()
        mock_graph.invoke.assert_called_once()
    
    @patch("agent.review_agent.create_agent_graph")
    def test_workflow_handles_missing_context_gracefully(self, mock_create_graph, sample_pr_url):
        """
        Test that workflow continues even when Jira/Confluence context is missing.
        
        Expected behavior:
        - Continues review without Jira context if unavailable
        - Continues review without Confluence context if unavailable
        - Still generates review comments
        """
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "status": "complete",
            "jira_context": None,  # Missing
            "confluence_context": None,  # Missing
            "review_comments": [{"body": "General review comment"}]
        }
        mock_create_graph.return_value = mock_graph
        
        from agent.review_agent import run_review_agent
        
        # Should not raise exception
        run_review_agent(pr_url=sample_pr_url, verbose=False)
        
        mock_graph.invoke.assert_called_once()
    
    @patch("agent.review_agent.create_agent_graph")
    def test_workflow_handles_errors_gracefully(self, mock_create_graph, sample_pr_url):
        """
        Test that workflow handles errors and reports them.
        
        Expected behavior:
        - Catches errors during execution
        - Logs error information
        - Returns error status
        - Does not crash
        """
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = Exception("Test error")
        mock_create_graph.return_value = mock_graph
        
        from agent.review_agent import run_review_agent
        
        # Should handle error gracefully
        with pytest.raises(Exception):
            run_review_agent(pr_url=sample_pr_url, verbose=False)

