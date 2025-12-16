# Data Flow Sequence Diagram

## PR Review Execution Flow

```mermaid
sequenceDiagram
    participant GH as GitHub
    participant GA as GitHub Actions<br/>Workflow
    participant AG as Review Agent<br/>(LangGraph)
    participant GH_MCP as GitHub MCP<br/>(FastMCP + PyGithub)
    participant JIRA_MCP as Jira MCP<br/>(FastMCP + jira library)
    participant CONF_MCP as Confluence MCP<br/>(FastMCP + LangChain)
    participant CHROMADB as ChromaDB<br/>(Optional - Semantic Search)
    participant LLM as LLM Service<br/>(OpenAI/Anthropic/Google)
    participant LS as LangSmith<br/>(Optional)
    
    GH->>GA: PR Event Triggered<br/>(opened, synchronize, reopened)
    GA->>AG: Execute Agent<br/>(PR URL from github.event)
    
    Note over AG: State: INITIALIZE
    AG->>AG: Validate PR URL
    
    Note over AG: State: FETCH_PR_DETAILS
    AG->>GH_MCP: get_pr_details(pr_url)
    GH_MCP->>GH: GitHub API: Get PR
    GH-->>GH_MCP: PR Data (diff, files, commits, labels)
    GH_MCP-->>AG: PR Details Dict
    
    Note over AG: State: EXTRACT_CONTEXT_IDS
    AG->>AG: Extract Jira Ticket ID<br/>(regex: PROJECT-123)
    AG->>AG: Extract Confluence Page ID<br/>(regex: page ID patterns)
    
    alt Jira Ticket ID Found
        Note over AG: State: FETCH_JIRA_CONTEXT
        AG->>JIRA_MCP: get_acceptance_criteria(ticket_id)
        alt Real API Mode
            JIRA_MCP->>JIRA_API: Jira API: Get Issue
            JIRA_API-->>JIRA_MCP: Ticket Data
        else Stub Mode
            JIRA_MCP->>JIRA_MCP: Load from Stub Data
        end
        JIRA_MCP-->>AG: Acceptance Criteria + Ticket Info
    else No Jira ID
        Note over AG: Skip Jira Context
    end
    
    alt Confluence Page ID Found
        Note over AG: State: FETCH_CONFLUENCE_CONTEXT
        AG->>CONF_MCP: get_domain_context(page_id)
        alt Real API Mode
            CONF_MCP->>CONF_API: Confluence API: Get Page<br/>(via LangChain ConfluenceLoader)
            CONF_API-->>CONF_MCP: Page Content
        else Stub Mode
            CONF_MCP->>CONF_MCP: Load from Stub Data
        end
        CONF_MCP-->>AG: Domain Context + Documentation
    else No Confluence ID
        Note over AG: State: FETCH_CONFLUENCE_CONTEXT<br/>Attempt Semantic Search
        AG->>CONF_MCP: search_documentation_semantic(query)
        alt ChromaDB Available
            CONF_MCP->>CHROMADB: Semantic Search<br/>(Vector Similarity)
            CHROMADB-->>CONF_MCP: Top Results<br/>(with similarity scores)
            CONF_MCP->>CONF_API: Get Full Page Content<br/>(for best match)
            CONF_API-->>CONF_MCP: Page Content
            CONF_MCP-->>AG: Domain Context<br/>(+ semantic metadata)
        else ChromaDB Not Available
            CONF_MCP->>CONF_MCP: Fallback to Keyword Search
            CONF_MCP->>CONF_API: Keyword Search (CQL)
            CONF_API-->>CONF_MCP: Search Results
            CONF_MCP-->>AG: Domain Context<br/>(from keyword match)
        end
    end
    
    Note over AG: State: ANALYZE_CODE
    AG->>LLM: Analyze Code Changes<br/>(Prompt: PR diff + Jira + Confluence)
    AG->>LS: Log Trace (if enabled)
    LLM-->>AG: Code Analysis Results
    
    Note over AG: State: GENERATE_REVIEW
    AG->>LLM: Generate Review Comments<br/>(Prompt: Analysis → JSON comments)
    AG->>LS: Log Trace (if enabled)
    LLM-->>AG: Structured Review Comments<br/>(JSON: path, line, body)
    
    Note over AG: State: POST_REVIEW
    AG->>GH_MCP: post_review_comments(comments)
    GH_MCP->>GH: GitHub API: Post Comments
    GH-->>GH_MCP: Comment IDs
    GH_MCP-->>AG: Posting Results
    
    Note over AG: State: COMPLETE
    AG->>GA: Review Complete
    GA->>GH: Workflow Status: Success
```

## Error Handling Flow

```mermaid
sequenceDiagram
    participant AG as Review Agent
    participant MCP as MCP Server
    participant API as External API
    
    AG->>MCP: Tool Call (e.g., get_pr_details)
    MCP->>API: API Request
    
    alt Transient Error (Network, Rate Limit)
        API-->>MCP: Error Response<br/>(RateLimitExceededException)
        MCP->>MCP: handle_github_exception()<br/>Extract reset time
        MCP-->>AG: Error with Details
        AG->>AG: Log Warning
        AG->>AG: Route to ERROR State
        AG->>AG: Error Node: Log & Continue
    else Authentication Error
        API-->>MCP: Auth Error<br/>(BadCredentialsException)
        MCP->>MCP: handle_github_exception()
        MCP-->>AG: Auth Error
        AG->>AG: Log Error, Route to ERROR
        AG->>AG: Error Node: Log & Exit
    else Resource Not Found
        API-->>MCP: Not Found<br/>(UnknownObjectException)
        MCP->>MCP: handle_github_exception()
        MCP-->>AG: Not Found Error
        AG->>AG: Log Warning
        AG->>AG: Route to ERROR State
    else Jira/Confluence Error (Non-Critical)
        API-->>MCP: Error Response
        MCP-->>AG: Error
        AG->>AG: Log Warning
        AG->>AG: Continue Without Context<br/>(Graceful Degradation)
        AG->>AG: Proceed to Next State
    end
```

## Key Implementation Details

### MCP Server Error Handling
- **GitHub MCP**: Uses `handle_github_exception()` for detailed error messages
- **Jira MCP**: Graceful fallback to stub data if real API fails
- **Confluence MCP**: Graceful fallback to stub data if real API fails

### Agent Error Handling
- **Critical Errors** (PR fetch failure): Route to ERROR state, exit
- **Non-Critical Errors** (Jira/Confluence): Log warning, continue with available data
- **LLM Errors**: Retry logic, fallback to error state if persistent

### Graceful Degradation Strategy
- PR details: **Required** - failure blocks review
- Jira context: **Optional** - failure doesn't block review
- Confluence context: **Optional** - failure doesn't block review
- Review generation: **Required** - failure blocks posting

