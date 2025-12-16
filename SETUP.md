# Quick Setup Reference

Quick reference for setting up the PR Review Agent in a demo project.

## Installation

```bash
pip install git+https://github.com/pjlosco/pr-reviewer.git
```

## GitHub Actions Workflow

Create `.github/workflows/code-review.yml`:

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
      - run: python app.py --pr-url "${{ github.event.pull_request.html_url }}"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LLM_PROVIDER: "openai"
          LLM_MODEL: "gpt-3.5-turbo"
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          JIRA_STUB_DATA_PATH: ./stubs/jira-stubs.json
          CONFLUENCE_STUB_DATA_PATH: ./stubs/confluence-stubs.json
```

## Required Secrets

Add in **Settings** → **Secrets and variables** → **Actions**:

- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`)

## Optional Configuration

- **LangSmith**: `LANGCHAIN_TRACING_V2: "true"`, `LANGCHAIN_API_KEY`
- **Real Jira/Confluence**: Set `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, etc.
- **ChromaDB**: Install `chromadb langchain-community`, set `CHROMADB_PATH`

## Stub Data (Optional)

Create `stubs/jira-stubs.json` and `stubs/confluence-stubs.json` - see [Stub Data Format](docs/stub-data-format.md).

## Full Documentation

See [Setting Up Demo Project](docs/setup-demo-project.md) for complete instructions.
