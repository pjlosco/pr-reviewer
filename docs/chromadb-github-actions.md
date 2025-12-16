# ChromaDB in GitHub Actions

## The Problem

GitHub Actions runners are **ephemeral** - they start fresh for each workflow run. This means:

1. **In-memory ChromaDB** (default): Database is rebuilt every time
2. **Local persistent storage**: Data is lost when the runner terminates
3. **No persistence**: Every run requires full re-ingestion

## Solutions

### Option 1: Use GitHub Actions Cache (Recommended for Small Datasets)

Cache the ChromaDB directory between runs:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache ChromaDB
        uses: actions/cache@v3
        with:
          path: ~/.chromadb/confluence
          key: chromadb-confluence-${{ hashFiles('stubs/confluence-stubs.json') }}
          restore-keys: |
            chromadb-confluence-
      
      - name: Install dependencies
        run: |
          pip install git+https://github.com/pjlosco/pr-reviewer.git
          pip install chromadb langchain-community
      
      - name: Ingest Confluence pages (if needed)
        env:
          CHROMADB_PATH: ~/.chromadb/confluence
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          # Only ingest if cache was not restored (first run or cache miss)
          # Note: Ingestion script is not included in the pip package, so we clone the repo
          if [ ! -d ~/.chromadb/confluence ]; then
            git clone --depth 1 https://github.com/pjlosco/pr-reviewer.git /tmp/pr-reviewer
            python /tmp/pr-reviewer/scripts/ingest_confluence.py --from-stubs
          fi
      
      - name: Run code review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CHROMADB_PATH: ~/.chromadb/confluence
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          pr-review-agent --pr-url "${{ github.event.pull_request.html_url }}"
```

**Pros:**
- Fast subsequent runs (cache hit)
- No external dependencies
- Works with GitHub Actions

**Cons:**
- Cache size limits (10GB per repo)
- Cache can be evicted
- Still rebuilds on cache miss

### Option 2: Use Remote ChromaDB Server (Recommended for Production)

Use a persistent ChromaDB server that survives between runs:

```yaml
- name: Run code review
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    CHROMADB_HOST: ${{ secrets.CHROMADB_HOST }}
    CHROMADB_PORT: ${{ secrets.CHROMADB_PORT }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    pr-review-agent --pr-url "${{ github.event.pull_request.html_url }}"
```

**Setup:**
1. Deploy ChromaDB server (Docker, cloud service, etc.)
2. Run ingestion as a separate scheduled job or one-time setup
3. Agent connects to remote server for searches

**Pros:**
- Persistent across all runs
- Shared across multiple workflows
- No cache size limits
- Incremental updates work perfectly

**Cons:**
- Requires infrastructure setup
- Additional cost/maintenance

### Option 3: Skip ChromaDB in Actions, Use Only in CI/CD

For GitHub Actions specifically, you might skip ChromaDB and rely on:
- Direct page ID lookup (if provided in PR)
- Keyword search fallback
- Semantic search only in non-ephemeral environments

```python
# In your workflow, set CHROMADB_PATH only if you want to use it
# Otherwise, agent gracefully falls back to keyword search
```

## Incremental Updates

The improved implementation now supports:

1. **Duplicate Detection**: Checks if pages exist before ingesting
2. **Skip Existing**: `skip_existing=True` (default) skips pages that already exist
3. **Force Update**: `force_update=True` updates all pages regardless
4. **Statistics**: Returns counts of ingested/skipped/failed pages

### Example: Incremental Ingestion

```python
from mcp_servers.chromadb_service import get_chromadb_service

service = get_chromadb_service()

# First run: ingests all pages
stats = service.bulk_ingest(pages, skip_existing=True)
# Returns: {"ingested": 100, "skipped": 0, "failed": 0}

# Second run: only ingests new pages
stats = service.bulk_ingest(pages, skip_existing=True)
# Returns: {"ingested": 5, "skipped": 100, "failed": 0}
```

## Best Practices

1. **Use Remote Server for Production**: Most reliable option
2. **Use Cache for Development**: Good for testing with small datasets
3. **Separate Ingestion Job**: Run ingestion as a scheduled job, not per-PR
4. **Monitor Cache Hit Rate**: If cache misses are frequent, consider remote server
5. **Set CHROMADB_PATH**: Always use persistent storage in CI/CD (not in-memory)

## Example: Scheduled Ingestion Job

```yaml
name: Update ChromaDB

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:  # Manual trigger

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install git+https://github.com/pjlosco/pr-reviewer.git
          pip install chromadb langchain-community
      
      - name: Ingest Confluence pages
        env:
          CHROMADB_HOST: ${{ secrets.CHROMADB_HOST }}
          CHROMADB_PORT: ${{ secrets.CHROMADB_PORT }}
          CONFLUENCE_URL: ${{ secrets.CONFLUENCE_URL }}
          CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
          CONFLUENCE_API_TOKEN: ${{ secrets.CONFLUENCE_API_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          # Ingest specific pages or spaces
          # Note: Clone repo first since scripts aren't in the pip package
          git clone --depth 1 https://github.com/pjlosco/pr-reviewer.git /tmp/pr-reviewer
          python /tmp/pr-reviewer/scripts/ingest_confluence.py --page-ids 123456 789012
```

This way, ingestion happens once (or periodically), and the agent just searches the persistent database.

