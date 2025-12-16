# Code Review Agent Architecture

## System Overview

This document describes the architecture of an AI-powered code review agent designed to operate within an enterprise environment. The agent automatically reviews pull requests (PRs) in GitHub, focusing on issues that human reviewers would typically catch, rather than those already handled by CI/CD pipelines.

The system can be triggered through various pipeline options (GitHub Actions, Jenkins webhooks, GitHub Apps, etc.) when PRs are updated. The agent leverages Model Context Protocol (MCP) servers to provide autonomous data-fetching capabilities. The agent incorporates context from Jira (acceptance criteria) and Confluence (domain knowledge) to tailor its review strategy.

**Note**: While the original design specified Jenkins, the agent is trigger-agnostic and can run in GitHub Actions (recommended for simplicity), as a GitHub App, or in other CI/CD environments. See `pipeline-options.md` for detailed comparison of trigger mechanisms.

## Core Components

### 1. Trigger Mechanism (Pipeline-Specific)
The agent can be triggered through various mechanisms:

**Option A: GitHub Actions (Recommended)**
- **Purpose**: Native GitHub integration via workflow
- **Input**: PR URL from GitHub Actions context (`github.event.pull_request.html_url`)
- **Trigger**: PR events (opened, synchronize, reopened)
- **Advantages**: Simple setup, no webhook configuration, built-in secrets

**Option B: Jenkins + Webhook**
- **Purpose**: Receives GitHub webhook notifications when PRs are updated
- **Input**: PR URL from webhook payload
- **Output**: Triggers the review agent with PR URL
- **Responsibilities**:
  - Validate webhook payload
  - Extract PR URL
  - Queue/trigger agent execution
  - Handle webhook authentication

**Option C: GitHub App**
- **Purpose**: GitHub App receives webhook events
- **Input**: PR URL from webhook payload
- **Advantages**: Multi-repo support, fine-grained permissions

See `pipeline-options.md` for detailed comparison of all trigger options.

### 2. Code Review Agent (LangGraph)
- **Purpose**: Orchestrates the code review process using AI
- **Framework**: LangGraph state machine
- **LLM**: Cost-effective model (e.g., gpt-3.5-turbo or claude-haiku)
- **Responsibilities**:
  - Coordinate tool calls to MCP servers
  - Fetch PR details, Jira criteria, and Confluence context
  - Analyze code changes against requirements and domain knowledge
  - Generate human-focused review comments
  - Post review feedback back to GitHub

### 3. MCP Servers

#### 3.1 GitHub MCP Server
- **Purpose**: Provides PR data and metadata
- **Implementation**: FastMCP with PyGithub
- **Tools**:
  - `get_pr_details(pr_url)`: Returns PR diff, description, author, files changed, commit history, labels, reviewers, etc.
- **Authentication**: GitHub token via environment variable
- **Real Implementation**: Uses actual GitHub API

#### 3.2 Jira MCP Server
- **Purpose**: Provides acceptance criteria and ticket context
- **Implementation**: FastMCP with stubbed responses
- **Tools**:
  - `get_acceptance_criteria(jira_ticket_id)`: Returns acceptance criteria, ticket description, status, assignee
  - `get_related_tickets(jira_ticket_id)`: Returns linked tickets (epics, stories, bugs)
- **Authentication**: Jira token via environment variable (for future real implementation)
- **Current State**: Stubbed responses matching real Jira API format

#### 3.3 Confluence MCP Server
- **Purpose**: Provides domain context and documentation
- **Implementation**: FastMCP with stubbed responses
- **Tools**:
  - `get_domain_context(confluence_page_id)`: Returns page content, related pages, domain-specific guidelines
  - `search_documentation(query)`: Searches Confluence for relevant documentation
- **Authentication**: Confluence token via environment variable (for future real implementation)
- **Current State**: Stubbed responses matching real Confluence API format

## Data Flow

### Primary Flow: PR Review Execution

1. **Trigger Event**: PR updated in GitHub (triggered via GitHub Actions, webhook, or GitHub App)
2. **Agent Initialization**: Pipeline triggers LangGraph agent with PR URL
3. **PR Data Fetching**: Agent calls GitHub MCP server to get PR details
4. **Context Gathering**:
   - Agent extracts Jira ticket ID from PR description/labels
   - Agent calls Jira MCP server for acceptance criteria
   - Agent identifies relevant Confluence pages (from ticket or PR metadata)
   - Agent calls Confluence MCP server for domain context
5. **Review Analysis**: Agent analyzes code changes against:
   - PR diff and metadata
   - Jira acceptance criteria
   - Domain context from Confluence
   - Human-focused review criteria (logic, design patterns, maintainability, etc.)
6. **Review Generation**: Agent generates review comments
7. **Feedback Posting**: Agent posts comments to GitHub PR (via GitHub MCP server or direct API)

