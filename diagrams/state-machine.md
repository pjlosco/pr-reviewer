# State Machine Workflow Diagram

## Agent State Flow

```mermaid
stateDiagram-v2
    [*] --> INITIALIZE
    
    INITIALIZE --> FETCH_PR_DETAILS: Valid PR URL
    INITIALIZE --> ERROR: Invalid PR URL
    
    FETCH_PR_DETAILS --> EXTRACT_CONTEXT_IDS: Success (should_continue)
    FETCH_PR_DETAILS --> ERROR: Failed (should_continue)
    
    EXTRACT_CONTEXT_IDS --> FETCH_JIRA_CONTEXT: Jira ID Found (should_fetch_jira)
    EXTRACT_CONTEXT_IDS --> FETCH_CONFLUENCE_CONTEXT: No Jira ID (should_fetch_jira)
    
    FETCH_JIRA_CONTEXT --> FETCH_CONFLUENCE_CONTEXT: Always Continue
    FETCH_CONFLUENCE_CONTEXT --> ANALYZE_CODE: Always Continue
    
    ANALYZE_CODE --> GENERATE_REVIEW: Analysis Complete
    ANALYZE_CODE --> ERROR: LLM Failure
    
    GENERATE_REVIEW --> POST_REVIEW: Comments Generated
    GENERATE_REVIEW --> ERROR: Generation Failed
    
    POST_REVIEW --> COMPLETE: Posted Successfully
    POST_REVIEW --> ERROR: Post Failed
    
    ERROR --> [*]: Error Handled
    
    COMPLETE --> [*]
```

## State Descriptions

- **INITIALIZE**: Entry point, validates PR URL format
- **FETCH_PR_DETAILS**: Calls GitHub MCP `get_pr_details()` tool
- **EXTRACT_CONTEXT_IDS**: Parses PR description/labels for Jira ticket IDs and Confluence page IDs
- **FETCH_JIRA_CONTEXT**: Calls Jira MCP `get_acceptance_criteria()` tool (optional, graceful degradation)
- **FETCH_CONFLUENCE_CONTEXT**: Calls Confluence MCP with hybrid approach:
  - If page ID: `get_domain_context()` (direct lookup)
  - If no page ID: `search_documentation_semantic()` (ChromaDB) → fallback to keyword search
  - Optional, graceful degradation
- **ANALYZE_CODE**: LLM analyzes code changes with all available context (PR diff, Jira criteria, Confluence docs)
- **GENERATE_REVIEW**: LLM generates structured review comments in JSON format
- **POST_REVIEW**: Calls GitHub MCP `post_review_comments()` tool to post comments
- **ERROR**: Handles errors gracefully, logs details
- **COMPLETE**: Final state, review posted successfully

## Conditional Routing

- **should_continue()**: Routes after `FETCH_PR_DETAILS` based on success/failure
- **should_fetch_jira()**: Routes after `EXTRACT_CONTEXT_IDS` based on Jira ticket ID presence

## Graceful Degradation

- Jira/Confluence context fetching failures don't block the review
- Agent continues with available data (PR details always required)
- Missing context is noted but review proceeds

