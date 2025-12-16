"""
Tests for agent/review_agent.py

These tests verify the LangGraph state machine and agent logic.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from agent.review_agent import (
    AgentState,
    initialize_node,
    fetch_pr_details_node,
    extract_context_ids_node,
    fetch_jira_context_node,
    fetch_confluence_context_node,
    analyze_code_node,
    generate_review_node,
    post_review_node,
    error_node,
    should_continue,
    should_fetch_jira,
    run_review_agent,
    create_agent_graph,
    get_llm_client,
    extract_jira_ticket_id,
    extract_confluence_page_id,
)


class TestInitializeNode:
    """Tests for initialize_node()"""
    
    def test_initialize_node_validates_pr_url(self, sample_pr_url):
        """
        Test that initialize_node validates PR URL format.
        
        Expected behavior:
        - Validates URL format
        - Extracts repository and PR number
        - Sets initial status
        - Returns updated state
        """
        state = {"pr_url": sample_pr_url, "status": None}
        
        result = initialize_node(state)
        
        assert result["status"] is not None
        assert "pr_url" in result
    
    def test_initialize_node_rejects_invalid_url(self):
        """
        Test that initialize_node rejects invalid PR URLs.
        
        Expected behavior:
        - Raises ValueError or sets error state for invalid URLs
        """
        state = {"pr_url": "not-a-valid-url", "status": None}
        
        # Should handle invalid URL gracefully
        try:
            result = initialize_node(state)
            if isinstance(result, dict):
                assert "error" in result or result.get("status") == "error"
        except (ValueError, KeyError):
            # Expected exception for invalid URL
            pass


class TestFetchPrDetailsNode:
    """Tests for fetch_pr_details_node()"""
    
    @patch("agent.review_agent._get_pr_details_impl")
    def test_fetch_pr_details_calls_github_mcp(self, mock_get_pr, sample_pr_url, sample_pr_data):
        """
        Test that fetch_pr_details_node calls GitHub MCP server.
        
        Expected behavior:
        - Calls _get_pr_details_impl directly
        - Stores PR details in state
        """
        mock_get_pr.return_value = sample_pr_data
        
        state = {"pr_url": sample_pr_url, "pr_details": None}
        
        result = fetch_pr_details_node(state)
        
        assert result["pr_details"] == sample_pr_data
        mock_get_pr.assert_called_once_with(sample_pr_url)
    
    @patch("agent.review_agent._get_pr_details_impl")
    def test_fetch_pr_details_handles_errors(self, mock_get_pr, sample_pr_url):
        """
        Test that fetch_pr_details_node handles API errors gracefully.
        
        Expected behavior:
        - Sets error state on exception
        """
        mock_get_pr.side_effect = Exception("API Error")
        
        state = {"pr_url": sample_pr_url, "pr_details": None, "error": None}
        
        result = fetch_pr_details_node(state)
        
        # Should handle error and set error state
        assert "error" in result
        assert result.get("pr_details") is None


class TestExtractContextIdsNode:
    """Tests for extract_context_ids_node()"""
    
    def test_extract_context_ids_finds_jira_ticket(self, sample_pr_data):
        """
        Test that extract_context_ids_node finds Jira ticket ID in PR description.
        
        Expected behavior:
        - Parses PR description for ticket patterns (e.g., "PROJ-123")
        - Checks PR labels for ticket references
        - Stores ticket ID in state
        """
        sample_pr_data["description"] = "Fixes PROJ-123"
        state = {"pr_details": sample_pr_data, "jira_ticket_id": None}
        
        result = extract_context_ids_node(state)
        
        assert result["jira_ticket_id"] == "PROJ-123"
    
    def test_extract_context_ids_finds_in_labels(self, sample_pr_data):
        """
        Test that extract_context_ids_node finds ticket ID in PR labels.
        
        Expected behavior:
        - Checks labels for ticket patterns
        - Extracts ticket ID from labels
        """
        # Clear description so it doesn't find PROJ-123 from there
        sample_pr_data["description"] = "No ticket in description"
        sample_pr_data["labels"] = ["bug", "PROJ-456"]
        state = {"pr_details": sample_pr_data, "jira_ticket_id": None}
        
        result = extract_context_ids_node(state)
        
        assert result["jira_ticket_id"] == "PROJ-456"
    
    def test_extract_context_ids_handles_no_ticket(self, sample_pr_data):
        """
        Test that extract_context_ids_node handles PRs without ticket references.
        
        Expected behavior:
        - Returns state with jira_ticket_id as None
        - Continues without error
        """
        sample_pr_data["description"] = "No ticket reference"
        sample_pr_data["labels"] = []
        state = {"pr_details": sample_pr_data, "jira_ticket_id": None}
        
        result = extract_context_ids_node(state)
        
        assert result["jira_ticket_id"] is None


class TestFetchJiraContextNode:
    """Tests for fetch_jira_context_node()"""
    
    @patch("agent.review_agent._get_acceptance_criteria_impl")
    def test_fetch_jira_context_calls_jira_mcp(self, mock_get_jira, sample_jira_ticket_data):
        """
        Test that fetch_jira_context_node calls Jira MCP server.
        
        Expected behavior:
        - Calls _get_acceptance_criteria_impl directly
        - Stores Jira context in state
        """
        mock_get_jira.return_value = sample_jira_ticket_data
        
        state = {"jira_ticket_id": "PROJ-123", "jira_context": None}
        
        result = fetch_jira_context_node(state)
        
        assert result["jira_context"] == sample_jira_ticket_data
        mock_get_jira.assert_called_once_with("PROJ-123")
    
    def test_fetch_jira_context_skips_when_no_ticket(self):
        """
        Test that fetch_jira_context_node skips when no ticket ID.
        
        Expected behavior:
        - Returns state unchanged if no ticket ID
        - Does not call MCP server
        """
        state = {"jira_ticket_id": None, "jira_context": None}
        
        result = fetch_jira_context_node(state)
        
        assert result["jira_context"] is None
    
    @patch("agent.review_agent._get_acceptance_criteria_impl")
    def test_fetch_jira_context_handles_errors_gracefully(self, mock_get_jira):
        """
        Test that fetch_jira_context_node continues on error.
        
        Expected behavior:
        - Logs warning on error
        - Continues without blocking review
        - Sets jira_context to None
        """
        mock_get_jira.side_effect = Exception("Jira API Error")
        
        state = {"jira_ticket_id": "PROJ-123", "jira_context": None}
        
        result = fetch_jira_context_node(state)
        
        # Should not raise exception, should continue
        assert result["jira_context"] is None
        assert "error" not in result


class TestFetchConfluenceContextNode:
    """Tests for fetch_confluence_context_node()"""
    
    def test_fetch_confluence_context_calls_confluence_mcp(self, sample_confluence_page_data):
        """
        Test that fetch_confluence_context_node calls Confluence MCP server when page ID provided.
        
        Expected behavior:
        - Calls get_domain_context when page ID is available
        - Stores context in state
        - Handles errors gracefully
        """
        with patch("agent.review_agent._get_domain_context_impl", return_value=sample_confluence_page_data):
            state = {
                "confluence_page_id": "123456",
                "confluence_context": None,
                "status": "jira_context_fetched"
            }
            
            result = fetch_confluence_context_node(state)
            
            assert result["confluence_context"] == sample_confluence_page_data
            assert result["status"] == "confluence_context_fetched"
    
    def test_fetch_confluence_context_skips_when_no_page_id(self):
        """
        Test that fetch_confluence_context_node attempts semantic search when no page ID.
        
        Expected behavior:
        - Tries semantic search via ChromaDB when no page ID
        - Falls back to keyword search if semantic search fails
        - Returns state with context if found, None otherwise
        """
        state = {
            "confluence_page_id": None,
            "confluence_context": None,
            "pr_details": {
                "title": "Test PR",
                "description": "Testing authentication",
                "files": [{"path": "auth.py"}]
            },
            "status": "jira_context_fetched"
        }
        
        # Mock semantic search to return empty (ChromaDB not available)
        with patch("agent.review_agent._search_documentation_semantic_impl", return_value=[]):
            # Mock keyword search to also return empty
            with patch("mcp_servers.confluence_server._search_documentation_impl", return_value=[]):
                result = fetch_confluence_context_node(state)
                
                assert result["confluence_context"] is None
                assert result["status"] == "confluence_context_fetched"
    
    def test_fetch_confluence_context_uses_semantic_search_result(self, sample_confluence_page_data):
        """
        Test that fetch_confluence_context_node uses semantic search results.
        
        Expected behavior:
        - When semantic search finds results, fetches full page content
        - Adds semantic search metadata to context
        """
        semantic_results = [
            {
                "id": "123456",
                "title": "Authentication Guide",
                "similarity_score": 0.85,
                "space": {"key": "ENG", "name": "Engineering"}
            }
        ]
        
        state = {
            "confluence_page_id": None,
            "confluence_context": None,
            "pr_details": {
                "title": "Add OAuth2 authentication",
                "description": "Implement OAuth2 flow",
                "files": [{"path": "auth.py"}]
            },
            "status": "jira_context_fetched"
        }
        
        with patch("agent.review_agent._search_documentation_semantic_impl", return_value=semantic_results):
            with patch("agent.review_agent._get_domain_context_impl", return_value=sample_confluence_page_data):
                result = fetch_confluence_context_node(state)
                
                assert result["confluence_context"] is not None
                assert result["confluence_context"]["_semantic_search"] is not None
                assert result["confluence_context"]["_semantic_search"]["similarity_score"] == 0.85
                assert result["status"] == "confluence_context_fetched"
    
    def test_fetch_confluence_context_falls_back_to_keyword_search(self, sample_confluence_page_data):
        """
        Test that fetch_confluence_context_node falls back to keyword search.
        
        Expected behavior:
        - When semantic search returns empty, tries keyword search
        - Uses keyword search result if found
        """
        keyword_results = [
            {
                "id": "123456",
                "title": "Authentication Guide",
                "space": {"key": "ENG", "name": "Engineering"}
            }
        ]
        
        state = {
            "confluence_page_id": None,
            "confluence_context": None,
            "pr_details": {
                "title": "Add OAuth2 authentication",
                "description": "Implement OAuth2 flow",
                "files": [{"path": "auth.py"}]
            },
            "status": "jira_context_fetched"
        }
        
        with patch("agent.review_agent._search_documentation_semantic_impl", return_value=[]):
            with patch("mcp_servers.confluence_server._search_documentation_impl", return_value=keyword_results):
                with patch("agent.review_agent._get_domain_context_impl", return_value=sample_confluence_page_data):
                    result = fetch_confluence_context_node(state)
                    
                    assert result["confluence_context"] is not None
                    assert result["confluence_context"]["_keyword_search"] is True
                    assert result["status"] == "confluence_context_fetched"


class TestAnalyzeCodeNode:
    """Tests for analyze_code_node()"""
    
    @patch("agent.review_agent.get_llm_client")
    def test_analyze_code_calls_llm(self, mock_get_llm, sample_pr_data, sample_jira_ticket_data):
        """
        Test that analyze_code_node calls LLM with all context.
        
        Expected behavior:
        - Builds prompt with PR diff, Jira criteria, Confluence context
        - Calls LLM to analyze code
        - Stores analysis results in state
        """
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Code analysis: Looks good"
        mock_get_llm.return_value = mock_llm
        
        state = {
            "pr_details": sample_pr_data,
            "jira_context": sample_jira_ticket_data,
            "confluence_context": None,
            "review_analysis": None
        }
        
        result = analyze_code_node(state)
        
        assert result["review_analysis"] is not None
        mock_llm.invoke.assert_called_once()


class TestGenerateReviewNode:
    """Tests for generate_review_node()"""
    
    @patch("agent.review_agent.get_llm_client")
    def test_generate_review_creates_comments(self, mock_get_llm, sample_pr_data):
        """
        Test that generate_review_node creates review comments.
        
        Expected behavior:
        - Uses LLM to generate comments from analysis
        - Formats comments for GitHub PR
        - Structures comments by file/line
        """
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"summary": "Review", "comments": [{"path": "test.py", "line": 10, "body": "Fix this"}]}'
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm
        
        state = {
            "review_analysis": "Analysis results",
            "review_comments": None,
            "pr_details": sample_pr_data
        }
        
        result = generate_review_node(state)
        
        assert result["review_comments"] is not None
        assert isinstance(result["review_comments"], list)


class TestPostReviewNode:
    """Tests for post_review_node()"""
    
    @patch("agent.review_agent._post_review_comments_impl")
    def test_post_review_posts_comments(self, mock_post_comments, sample_pr_url):
        """
        Test that post_review_node posts comments to GitHub.
        
        Expected behavior:
        - Calls _post_review_comments_impl directly
        - Posts comments to PR
        - Updates status to complete
        """
        mock_post_comments.return_value = {"posted": 3, "failed": 0}
        
        review_comments = [
            {"path": "test.py", "line": 10, "body": "Fix this"}
        ]
        
        state = {
            "pr_url": sample_pr_url,
            "review_comments": review_comments,
            "status": "generated"
        }
        
        result = post_review_node(state)
        
        assert result["status"] == "complete"
        mock_post_comments.assert_called_once_with(sample_pr_url, review_comments)


class TestRoutingFunctions:
    """Tests for routing/conditional functions"""
    
    def test_should_continue_with_valid_pr_details(self, sample_pr_data):
        """
        Test that should_continue returns 'continue' with valid PR details.
        
        Expected behavior:
        - Returns "continue" if pr_details exists and is valid
        - Returns "error" if pr_details is missing or invalid
        """
        state = {"pr_details": sample_pr_data}
        
        result = should_continue(state)
        
        assert result == "continue"
    
    def test_should_continue_with_missing_pr_details(self):
        """
        Test that should_continue returns 'error' when PR details missing.
        
        Expected behavior:
        - Returns "error" if pr_details is None or missing
        """
        state = {"pr_details": None}
        
        result = should_continue(state)
        
        assert result == "error"
    
    def test_should_fetch_jira_with_ticket_id(self):
        """
        Test that should_fetch_jira returns 'fetch_jira' when ticket ID exists.
        
        Expected behavior:
        - Returns "fetch_jira" if jira_ticket_id exists
        - Returns "skip_jira" if jira_ticket_id is None
        """
        state = {"jira_ticket_id": "PROJ-123"}
        
        result = should_fetch_jira(state)
        
        assert result == "fetch_jira"
    
    def test_should_fetch_jira_without_ticket_id(self):
        """
        Test that should_fetch_jira returns 'skip_jira' when no ticket ID.
        
        Expected behavior:
        - Returns "skip_jira" if jira_ticket_id is None
        """
        state = {"jira_ticket_id": None}
        
        result = should_fetch_jira(state)
        
        assert result == "skip_jira"


class TestRunReviewAgent:
    """Tests for run_review_agent() main function"""
    
    @patch("agent.review_agent.create_agent_graph")
    def test_run_review_agent_creates_and_runs_graph(self, mock_create_graph, sample_pr_url):
        """
        Test that run_review_agent creates and executes the state graph.
        
        Expected behavior:
        - Creates LangGraph state machine
        - Executes graph with initial state
        - Handles final state
        """
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "complete"}
        mock_create_graph.return_value = mock_graph
        
        run_review_agent(pr_url=sample_pr_url, verbose=False)
        
        mock_create_graph.assert_called_once()
        mock_graph.invoke.assert_called_once()


class TestCreateAgentGraph:
    """Tests for create_agent_graph()"""
    
    def test_create_agent_graph_returns_state_graph(self):
        """
        Test that create_agent_graph returns a StateGraph.
        
        Expected behavior:
        - Returns StateGraph instance
        - Graph has all nodes added
        - Graph has edges configured
        """
        graph = create_agent_graph()
        
        assert graph is not None
        # Graph should be a StateGraph instance
        # (exact type checking depends on LangGraph implementation)


class TestGetLlmClient:
    """Tests for get_llm_client()"""
    
    @patch.dict("os.environ", {
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "gpt-3.5-turbo",
        "LLM_TEMPERATURE": "0.7",
        "OPENAI_API_KEY": "test-key"
    })
    @patch("langchain_openai.ChatOpenAI")
    def test_get_llm_client_openai(self, mock_chat_openai):
        """Test that get_llm_client creates OpenAI client."""
        get_llm_client()
        mock_chat_openai.assert_called_once()
    
    @patch.dict("os.environ", {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-3-haiku-20240307",
        "ANTHROPIC_API_KEY": "test-key"
    })
    @patch("builtins.__import__")
    def test_get_llm_client_anthropic(self, mock_import):
        """Test that get_llm_client creates Anthropic client."""
        # Mock the import to return a mock class
        mock_chat_anthropic = MagicMock()
        mock_module = MagicMock()
        mock_module.ChatAnthropic = mock_chat_anthropic
        mock_import.return_value = mock_module
        
        get_llm_client()
        # Verify import was attempted
        assert any("langchain_anthropic" in str(call) for call in mock_import.call_args_list)
    
    @patch.dict("os.environ", {
        "LLM_PROVIDER": "google",
        "LLM_MODEL": "gemini-pro",
        "GOOGLE_API_KEY": "test-key"
    })
    @patch("builtins.__import__")
    def test_get_llm_client_google(self, mock_import):
        """Test that get_llm_client creates Google client."""
        # Mock the import to return a mock class
        mock_chat_google = MagicMock()
        mock_module = MagicMock()
        mock_module.ChatGoogleGenerativeAI = mock_chat_google
        mock_import.return_value = mock_module
        
        get_llm_client()
        # Verify import was attempted
        assert any("langchain_google_genai" in str(call) for call in mock_import.call_args_list)
    
    @patch.dict("os.environ", {}, clear=True)
    def test_get_llm_client_missing_api_key(self):
        """Test that get_llm_client raises error when API key missing."""
        with patch.dict("os.environ", {"LLM_PROVIDER": "openai"}, clear=False):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_llm_client()
    
    @patch.dict("os.environ", {
        "LLM_PROVIDER": "invalid",
    }, clear=True)
    def test_get_llm_client_invalid_provider(self):
        """Test that get_llm_client raises error for invalid provider."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_client()


