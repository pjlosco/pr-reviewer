# Setting Up a Demo Project with PR Review Agent

This guide explains how to use the `pr-review-agent` package in a separate demo project to automatically review pull requests.

## Quick Start

1. **Install the package** in your demo project:
   ```bash
   pip install git+https://github.com/pjlosco/pr-reviewer.git
   ```

2. **Create GitHub Actions workflow** (`.github/workflows/code-review.yml`):
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
             LLM_PROVIDER: "openai"
             LLM_MODEL: "gpt-3.5-turbo"
             LLM_TEMPERATURE: "0.7"
             OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
             # Optional: LangSmith observability
             LANGCHAIN_TRACING_V2: "true"
             LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
             # Optional: Stub data for Jira/Confluence
             JIRA_STUB_DATA_PATH: ./stubs/jira-stubs.json
             CONFLUENCE_STUB_DATA_PATH: ./stubs/confluence-stubs.json
   ```

3. **Add GitHub Secrets**:
   - Go to **Settings** → **Secrets and variables** → **Actions**
   - Add `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` for other providers)
   - Optionally add `LANGCHAIN_API_KEY` for observability

4. **Create stub data** (optional, recommended for demos):
   - Create `stubs/jira-stubs.json` and `stubs/confluence-stubs.json`
   - See [Stub Data Format](stub-data-format.md) for examples

5. **Test**: Create a PR and the agent will automatically review it.

## Configuration

### LLM Configuration

Set in your workflow environment variables:

- `LLM_PROVIDER`: `"openai"`, `"anthropic"`, or `"google"`
- `LLM_MODEL`: Model name (e.g., `"gpt-3.5-turbo"`, `"claude-3-haiku-20240307"`)
- `LLM_TEMPERATURE`: `"0.7"` (default, range: 0.0-1.0)
- API Key: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`

### Jira/Confluence Configuration

**Option A: Use Stub Data (Recommended for demos)**
- Create `stubs/jira-stubs.json` and `stubs/confluence-stubs.json` in your repo
- Set `JIRA_STUB_DATA_PATH` and `CONFLUENCE_STUB_DATA_PATH` in workflow
- See [Stub Data Format](stub-data-format.md) for format

**Option B: Use Real APIs**
- Add secrets: `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- Add secrets: `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`
- Set these environment variables in workflow
- Agent automatically detects real API credentials and uses them

**Option C: Use Default Stubs**
- Leave unset to use built-in minimal stubs

### ChromaDB Semantic Search (Optional)

ChromaDB enables automatic discovery of relevant Confluence documentation when page IDs aren't specified in PRs.

**Quick Setup with GitHub Actions Cache:**
```yaml
- name: Install ChromaDB
  run: pip install chromadb langchain-community

- name: Cache ChromaDB
  uses: actions/cache@v3
  with:
    path: ~/.chromadb/confluence
    key: chromadb-confluence-${{ hashFiles('stubs/confluence-stubs.json') }}

- name: Ingest Confluence (if needed)
  env:
    CHROMADB_PATH: ~/.chromadb/confluence
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    if [ ! -d ~/.chromadb/confluence ]; then
      # Note: Ingestion script is not included in pip package, so clone repo temporarily
      git clone --depth 1 https://github.com/pjlosco/pr-reviewer.git /tmp/pr-reviewer
      python /tmp/pr-reviewer/scripts/ingest_confluence.py --from-stubs
    fi

- name: Run Review
  env:
    CHROMADB_PATH: ~/.chromadb/confluence
    # ... other env vars
```

**How It Works:**
- If PR specifies Confluence page ID → direct lookup
- If no page ID → tries semantic search via ChromaDB
- If ChromaDB unavailable → falls back to keyword search
- If no results → continues without Confluence context

See [ChromaDB Setup Guide](chromadb-setup.md) for detailed instructions.

### LangSmith Observability (Optional but Recommended)

Enable LangSmith tracing for observability and debugging:

- `LANGCHAIN_TRACING_V2`: `"true"` (enable tracing)
- `LANGCHAIN_API_KEY`: Your LangSmith API key (get from https://smith.langchain.com)
- `LANGCHAIN_PROJECT`: `"pr-review-agent"` (optional project name)

**Benefits:** Track agent execution, debug LLM calls, monitor performance and costs.

## Stub Data Format

Create `stubs/jira-stubs.json`:
```json
{
  "tickets": {
    "PROJ-123": {
      "key": "PROJ-123",
      "summary": "Implement user authentication",
      "description": "Add OAuth2 authentication flow",
      "status": "In Progress",
      "acceptanceCriteria": [
        "User can log in with OAuth2",
        "Session is maintained for 24 hours"
      ]
    }
  }
}
```

Create `stubs/confluence-stubs.json`:
```json
{
  "pages": {
    "123456": {
      "id": "123456",
      "title": "API Design Guidelines",
      "body": {
        "storage": {
          "value": "<h2>REST API Standards</h2><ul><li>Use HTTP status codes correctly</li></ul>"
        }
      }
    }
  }
}
```

See [Stub Data Format](stub-data-format.md) for complete format specification.

## Troubleshooting

**Workflow Fails with "OPENAI_API_KEY not found"**
- Verify `OPENAI_API_KEY` is set as a repository secret
- Check secret name matches exactly (case-sensitive)

**No Review Comments Appear**
- Check Actions tab for error logs
- Verify PR URL is correct
- Ensure workflow has `pull-requests: write` permission

**Agent Can't Find Jira/Confluence Data**
- Verify stub files exist at specified paths
- Check file paths in workflow match repository structure
- Agent continues without Jira/Confluence context if files are missing

**ChromaDB Not Working**
- ChromaDB is optional - agent falls back automatically
- Ensure pages are ingested first if using ChromaDB
- Check `CHROMADB_PATH` or `CHROMADB_HOST` is set correctly

## Advanced Configuration

### Use Different LLM Provider

Update workflow environment variables:
```yaml
env:
  LLM_PROVIDER: "anthropic"
  LLM_MODEL: "claude-3-haiku-20240307"
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Switch from Stubs to Real API

1. Add API credentials as secrets
2. Update workflow to set real API environment variables
3. Remove or comment out stub data paths
4. Agent automatically detects and uses real APIs

### Use Remote ChromaDB Server

For production, use a remote ChromaDB server:

1. Deploy ChromaDB server (Docker, cloud service, etc.)
2. Add secrets: `CHROMADB_HOST`, `CHROMADB_PORT`
3. Set up separate scheduled job for ingestion
4. Set `CHROMADB_HOST` and `CHROMADB_PORT` in review workflow

See [ChromaDB in GitHub Actions](chromadb-github-actions.md) for detailed setup.

## Reference

- [Architecture Documentation](architecture.md)
- [Stub Data Format](stub-data-format.md)
- [ChromaDB Setup Guide](chromadb-setup.md)
- [ChromaDB in GitHub Actions](chromadb-github-actions.md)
