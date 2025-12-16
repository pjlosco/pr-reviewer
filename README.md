# PR Review Agent

An AI-powered code review agent that automatically reviews pull requests using LangGraph, MCP servers, and LLMs. The agent focuses on human-reviewer concerns (logic, design, maintainability) rather than issues already caught by CI/CD.

## Features

- 🤖 **AI-Powered Reviews**: Uses LLMs to analyze code changes
- 🔗 **Context-Aware**: Incorporates Jira acceptance criteria and Confluence domain knowledge
- 🔍 **Semantic Search**: ChromaDB integration for finding relevant Confluence docs automatically
- 🛠️ **MCP Architecture**: Leverages Model Context Protocol (MCP) servers for data fetching
- 🔄 **LangGraph State Machine**: Robust workflow orchestration with error handling
- 📊 **LangSmith Integration**: Built-in observability and monitoring (optional)
- 📦 **Package-Based**: Installable as a Python package for use in any repository
- ⚡ **Multiple Triggers**: Supports GitHub Actions, Jenkins, GitHub Apps, and more

## Architecture

The agent uses a LangGraph state machine to:
1. Fetch PR details from GitHub
2. Extract Jira ticket IDs and Confluence page references
3. Gather acceptance criteria from Jira (real API or stubs)
4. Retrieve domain context from Confluence (real API, semantic search, or stubs)
5. Analyze code changes with LLM
6. Generate and post review comments

See [Architecture Documentation](docs/architecture.md) for detailed design.

## Quick Start

### Installation

Install the package from GitHub:

```bash
pip install git+https://github.com/pjlosco/pr-reviewer.git
```

Or install locally for development:

```bash
git clone https://github.com/pjlosco/pr-reviewer.git
cd pr-reviewer
pip install -e .
```

### Usage

#### As a Command-Line Tool

```bash
export GITHUB_TOKEN="your_github_token"
export OPENAI_API_KEY="your_openai_key"

# Option 1: Run directly
python app.py --pr-url "https://github.com/owner/repo/pull/123"

# Option 2: Run as module
python -m app --pr-url "https://github.com/owner/repo/pull/123"

# Option 3: After installation, use console script
pr-review-agent --pr-url "https://github.com/owner/repo/pull/123"
```

#### As a Python Module

```python
from agent import run_review_agent

run_review_agent(pr_url="https://github.com/owner/repo/pull/123")
```

#### In GitHub Actions

See [Setting Up a Demo Project](docs/setup-demo-project.md) for complete instructions.

Quick example workflow (`.github/workflows/code-review.yml`):

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install git+https://github.com/pjlosco/pr-reviewer.git
      - run: pr-review-agent --pr-url "${{ github.event.pull_request.html_url }}"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          # LLM Configuration
          LLM_PROVIDER: "openai"
          LLM_MODEL: "gpt-3.5-turbo"
          LLM_TEMPERATURE: "0.7"
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          # LangSmith Observability (Optional)
          LANGCHAIN_TRACING_V2: "true"
          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
```

## Project Structure

```
pr-reviewer/
├── app.py                # Main entry point
├── agent/                # LangGraph agent implementation
│   ├── __init__.py
│   └── review_agent.py
├── mcp_servers/          # MCP server implementations
│   ├── __init__.py
│   ├── github_server.py   # Real GitHub API integration
│   ├── jira_server.py    # Real API or stubbed Jira integration
│   ├── confluence_server.py  # Real API, stubs, or semantic search
│   └── chromadb_service.py  # ChromaDB service for semantic search
├── scripts/              # Utility scripts
│   └── ingest_confluence.py  # ChromaDB ingestion script
├── docs/                 # Documentation
│   ├── architecture.md
│   ├── state-machine.md
│   ├── pipeline-options.md
│   └── setup-demo-project.md
├── diagrams/             # Architecture diagrams
│   ├── system-architecture.md
│   ├── state-machine.md
│   └── data-flow.md
├── .github/
│   └── workflows/
│       └── code-review.yml  # Example workflow
├── pyproject.toml        # Package configuration
├── requirements.txt      # Dependencies
└── README.md
```

## Requirements

- Python 3.11+
- GitHub token (for PR access)
- LLM API key (OpenAI, Anthropic, etc.)
- Optional: Jira token, Confluence token

## Configuration

### Environment Variables

#### Required
- `GITHUB_TOKEN`: GitHub personal access token or app token
- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY`): LLM API key

#### Jira Configuration (choose one option)

**Option A: Real API Connection**
- `JIRA_URL`: Your Jira instance URL (e.g., `https://company.atlassian.net`)
- `JIRA_EMAIL`: Your Jira email address
- `JIRA_API_TOKEN`: Your Jira API token

**Option B: Stub Data from File**
- `JIRA_STUB_DATA_PATH`: Path to stub data file (e.g., `./stubs/jira-stubs.json`)

**Option C: Stub Data from URL**
- `JIRA_STUB_DATA_URL`: URL to stub data file

**Option D: Default Stubs**
- Leave all Jira variables unset to use built-in minimal stubs

#### Confluence Configuration (choose one option)

**Option A: Real API Connection**
- `CONFLUENCE_URL`: Your Confluence instance URL (e.g., `https://company.atlassian.net`)
- `CONFLUENCE_EMAIL`: Your Confluence email address
- `CONFLUENCE_API_TOKEN`: Your Confluence API token

**Option B: Stub Data from File**
- `CONFLUENCE_STUB_DATA_PATH`: Path to stub data file (e.g., `./stubs/confluence-stubs.json`)

**Option C: Stub Data from URL**
- `CONFLUENCE_STUB_DATA_URL`: URL to stub data file

