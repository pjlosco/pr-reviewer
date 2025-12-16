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

## What to Expect

When the agent runs, it will post review comments on your PR. Here's what you'll see:

### In GitHub Actions (Most Common)

Since GitHub Actions cannot submit official reviews, the agent posts comments instead:

#### 1. Review Summary Comment

The agent posts a summary comment at the top of the PR conversation with the review decision:

```
**Review Decision: APPROVE** ✅

Code review completed. The implementation looks good overall. 
All acceptance criteria from DEMO-101 are met. The OAuth2 
authentication flow is correctly implemented with proper 
error handling.

---
*Note: GitHub Actions cannot submit official reviews, so this is posted as a comment.*
```

Or for issues found:

```
**Review Decision: REQUEST CHANGES** ❌

Code review completed with 3 comment(s). Several issues 
need to be addressed before this can be merged.

Issues found:
- Missing error handling in authentication flow
- API endpoints don't return proper HTTP status codes
- Performance concern with O(n*k) algorithm

---
*Note: GitHub Actions cannot submit official reviews, so this is posted as a comment.*
```

#### 2. Line-Specific Comments

The agent posts comments directly on specific lines of code:

**Example on `src/api.py` line 45:**
```
Consider adding proper HTTP status codes. According to the 
API Design Guidelines, authentication errors should return 
401 Unauthorized, not just an error message in the response body.
```

**Example on `src/leetcode_sliding_window.py` line 15:**
```
This algorithm has O(n*k) time complexity. Consider using 
the sliding window technique for O(n) complexity. See the 
optimized version in the same file for reference.
```

#### 3. File-Level Comments

For general file-level feedback:

```
**File: src/auth.py**

Overall structure looks good. Consider adding more 
comprehensive error handling for edge cases like network 
timeouts during OAuth token exchange.
```

### Outside GitHub Actions

When running outside GitHub Actions (e.g., locally or in other CI systems), the agent can submit official reviews:

- **APPROVE**: Shows as an approved review with green checkmark
- **REQUEST_CHANGES**: Shows as a "changes requested" review that blocks merging
- **COMMENT**: Shows as a review comment without approval/block

### Review Comment Format

All comments include:
- **Constructive feedback**: Actionable suggestions, not just criticism
- **Context-aware**: References Jira acceptance criteria and Confluence guidelines when available
- **Line-specific**: Points to exact lines when possible
- **Prioritized**: Most critical issues first

### Example Full Review

Here's what a complete review might look like:

**Summary Comment:**
```
**Review Decision: REQUEST CHANGES** ❌

Code review completed with 4 comment(s).

Overall Assessment:
- ✅ OAuth2 flow is correctly implemented
- ❌ Missing proper HTTP status codes in API responses
- ⚠️ Performance issue in sliding window algorithm
- 💡 Consider adding rate limiting per acceptance criteria

Please address the critical issues before merging.

---
*Note: GitHub Actions cannot submit official reviews, so this is posted as a comment.*
```

**Line Comments:**
1. `src/api.py:45` - "Return 401 status code for authentication errors"
2. `src/api.py:67` - "Return 404 status code when session not found"
3. `src/leetcode_sliding_window.py:15` - "Use sliding window for O(n) complexity"
4. `src/auth.py:52` - "Add timeout handling for OAuth token exchange"

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
