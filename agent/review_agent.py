"""
Code Review Agent

This module contains the main LangGraph agent that orchestrates the code review process.
The agent uses a state machine to:
1. Fetch PR details from GitHub
2. Extract context IDs (Jira tickets, Confluence pages)
3. Gather acceptance criteria from Jira
4. Retrieve domain context from Confluence
5. Analyze code changes with LLM
6. Generate and post review comments
"""

import os
import re
import logging
from typing import Optional, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

# Import MCP server tools
from mcp_servers.github_server import (
    _get_pr_details_impl,
    _post_review_comments_impl,
    _submit_review_impl,
)
from mcp_servers.jira_server import (
    _get_acceptance_criteria_impl,
)
from mcp_servers.confluence_server import (
    _get_domain_context_impl,
    _search_documentation_semantic_impl,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================

class AgentState(TypedDict):
    """
    State schema for the LangGraph agent.
    
    This defines all the data that flows through the state machine,
    allowing each node to read and update the state as needed.
    """
    pr_url: str                    # Input: PR URL from trigger
    pr_details: Optional[dict]     # PR data from GitHub MCP
    jira_ticket_id: Optional[str]   # Extracted Jira ticket ID
    confluence_page_id: Optional[str]  # Extracted Confluence page ID
    jira_context: Optional[dict]    # Acceptance criteria from Jira
    confluence_context: Optional[dict]  # Domain context from Confluence
    review_analysis: Optional[str]  # Analysis results from LLM
    review_comments: Optional[list]  # Generated review comments
    review_decision: Optional[str]   # Review decision: APPROVE, REQUEST_CHANGES, or COMMENT
    review_body: Optional[str]       # Review body text for official review
    error: Optional[str]            # Error message if any
    status: str                    # Current status


# ============================================================================
# Helper Functions
# ============================================================================

def get_llm_client() -> BaseChatModel:
    """
    Initialize and return an LLM client based on environment variables.
    
    Supports OpenAI, Anthropic, and Google providers.
    
    Returns:
        Configured LLM client
        
    Raises:
        ValueError: If provider is invalid or API key is missing
        ImportError: If required library is not installed
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for OpenAI. "
                "Install it with: pip install langchain-openai"
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
    
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is required for Anthropic. "
                "Install it with: pip install langchain-anthropic"
            )
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)
    
    elif provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is required for Google. "
                "Install it with: pip install langchain-google-genai"
            )
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=api_key)
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use 'openai', 'anthropic', or 'google'")


def extract_jira_ticket_id(pr_description: str, labels: list[str]) -> Optional[str]:
    """
    Extract Jira ticket ID from PR description or labels.
    
    Looks for patterns like "PROJ-123" or "JIRA-456" in the description
    or labels.
    
    Args:
        pr_description: PR description text
        labels: List of PR labels
        
    Returns:
        Jira ticket ID if found, None otherwise
    """
    # Pattern: PROJECT-123 or JIRA-456 (uppercase letters, dash, numbers)
    pattern = r'([A-Z]+-\d+)'
    
    # Search in description
    matches = re.findall(pattern, pr_description or "")
    if matches:
        return matches[0]  # Return first match
    
    # Search in labels
    for label in labels:
        matches = re.findall(pattern, label)
        if matches:
            return matches[0]
    
    return None


def extract_confluence_page_id(pr_description: str, jira_context: Optional[dict]) -> Optional[str]:
    """
    Extract Confluence page ID from PR description or Jira context.
    
    Looks for Confluence page references in the PR description or
    extracts from related Jira ticket metadata.
    
    Args:
        pr_description: PR description text
        jira_context: Jira ticket context (may contain Confluence references)
        
    Returns:
        Confluence page ID if found, None otherwise
    """
    # Pattern: confluence page ID (numeric)
    # Could be in format: "Confluence: 123456" or "Page ID: 123456"
    patterns = [
        r'confluence[:\s]+(\d+)',
        r'page[:\s]+id[:\s]+(\d+)',
        r'page[:\s]+(\d+)',
    ]
    
    text = (pr_description or "").lower()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]
    
    # Could also extract from Jira context if it contains Confluence links
    # This is a placeholder - real implementation would parse Jira ticket
    # for Confluence page references
    
    return None


# ============================================================================
# State Node Functions
# ============================================================================

def initialize_node(state: AgentState) -> AgentState:
    """
    Initialize the agent and validate the PR URL.
    
    This is the entry point of the state machine. It validates the input
    PR URL format and prepares the state for the review process.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with validated PR URL and initial status
    """
    pr_url = state.get("pr_url", "")
    
    # Validate PR URL format
    if not pr_url:
        return {
            **state,
            "error": "PR URL is required",
            "status": "error"
        }
    
    # Basic URL validation
    if not pr_url.startswith("https://github.com/") or "/pull/" not in pr_url:
        return {
            **state,
            "error": f"Invalid PR URL format: {pr_url}",
            "status": "error"
        }
    
    logger.info(f"Initializing review for PR: {pr_url}")
    
    return {
        **state,
        "status": "initialized"
    }


def fetch_pr_details_node(state: AgentState) -> AgentState:
    """
    Fetch PR details from GitHub using the GitHub MCP server.
    
    This node calls the GitHub MCP server to retrieve:
    - PR diff
    - PR description
    - Author information
    - Files changed
    - Commit history
    - Labels and reviewers
    
    Args:
        state: Current agent state with PR URL
        
    Returns:
        Updated state with PR details
    """
    pr_url = state.get("pr_url", "")
    
    try:
        logger.info(f"Fetching PR details for: {pr_url}")
        pr_details = _get_pr_details_impl(pr_url)
        
        return {
            **state,
            "pr_details": pr_details,
            "status": "pr_details_fetched"
        }
    except Exception as e:
        logger.error(f"Failed to fetch PR details: {e}")
        return {
            **state,
            "error": f"Failed to fetch PR details: {str(e)}",
            "status": "error"
        }


def extract_context_ids_node(state: AgentState) -> AgentState:
    """
    Extract Jira ticket IDs and Confluence page IDs from PR metadata.
    
    This node parses the PR description, labels, and other metadata to
    identify related Jira tickets and Confluence pages that provide
    context for the code review.
    
    Args:
        state: Current agent state with PR details
        
    Returns:
        Updated state with extracted context IDs
    """
    pr_details = state.get("pr_details")
    if not pr_details:
        logger.warning("No PR details available for context extraction")
        return {
            **state,
            "status": "context_ids_extracted"
        }
    
    description = pr_details.get("description", "")
    labels = pr_details.get("labels", [])
    
    # Extract Jira ticket ID
    jira_ticket_id = extract_jira_ticket_id(description, labels)
    if jira_ticket_id:
        logger.info(f"Found Jira ticket: {jira_ticket_id}")
    
    # Extract Confluence page ID
    confluence_page_id = extract_confluence_page_id(description, None)
    if confluence_page_id:
        logger.info(f"Found Confluence page: {confluence_page_id}")
    
    return {
        **state,
        "jira_ticket_id": jira_ticket_id,
        "confluence_page_id": confluence_page_id,
        "status": "context_ids_extracted"
    }


def fetch_jira_context_node(state: AgentState) -> AgentState:
    """
    Fetch acceptance criteria and ticket context from Jira.
    
    This node calls the Jira MCP server to retrieve acceptance criteria
    and other ticket information. If no ticket ID is found or the call
    fails, it continues without blocking the review.
    
    Args:
        state: Current agent state with Jira ticket ID (if available)
        
    Returns:
        Updated state with Jira context (or None if unavailable)
    """
    jira_ticket_id = state.get("jira_ticket_id")
    
    if not jira_ticket_id:
        logger.info("No Jira ticket ID found, skipping Jira context fetch")
        return {
            **state,
            "status": "jira_context_fetched"
        }
    
    try:
        logger.info(f"Fetching Jira context for ticket: {jira_ticket_id}")
        jira_context = _get_acceptance_criteria_impl(jira_ticket_id)
        
        return {
            **state,
            "jira_context": jira_context,
            "status": "jira_context_fetched"
        }
    except Exception as e:
        logger.warning(f"Failed to fetch Jira context (continuing without it): {e}")
        # Don't block review if Jira fetch fails
        return {
            **state,
            "jira_context": None,
            "status": "jira_context_fetched"
        }


def fetch_confluence_context_node(state: AgentState) -> AgentState:
    """
    Fetch domain context and documentation from Confluence.
    
    This node calls the Confluence MCP server to retrieve domain-specific
    documentation and guidelines. It uses a hybrid approach:
    1. If page ID is provided → direct lookup
    2. If no page ID → semantic search via ChromaDB (if available)
    3. Fallback to keyword search if ChromaDB not available
    
    If no page ID is found or the call fails, it continues without blocking the review.
    
    Args:
        state: Current agent state with Confluence page ID (if available)
        
    Returns:
        Updated state with Confluence context (or None if unavailable)
    """
    confluence_page_id = state.get("confluence_page_id")
    pr_details = state.get("pr_details")
    
    # If page ID is provided, use direct lookup (existing behavior)
    if confluence_page_id:
        try:
            logger.info(f"Fetching Confluence context for page: {confluence_page_id}")
            confluence_context = _get_domain_context_impl(confluence_page_id)
            
            return {
                **state,
                "confluence_context": confluence_context,
                "status": "confluence_context_fetched"
            }
        except Exception as e:
            logger.warning(f"Failed to fetch Confluence context (continuing without it): {e}")
            return {
                **state,
                "confluence_context": None,
                "status": "confluence_context_fetched"
            }
    
    # No page ID - try semantic search via ChromaDB
    logger.info("No Confluence page ID found, attempting semantic search...")
    
    try:
        # Build search query from PR context
        if pr_details:
            pr_title = pr_details.get("title", "")
            pr_description = pr_details.get("description", "")
            files_changed = pr_details.get("files", [])
            
            # Extract keywords from PR for semantic search
            search_query = f"{pr_title} {pr_description}"
            if files_changed:
                # Add file names as context
                file_names = " ".join([f.get("path", "").split("/")[-1] for f in files_changed[:5]])
                search_query += f" {file_names}"
        else:
            search_query = "code review documentation guidelines"
        
        # Try semantic search
        semantic_results = _search_documentation_semantic_impl(
            query=search_query,
            limit=3,  # Get top 3 most relevant pages
            min_similarity=0.7
        )
        
        if semantic_results:
            # Use the most relevant page
            best_match = semantic_results[0]
            logger.info(f"Found relevant Confluence page via semantic search: {best_match.get('title')} (similarity: {best_match.get('similarity_score', 0)})")
            
            # Fetch full page content using the page ID from semantic search
            page_id = best_match.get("id")
            if page_id:
                try:
                    confluence_context = _get_domain_context_impl(page_id)
                    # Add semantic search metadata
                    confluence_context["_semantic_search"] = {
                        "query": search_query,
                        "similarity_score": best_match.get("similarity_score"),
                        "all_results": semantic_results
                    }
                    
                    return {
                        **state,
                        "confluence_context": confluence_context,
                        "status": "confluence_context_fetched"
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch full page content for {page_id}: {e}")
        
        # Fallback to keyword search if semantic search didn't find anything
        logger.info("Semantic search found no results, trying keyword search...")
        from mcp_servers.confluence_server import _search_documentation_impl
        keyword_results = _search_documentation_impl(search_query, limit=3)
        
        if keyword_results:
            # Use first keyword match
            best_match = keyword_results[0]
            page_id = best_match.get("id")
            if page_id:
                try:
                    confluence_context = _get_domain_context_impl(page_id)
                    confluence_context["_keyword_search"] = True
                    return {
                        **state,
                        "confluence_context": confluence_context,
                        "status": "confluence_context_fetched"
                    }
                except Exception:
                    pass
        
        # No results from either method
        logger.info("No Confluence context found via search, continuing without it")
        return {
            **state,
            "confluence_context": None,
            "status": "confluence_context_fetched"
        }
        
    except Exception as e:
        logger.warning(f"Failed to search Confluence documentation (continuing without it): {e}")
        # Don't block review if search fails
        return {
            **state,
            "confluence_context": None,
            "status": "confluence_context_fetched"
        }


def analyze_code_node(state: AgentState) -> AgentState:
    """
    Analyze code changes using LLM with all available context.
    
    This node uses the LLM to analyze the code changes against:
    - PR diff and file changes
    - Jira acceptance criteria (if available)
    - Confluence domain context (if available)
    - Human-focused review criteria (logic, design, maintainability)
    
    Args:
        state: Current agent state with PR details and context
        
    Returns:
        Updated state with analysis results
    """
    pr_details = state.get("pr_details")
    if not pr_details:
        logger.error("No PR details available for analysis")
        return {
            **state,
            "error": "No PR details available",
            "status": "error"
        }
    
    try:
        llm = get_llm_client()
        
        # Build analysis prompt
        pr_diff = pr_details.get("diff", "")
        pr_description = pr_details.get("description", "")
        files_changed = pr_details.get("files", [])
        
        # Build context sections
        jira_context = state.get("jira_context")
        confluence_context = state.get("confluence_context")
        
        prompt_parts = [
            "You are an expert code reviewer. Analyze the following pull request changes.",
            "",
            f"PR Title: {pr_details.get('title', 'N/A')}",
            f"PR Description: {pr_description}",
            "",
            f"Files Changed: {len(files_changed)}",
        ]
        
        if jira_context:
            acceptance_criteria = jira_context.get("acceptanceCriteria", [])
            if acceptance_criteria:
                prompt_parts.extend([
                    "",
                    "Jira Acceptance Criteria:",
                    *[f"- {ac}" for ac in acceptance_criteria]
                ])
        
        if confluence_context:
            confluence_title = confluence_context.get("title", "")
            prompt_parts.extend([
                "",
                f"Domain Context (Confluence): {confluence_title}",
                "Use this context to understand domain-specific guidelines and patterns."
            ])
        
        prompt_parts.extend([
            "",
            "Code Changes (Diff):",
            pr_diff[:50000],  # Limit diff size to avoid token limits
            "",
            "Focus on human-reviewer concerns:",
            "- Logic errors and edge cases",
            "- Design pattern violations",
            "- Code maintainability",
            "- Security vulnerabilities",
            "- Performance issues",
            "- Missing error handling",
            "- Architecture concerns",
            "",
            "Do NOT focus on:",
            "- Syntax errors (caught by linters)",
            "- Formatting (caught by formatters)",
            "- Type errors (caught by type checkers)",
            "",
            "Provide a comprehensive analysis of the code changes."
        ])
        
        prompt = "\n".join(prompt_parts)
        
        logger.info("Calling LLM for code analysis...")
        response = llm.invoke([HumanMessage(content=prompt)])
        analysis = response.content if hasattr(response, 'content') else str(response)
        
        return {
            **state,
            "review_analysis": analysis,
            "status": "code_analyzed"
        }
    except Exception as e:
        logger.error(f"Failed to analyze code: {e}")
        return {
            **state,
            "error": f"Failed to analyze code: {str(e)}",
            "status": "error"
        }


def generate_review_node(state: AgentState) -> AgentState:
    """
    Generate review comments from the analysis results.
    
    This node uses the LLM to generate structured review comments
    from the analysis. Comments are formatted for GitHub PR review
    with file paths and line numbers.
    
    Args:
        state: Current agent state with analysis results
        
    Returns:
        Updated state with generated review comments
    """
    analysis = state.get("review_analysis")
    pr_details = state.get("pr_details")
    
    if not analysis:
        logger.error("No analysis available for review generation")
        return {
            **state,
            "error": "No analysis available",
            "status": "error"
        }
    
    if not pr_details:
        logger.error("No PR details available")
        return {
            **state,
            "error": "No PR details available",
            "status": "error"
        }
    
    try:
        llm = get_llm_client()
        
        files_changed = pr_details.get("files", [])
        
        prompt = f"""Based on the following code analysis, generate structured review comments for the GitHub PR.

Analysis:
{analysis}

Files Changed:
{chr(10).join([f"- {f.get('path', '')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})" for f in files_changed[:20]])}

Generate review comments in the following JSON format:
{{
  "summary": "Overall review summary",
  "review_decision": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "review_body": "Detailed review summary to include in the official review",
  "comments": [
    {{
      "path": "file/path.py",
      "line": 42,
      "body": "Comment text here"
    }}
  ]
}}

Review decision guidelines:
- "APPROVE": Code is good quality, meets requirements, no critical issues
- "REQUEST_CHANGES": Critical issues found that must be fixed (bugs, security, major design flaws)
- "COMMENT": Minor issues or suggestions, but code is acceptable

For each comment:
- Use the file path from the files changed list
- Specify line number if the comment is about a specific line (use null for general file comments)
- Make comments constructive and actionable
- Focus on the most important issues first

Return ONLY valid JSON, no markdown formatting."""

        logger.info("Generating review comments...")
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response (handle markdown code blocks if present)
        import json
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            review_data = json.loads(response_text)
            comments = review_data.get("comments", [])
            review_decision = review_data.get("review_decision", "COMMENT")
            review_body = review_data.get("review_body", review_data.get("summary", ""))
            
            # Format comments for GitHub API
            formatted_comments = []
            for comment in comments:
                formatted_comments.append({
                    "path": comment.get("path"),
                    "line": comment.get("line"),
                    "body": comment.get("body", "")
                })
            
            return {
                **state,
                "review_comments": formatted_comments,
                "review_decision": review_decision,
                "review_body": review_body,
                "status": "review_generated"
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response, creating single summary comment: {e}")
            # Fallback: create a single summary comment
            return {
                **state,
                "review_comments": [{
                    "body": f"Code Review Summary:\n\n{analysis}"
                }],
                "status": "review_generated"
            }
    except Exception as e:
        logger.error(f"Failed to generate review: {e}")
        return {
            **state,
            "error": f"Failed to generate review: {str(e)}",
            "status": "error"
        }


def post_review_node(state: AgentState) -> AgentState:
    """
    Post review comments and submit official review to the GitHub PR.
    
    This node posts the generated review comments and submits an official
    review (APPROVE, REQUEST_CHANGES, or COMMENT) to the GitHub PR.
    
    Args:
        state: Current agent state with review comments and decision
        
    Returns:
        Updated state with posting status
    """
    pr_url = state.get("pr_url", "")
    review_comments = state.get("review_comments", [])
    review_decision = state.get("review_decision", "COMMENT")
    review_body = state.get("review_body", "")
    
    try:
        # Submit official review with comments
        logger.info(f"Submitting {review_decision} review to PR: {pr_url}")
        
        # Validate review decision
        if review_decision not in ["APPROVE", "REQUEST_CHANGES", "COMMENT"]:
            logger.warning(f"Invalid review decision '{review_decision}', defaulting to COMMENT")
            review_decision = "COMMENT"
        
        # Format comments for submit_review (needs path, line, body)
        formatted_comments = []
        for comment in review_comments:
            if comment.get("path") and comment.get("line"):
                formatted_comments.append({
                    "path": comment.get("path"),
                    "line": comment.get("line"),
                    "body": comment.get("body", "")
                })
        
        # Submit the review (will handle GitHub Actions APPROVE limitation)
        try:
            review_result = _submit_review_impl(
                pr_url=pr_url,
                event=review_decision,
                body=review_body or f"Code review completed. {len(review_comments)} comment(s).",
                comments=formatted_comments if formatted_comments else None
            )
            
            logger.info(f"Review submitted: {review_result.get('state', 'unknown')}")
        except Exception as review_error:
            # If review submission fails (e.g., GitHub Actions approval), try to post comments
            error_msg = str(review_error)
            if "not permitted to approve" in error_msg.lower() or "422" in error_msg:
                logger.warning("Cannot submit official review (likely GitHub Actions limitation), posting comments instead")
                if review_comments:
                    _post_review_comments_impl(pr_url, review_comments)
                # Don't fail the workflow, just log the issue
                return {
                    **state,
                    "status": "complete"
                }
            else:
                raise
        
        # If there are comments without line numbers, post them separately
        general_comments = [
            c for c in review_comments 
            if not (c.get("path") and c.get("line"))
        ]
        
        if general_comments:
            logger.info(f"Posting {len(general_comments)} general comments separately")
            try:
                _post_review_comments_impl(pr_url, general_comments)
            except Exception as e:
                logger.warning(f"Failed to post some general comments: {e}")
        
        return {
            **state,
            "status": "complete"
        }
    except Exception as e:
        logger.error(f"Failed to submit review: {e}")
        # Fallback: try to post comments without official review
        if review_comments:
            try:
                logger.info("Falling back to posting comments without official review")
                _post_review_comments_impl(pr_url, review_comments)
                # Don't fail if we can at least post comments
                return {
                    **state,
                    "status": "complete"
                }
            except Exception as fallback_error:
                logger.error(f"Failed to post comments as fallback: {fallback_error}")
        
        return {
            **state,
            "error": f"Failed to submit review: {str(e)}",
            "status": "error"
        }


def error_node(state: AgentState) -> AgentState:
    """
    Handle errors and log failure information.
    
    This node is called when an error occurs in the state machine.
    It logs the error and prepares the state for graceful failure.
    
    Args:
        state: Current agent state with error information
        
    Returns:
        Updated state with error logged
    """
    error = state.get("error", "Unknown error")
    logger.error(f"Agent error: {error}")
    
    # Optionally post error to PR (could be enabled via config)
    # For now, just log it
    
    return {
        **state,
        "status": "error"
    }


# ============================================================================
# Conditional Routing Functions
# ============================================================================

def should_continue(state: AgentState) -> str:
    """
    Determine the next state after fetching PR details.
    
    This function checks if PR details were successfully fetched
    and routes to either continue the workflow or handle errors.
    
    Args:
        state: Current agent state
        
    Returns:
        "continue" if successful, "error" if failed
    """
    if state.get("error"):
        return "error"
    
    pr_details = state.get("pr_details")
    if pr_details and isinstance(pr_details, dict):
        return "continue"
    
    return "error"


def should_fetch_jira(state: AgentState) -> str:
    """
    Determine if Jira context should be fetched.
    
    This function checks if a Jira ticket ID was extracted and
    routes to fetch Jira context or skip to Confluence.
    
    Args:
        state: Current agent state
        
    Returns:
        "fetch_jira" if ticket ID exists, "skip_jira" otherwise
    """
    jira_ticket_id = state.get("jira_ticket_id")
    if jira_ticket_id:
        return "fetch_jira"
    return "skip_jira"


# ============================================================================
# Main Agent Function
# ============================================================================

def run_review_agent(pr_url: str, verbose: bool = False) -> None:
    """
    Main function to run the code review agent.
    
    This function creates and executes the LangGraph state machine
    to perform a complete code review of the specified PR.
    
    Args:
        pr_url: URL of the pull request to review
        verbose: Enable verbose logging
        
    Raises:
        Exception: If the review process fails critically
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Starting code review for PR: {pr_url}")
    
    # Create initial state
    initial_state: AgentState = {
        "pr_url": pr_url,
        "pr_details": None,
        "jira_ticket_id": None,
        "confluence_page_id": None,
        "jira_context": None,
        "confluence_context": None,
        "review_analysis": None,
        "review_comments": None,
        "error": None,
        "status": "initializing"
    }
    
    try:
        # Create and compile graph
        graph = create_agent_graph()
        
        # Execute the graph
        final_state = graph.invoke(initial_state)
        
        # Check final status
        status = final_state.get("status", "unknown")
        if status == "error":
            error = final_state.get("error", "Unknown error")
            logger.error(f"Review failed: {error}")
            raise Exception(f"Code review failed: {error}")
        elif status == "complete":
            logger.info("Code review completed successfully")
        else:
            logger.warning(f"Review completed with status: {status}")
            
    except Exception as e:
        logger.error(f"Critical error during review: {e}")
        raise


def create_agent_graph() -> StateGraph:
    """
    Create and configure the LangGraph state machine.
    
    This function builds the complete state graph with all nodes,
    edges, and conditional routing logic.
    
    Returns:
        Configured StateGraph ready to execute
    """
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("fetch_pr_details", fetch_pr_details_node)
    workflow.add_node("extract_context_ids", extract_context_ids_node)
    workflow.add_node("fetch_jira_context", fetch_jira_context_node)
    workflow.add_node("fetch_confluence_context", fetch_confluence_context_node)
    workflow.add_node("analyze_code", analyze_code_node)
    workflow.add_node("generate_review", generate_review_node)
    workflow.add_node("post_review", post_review_node)
    workflow.add_node("error", error_node)
    
    # Define edges
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "fetch_pr_details")
    
    # Conditional: check if PR details fetched successfully
    workflow.add_conditional_edges(
        "fetch_pr_details",
        should_continue,
        {
            "continue": "extract_context_ids",
            "error": "error"
        }
    )
    
    # Conditional: fetch Jira or skip to Confluence
    workflow.add_conditional_edges(
        "extract_context_ids",
        should_fetch_jira,
        {
            "fetch_jira": "fetch_jira_context",
            "skip_jira": "fetch_confluence_context"
        }
    )
    
    # After Jira, always go to Confluence
    workflow.add_edge("fetch_jira_context", "fetch_confluence_context")
    workflow.add_edge("fetch_confluence_context", "analyze_code")
    workflow.add_edge("analyze_code", "generate_review")
    workflow.add_edge("generate_review", "post_review")
    workflow.add_edge("post_review", END)
    workflow.add_edge("error", END)
    
    return workflow.compile()