**Option D: Default Stubs**
- Leave all Confluence variables unset to use built-in minimal stubs

See [Stub Data Format](docs/stub-data-format.md) for creating stub data files.

#### ChromaDB Configuration (Optional - for Semantic Search)

ChromaDB enables semantic search to automatically find relevant Confluence documentation when page IDs aren't specified in PRs.

**Installation:**
```bash
pip install chromadb langchain-community
# or
pip install -e ".[chromadb]"
```

**Configuration:**
- `CHROMADB_PATH`: Path to persistent ChromaDB storage (default: in-memory)
- `CHROMADB_HOST`: Remote ChromaDB server host (optional)
- `CHROMADB_PORT`: Remote ChromaDB server port (default: 8000)
- `OPENAI_API_KEY`: Required for embeddings (used by ChromaDB)

**Ingestion:**
Before semantic search works, Confluence pages must be ingested:
```bash
# From stub data
python scripts/ingest_confluence.py --from-stubs

# From real API (specific pages)
python scripts/ingest_confluence.py --page-ids 123456 789012
```

See [ChromaDB Setup Guide](docs/chromadb-setup.md) for detailed instructions.

#### LangSmith Observability (Optional but Recommended)

LangSmith provides observability, debugging, and monitoring for LangChain applications:

- `LANGCHAIN_TRACING_V2`: Set to `"true"` to enable LangSmith tracing
- `LANGCHAIN_API_KEY`: Your LangSmith API key (get from https://smith.langchain.com)
- `LANGCHAIN_PROJECT`: Project name for organizing traces (e.g., `"pr-review-agent"`)
- `LANGCHAIN_ENDPOINT`: LangSmith endpoint (optional, defaults to cloud)

**Benefits:**
- Track agent execution and state transitions
- Debug LLM calls and tool usage
- Monitor performance and costs
- View detailed traces in LangSmith dashboard

### LLM Configuration

Configure the LLM directly in your GitHub Actions workflow file using environment variables:

- **`LLM_PROVIDER`**: Provider name (`"openai"`, `"anthropic"`, or `"google"`)
- **`LLM_MODEL`**: Model name (e.g., `"gpt-3.5-turbo"`, `"claude-3-haiku-20240307"`, `"gemini-pro"`)
- **`LLM_TEMPERATURE`**: Temperature setting (0.0-1.0, default: `"0.7"`)
- **API Key**: Provider-specific secret (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`)

Example configuration in workflow:
```yaml
env:
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-3.5-turbo"
  LLM_TEMPERATURE: "0.7"
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

The agent defaults to `gpt-3.5-turbo` if not specified.

## Documentation

- **[Setting Up Demo Project](docs/setup-demo-project.md)** - Complete guide for using the agent in your repository
- [Architecture Design](docs/architecture.md) - System architecture and components
- [State Machine Design](docs/state-machine.md) - LangGraph workflow details
- [Stub Data Format](docs/stub-data-format.md) - Format specification for stub data files
- [ChromaDB Setup Guide](docs/chromadb-setup.md) - How to set up ChromaDB for semantic search
- [ChromaDB in GitHub Actions](docs/chromadb-github-actions.md) - Persistence strategies for CI/CD

## MCP Servers

### GitHub MCP Server (Real Implementation)

- **Tool**: `get_pr_details(pr_url)`
- **Returns**: PR diff, description, author, files changed, commit history, labels, reviewers
- **Implementation**: FastMCP + PyGithub

### Jira MCP Server (Stubbed)

- **Tool**: `get_acceptance_criteria(jira_ticket_id)`
- **Returns**: Stubbed acceptance criteria matching real Jira API format
- **Status**: Ready for real API integration

### Confluence MCP Server (Real API or Stubs)

- **Tool**: `get_domain_context(confluence_page_id)` - Direct page lookup
- **Tool**: `search_documentation(query)` - Keyword-based search
- **Tool**: `search_documentation_semantic(query)` - Semantic search via ChromaDB (optional)
- **Returns**: Domain context matching real Confluence API format
- **Status**: Supports real API, stub data, and semantic search
- **Features**:
  - Real API integration via LangChain ConfluenceLoader
  - Stub data fallback for development/demo
  - ChromaDB semantic search when page IDs not provided
  - Automatic fallback chain: page ID → semantic search → keyword search

## Development

### Setup Development Environment

```bash
git clone https://github.com/pjlosco/pr-reviewer.git
cd pr-reviewer
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agent --cov=mcp_servers --cov=app --cov-report=term

# Run specific test file
pytest tests/test_review_agent.py -v
```

### Code Quality

```bash
black .
ruff check .
```

## Pipeline Integration

This agent can be triggered via:

1. **GitHub Actions** (Recommended) - See [setup guide](docs/setup-demo-project.md)
2. **GitHub App** - Webhook-based integration
3. **Jenkins** - Traditional CI/CD integration
4. **Direct Webhook** - Custom webhook handler
5. **Other CI/CD** - GitLab CI, CircleCI, etc.

See [Pipeline Options](docs/pipeline-options.md) for detailed comparison.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Status

- ✅ GitHub MCP server (real implementation)
- ✅ Jira MCP server (real API + stubs)
- ✅ Confluence MCP server (real API + stubs + semantic search)
- ✅ LangGraph agent implementation
- ✅ ChromaDB semantic search integration
- ✅ Documentation and examples

## Support

For questions, issues, or contributions:
- Open an issue on [GitHub](https://github.com/pjlosco/pr-reviewer/issues)
- See [Setup Guide](docs/setup-demo-project.md) for usage instructions
- Check [Architecture Docs](docs/architecture.md) for design details