### Error Handling Flow

- **MCP Server Failures**: Agent retries with exponential backoff (max 3 attempts)
- **Missing Context**: Agent proceeds with available context, logs warnings
- **Invalid PR URL**: Agent returns error to Jenkins, logs failure
- **Authentication Failures**: Agent logs error, returns failure status
- **Partial Data**: Agent performs review with available data, notes missing context in review

## Error Handling Considerations

### Retry Strategy
- **Transient Failures**: Exponential backoff (1s, 2s, 4s) for network/API errors
- **Max Retries**: 3 attempts per tool call
- **Timeout**: 30 seconds per MCP server call

### Error Types and Handling
1. **Network Errors**: Retry with backoff, fail after max retries
2. **Authentication Errors**: Log and fail immediately (no retry)
3. **Rate Limiting**: Implement exponential backoff, respect rate limit headers
4. **Invalid Input**: Validate inputs, return clear error messages
5. **Missing Data**: Continue with available data, log warnings

### Logging and Monitoring

#### LangSmith Integration (Recommended)

The agent integrates with LangSmith for comprehensive observability:

- **Tracing**: Automatic tracing of all LangChain/LangGraph operations
- **State Transitions**: Track agent state machine transitions
- **LLM Calls**: Monitor LLM requests, responses, tokens, and costs
- **Tool Usage**: Track MCP server tool calls and responses
- **Performance**: Measure execution time for each state and operation
- **Debugging**: View detailed traces in LangSmith dashboard

**Configuration:**
- Enable with `LANGCHAIN_TRACING_V2=true`
- Provide API key via `LANGCHAIN_API_KEY`
- Organize traces with `LANGCHAIN_PROJECT` (optional)

**Benefits:**
- Debug agent behavior and state transitions
- Optimize LLM usage and reduce costs
- Monitor agent performance over time
- Track errors and failures
- Share traces with team for collaboration

#### Additional Logging
- Log all tool calls and responses (sanitize sensitive data)
- Track review execution time
- Monitor MCP server availability
- Alert on repeated failures
- Log to standard output for CI/CD integration

## Authentication Assumptions

### Token-Based Authentication
All external services use token-based authentication via environment variables:

- **GitHub**: `GITHUB_TOKEN` - Personal Access Token or GitHub App token
- **Jira**: `JIRA_TOKEN` - API token (for future implementation)
- **Confluence**: `CONFLUENCE_TOKEN` - API token (for future implementation)

### Security Considerations
- Tokens stored as environment variables (not in code)
- Tokens rotated regularly
- Least privilege principle: tokens have minimal required permissions
- Jenkins manages token injection into agent execution environment

## Integration Points

### Pipeline Integration

**GitHub Actions Integration (Recommended)**
- Agent runs as GitHub Actions workflow step
- GitHub Actions provides execution environment and token injection
- GitHub Actions handles PR event triggering
- GitHub Actions manages workflow logs and status reporting
- PR URL available via `github.event.pull_request.html_url`

**Jenkins Integration (Alternative)**
- Agent runs as Jenkins job/step
- Jenkins provides execution environment and token injection
- Jenkins handles webhook reception and agent triggering
- Jenkins manages agent execution logs and status reporting

**GitHub App Integration (Alternative)**
- Agent runs as app server endpoint handler
- App server receives webhook events from GitHub
- App server manages token rotation and permissions
- App server handles webhook validation and retries

### GitHub Integration
- Webhook subscription to PR events (opened, updated, synchronized)
- GitHub API for PR data retrieval
- GitHub API for posting review comments
- GitHub API for PR status updates

### Jira Integration (Future)
- Jira REST API for ticket data
- Link PRs to Jira tickets via PR description or labels
- Extract ticket IDs from PR metadata

### Confluence Integration (Future)
- Confluence REST API for page content
- Link Confluence pages to Jira tickets or PRs
- Search Confluence for domain-specific documentation

## Scalability Considerations

### Horizontal Scaling
- Multiple agent instances can run in parallel (stateless design)
- MCP servers can be deployed independently
- Jenkins can distribute load across multiple agents

### Performance Optimization
- Cache frequently accessed Confluence pages
- Batch MCP server calls where possible
- Use streaming for large PR diffs
- Implement request queuing for rate-limited APIs

## Future Enhancements

1. **Real Jira/Confluence Integration**: Replace stubbed responses with actual API calls
2. **Review History**: Store review history for learning and improvement
3. **Custom Review Rules**: Allow teams to define custom review criteria
4. **Multi-Repository Support**: Extend to support multiple GitHub repositories
5. **Review Quality Metrics**: Track review accuracy and usefulness
6. **Incremental Reviews**: Only review new changes in updated PRs