class TestExtractJiraTicketId:
    """Tests for extract_jira_ticket_id()"""
    
    def test_extract_jira_ticket_id_from_description(self):
        """Test extracting ticket ID from PR description."""
        description = "Fixes PROJ-123: Add feature"
        labels = []
        result = extract_jira_ticket_id(description, labels)
        assert result == "PROJ-123"
    
    def test_extract_jira_ticket_id_from_labels(self):
        """Test extracting ticket ID from labels."""
        description = "No ticket here"
        labels = ["bug", "PROJ-456"]
        result = extract_jira_ticket_id(description, labels)
        assert result == "PROJ-456"
    
    def test_extract_jira_ticket_id_prefers_description(self):
        """Test that description is checked before labels."""
        description = "Fixes PROJ-123"
        labels = ["PROJ-456"]
        result = extract_jira_ticket_id(description, labels)
        assert result == "PROJ-123"
    
    def test_extract_jira_ticket_id_no_match(self):
        """Test that None is returned when no ticket found."""
        description = "No ticket reference"
        labels = ["bug", "feature"]
        result = extract_jira_ticket_id(description, labels)
        assert result is None
    
    def test_extract_jira_ticket_id_empty_inputs(self):
        """Test with empty description and labels."""
        result = extract_jira_ticket_id("", [])
        assert result is None


class TestExtractConfluencePageId:
    """Tests for extract_confluence_page_id()"""
    
    def test_extract_confluence_page_id_from_description(self):
        """Test extracting page ID from PR description."""
        description = "See Confluence: 123456 for details"
        result = extract_confluence_page_id(description, None)
        assert result == "123456"
    
    def test_extract_confluence_page_id_page_id_format(self):
        """Test extracting with 'page id' format."""
        description = "Page ID: 789012"
        result = extract_confluence_page_id(description, None)
        assert result == "789012"
    
    def test_extract_confluence_page_id_case_insensitive(self):
        """Test that extraction is case insensitive."""
        description = "CONFLUENCE: 555555"
        result = extract_confluence_page_id(description, None)
        assert result == "555555"
    
    def test_extract_confluence_page_id_no_match(self):
        """Test that None is returned when no page ID found."""
        description = "No confluence reference"
        result = extract_confluence_page_id(description, None)
        assert result is None
    
    def test_extract_confluence_page_id_empty_description(self):
        """Test with empty description."""
        result = extract_confluence_page_id("", None)
        assert result is None

