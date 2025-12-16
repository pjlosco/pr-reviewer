# Code Review Agent State Machine Design

## Overview

The code review agent is implemented as a LangGraph state machine that orchestrates the review process through a series of states and transitions. The agent autonomously fetches required data using MCP tools and generates human-focused code review feedback.

## State Machine Architecture

### State Graph Structure

The agent follows a directed graph with the following states:
1. **INITIALIZE** - Entry point, validates input
2. **FETCH_PR_DETAILS** - Retrieves PR information from GitHub
3. **EXTRACT_CONTEXT_IDS** - Identifies Jira ticket and Confluence page IDs
4. **FETCH_JIRA_CONTEXT** - Retrieves acceptance criteria from Jira
5. **FETCH_CONFLUENCE_CONTEXT** - Retrieves domain context from Confluence
6. **ANALYZE_CODE** - Performs code review analysis
7. **GENERATE_REVIEW** - Generates review comments
8. **POST_REVIEW** - Posts comments to GitHub PR
9. **COMPLETE** - Final state, review complete
10. **ERROR** - Error handling state

## State Definitions

### State Schema

```python
class AgentState(TypedDict):
    pr_url: str                    # Input: PR URL from webhook
    pr_details: Optional[dict]     # PR data from GitHub MCP
    jira_ticket_id: Optional[str]   # Extracted Jira ticket ID
    confluence_page_id: Optional[str] # Extracted Confluence page ID
    jira_context: Optional[dict]    # Acceptance criteria from Jira
    confluence_context: Optional[dict] # Domain context from Confluence
    review_analysis: Optional[str]  # Analysis results
    review_comments: Optional[list] # Generated review comments
    error: Optional[str]            # Error message if any
    status: str                    # Current status
```

## State Transitions

### 1. INITIALIZE → FETCH_PR_DETAILS
- **Condition**: Always (entry point)
- **Action**: Validate PR URL format
- **Error Handling**: If invalid URL, transition to ERROR

### 2. FETCH_PR_DETAILS → EXTRACT_CONTEXT_IDS
- **Condition**: PR details successfully fetched
- **Action**: 
  - Call GitHub MCP server `get_pr_details(pr_url)`
  - Store PR diff, description, author, metadata
- **Error Handling**: 
  - Retry up to 3 times on failure
  - If all retries fail, transition to ERROR
  - If partial data, continue with available data

### 3. EXTRACT_CONTEXT_IDS → FETCH_JIRA_CONTEXT
- **Condition**: Jira ticket ID found in PR
- **Action**: 
  - Extract Jira ticket ID from PR description/labels
  - Use regex or label matching to identify ticket
- **Conditional Routing**:
  - If Jira ticket ID found → FETCH_JIRA_CONTEXT
  - If not found → FETCH_CONFLUENCE_CONTEXT (skip Jira)
  - If error → FETCH_CONFLUENCE_CONTEXT (continue without Jira)

### 4. FETCH_JIRA_CONTEXT → FETCH_CONFLUENCE_CONTEXT
- **Condition**: Jira context fetched (or skipped)
- **Action**: 
  - Call Jira MCP server `get_acceptance_criteria(jira_ticket_id)`
  - Store acceptance criteria and ticket metadata
- **Error Handling**: 
  - On failure, log warning and continue to next state
  - Don't block review if Jira is unavailable

### 5. FETCH_CONFLUENCE_CONTEXT → ANALYZE_CODE
- **Condition**: Confluence context fetched (or skipped)
- **Action**: 
  - Identify relevant Confluence pages from Jira ticket or PR metadata
  - Call Confluence MCP server `get_domain_context(confluence_page_id)`
  - Store domain context and guidelines
- **Error Handling**: 
  - On failure, log warning and continue
  - Review can proceed without Confluence context

### 6. ANALYZE_CODE → GENERATE_REVIEW
- **Condition**: Analysis complete
- **Action**: 
  - LLM analyzes code changes using:
    - PR diff and file changes
    - Jira acceptance criteria (if available)
    - Confluence domain context (if available)
    - Human-focused review criteria:
      * Logic correctness
      * Design patterns and architecture
      * Code maintainability
      * Error handling
      * Security considerations
      * Performance implications
      * Test coverage
  - Generate structured analysis
- **Error Handling**: 
  - If LLM call fails, retry with backoff
  - If analysis incomplete, proceed with partial analysis

