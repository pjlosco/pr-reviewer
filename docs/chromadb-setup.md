# ChromaDB Setup Guide

## Overview

ChromaDB integration enables semantic search across Confluence documentation when specific page IDs are not provided in PRs. This allows the agent to automatically find relevant documentation based on code changes and PR context.

## Installation

ChromaDB is an optional dependency. Install it with:

```bash
pip install chromadb langchain-community
```

Or install the optional dependency group:

```bash
pip install -e ".[chromadb]"
```

## Configuration

### Environment Variables

```bash
# Optional: Path to persistent ChromaDB storage (default: in-memory)
CHROMADB_PATH=/path/to/chromadb/storage

# Optional: Remote ChromaDB server (if using remote instance)
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# Required: OpenAI API key for embeddings (used by ChromaDB)
OPENAI_API_KEY=sk-...
```

### Storage Options

1. **In-Memory (Default)**: Ephemeral storage, data lost on restart
   - No configuration needed
   - Good for testing

2. **Local Persistent**: Data stored on disk
   ```bash
   export CHROMADB_PATH=~/.chromadb/confluence
   ```

3. **Remote Server**: Connect to ChromaDB server
   ```bash
   export CHROMADB_HOST=chromadb.example.com
   export CHROMADB_PORT=8000
   ```

## Ingesting Confluence Pages

Before semantic search can work, Confluence pages must be ingested into ChromaDB.

### From Stub Data

```bash
python scripts/ingest_confluence.py --from-stubs
```

### From Real Confluence API

```bash
# Set Confluence credentials
export CONFLUENCE_URL=https://your-confluence.atlassian.net
export CONFLUENCE_EMAIL=your-email@example.com
export CONFLUENCE_API_TOKEN=your-api-token

# Ingest specific pages
python scripts/ingest_confluence.py --page-ids 123456 789012

# Note: Full space ingestion not yet implemented
```

### Automated Ingestion

You can set up a periodic job to sync Confluence pages:

```bash
# Cron job example (daily sync)
0 2 * * * cd /path/to/pr-reviewer && python scripts/ingest_confluence.py --from-stubs
```

## How It Works

### When Page ID is Provided

1. Agent extracts Confluence page ID from PR
2. Uses direct lookup via `get_domain_context(page_id)`
3. **ChromaDB is not used** in this case

### When No Page ID is Provided

1. Agent builds search query from PR context (title, description, file names)
2. Tries semantic search via ChromaDB (`search_documentation_semantic`)
3. If ChromaDB finds results:
   - Fetches full page content for the most relevant match
   - Uses that page in code review
4. If ChromaDB not available or no results:
   - Falls back to keyword search (`search_documentation`)
   - Uses first keyword match if found
5. If no results from either method:
   - Continues review without Confluence context (graceful degradation)

## Usage in Agent

The agent automatically uses ChromaDB when:
- No Confluence page ID is found in PR
- ChromaDB is installed and configured
- ChromaDB has been populated with pages

No code changes needed - it's automatic!

## Troubleshooting

### "ChromaDB is not available"

- Install ChromaDB: `pip install chromadb langchain-community`
- Check that `OPENAI_API_KEY` is set (required for embeddings)

### "No results from semantic search"

- Ensure pages have been ingested: `python scripts/ingest_confluence.py --from-stubs`
- Check that `CHROMADB_PATH` points to the correct database (if using persistent storage)
- Verify embeddings are working (check OpenAI API key)

### "Semantic search failed"

- Check logs for specific error messages
- Verify ChromaDB service can be initialized
- Ensure embeddings model is accessible

## Benefits

1. **Automatic Context Discovery**: Finds relevant docs without manual page ID specification
2. **Semantic Understanding**: Matches based on meaning, not just keywords
3. **Better Reviews**: More context leads to more informed code reviews
4. **Graceful Degradation**: Falls back to keyword search or continues without context if needed

## Limitations

- Requires initial ingestion of Confluence pages
- Needs OpenAI API key for embeddings (adds cost)
- In-memory storage is ephemeral (use persistent storage for production)
- Full space ingestion not yet implemented (use specific page IDs for now)