### 7. GENERATE_REVIEW → POST_REVIEW
- **Condition**: Review comments generated
- **Action**: 
  - LLM generates review comments from analysis
  - Format comments for GitHub PR review
  - Structure comments by file/line number
- **Error Handling**: 
  - If generation fails, retry
  - Ensure at least summary comment is generated

### 8. POST_REVIEW → COMPLETE
- **Condition**: Review posted successfully
- **Action**: 
  - Post comments to GitHub PR via GitHub MCP server or API
  - Update PR status if needed
- **Error Handling**: 
  - Retry posting on failure
  - Log final status

### 9. ERROR → COMPLETE
- **Condition**: Error occurred and handled
- **Action**: 
  - Log error details
  - Return error status to Jenkins
  - Optionally post error message to PR

## Tool Calling Strategy

### Autonomous Tool Usage

The agent uses tools (MCP servers) autonomously based on its understanding of the task:

1. **Tool Selection**: Agent decides which tools to call based on:
   - Current state and available context
   - Need for additional information
   - Error recovery requirements

2. **Tool Execution Pattern**:
   ```
   Agent → Tool Call → MCP Server → External API → Response → Agent
   ```

3. **Parallel Tool Calls**: 
   - Jira and Confluence calls can be made in parallel (if both IDs available)
   - Optimize for speed when possible

4. **Tool Error Handling**:
   - Agent receives tool errors as part of tool response
   - Agent decides whether to retry, skip, or fail based on error type
   - Agent continues with available data when non-critical tools fail

## Review Workflow Logic

### Human-Focused Review Criteria

The agent focuses on issues that human reviewers would catch, excluding CI/CD concerns:

**Included:**
- Logic errors and edge cases
- Design pattern violations
- Code maintainability issues
- Security vulnerabilities
- Performance anti-patterns
- Missing error handling
- Inconsistent coding style
- Missing or inadequate tests
- Architecture concerns
- Requirements alignment (from Jira)

**Excluded:**
- Syntax errors (caught by linters)
- Build failures (caught by CI)
- Test failures (caught by CI)
- Formatting issues (caught by formatters)
- Type errors (caught by type checkers)

### Context-Aware Review

The agent tailors its review based on available context:

1. **With Jira Context**: 
   - Validates code against acceptance criteria
   - Checks for requirement implementation
   - Verifies ticket-related changes

2. **With Confluence Context**:
   - Applies domain-specific guidelines
   - Checks against architectural patterns
   - Validates naming conventions and standards

3. **Without Context**:
   - Performs general code review
   - Focuses on code quality and best practices
   - Notes missing context in review

## State Machine Implementation Details

### LangGraph Configuration

```python
from langgraph.graph import StateGraph, END

# Create state graph
workflow = StateGraph(AgentState)

# Add nodes (states)
workflow.add_node("initialize", initialize_node)
workflow.add_node("fetch_pr_details", fetch_pr_details_node)
workflow.add_node("extract_context_ids", extract_context_ids_node)
workflow.add_node("fetch_jira_context", fetch_jira_context_node)
workflow.add_node("fetch_confluence_context", fetch_confluence_context_node)
workflow.add_node("analyze_code", analyze_code_node)
workflow.add_node("generate_review", generate_review_node)
workflow.add_node("post_review", post_review_node)
workflow.add_node("error", error_node)

# Define edges (transitions)
workflow.set_entry_point("initialize")
workflow.add_edge("initialize", "fetch_pr_details")
workflow.add_conditional_edges(
    "fetch_pr_details",
    should_continue,
    {
        "continue": "extract_context_ids",
        "error": "error"
    }
)
# ... additional edges
workflow.add_edge("post_review", END)
workflow.add_edge("error", END)
```

### Conditional Routing

The state machine uses conditional edges for:
- Error handling and recovery
- Optional context fetching (Jira/Confluence)
- Parallel execution when possible
- Skipping states when data unavailable

## Error Recovery

### Retry Logic
- Implemented at state level, not graph level
- Each state handles its own retries
- Exponential backoff for transient failures

### Graceful Degradation
- Agent continues with available data
- Missing context is noted but doesn't block review
- Partial reviews are better than no reviews

### Error States
- Errors are captured in state
- Error state logs and reports issues
- Agent attempts to provide useful feedback even on failure

