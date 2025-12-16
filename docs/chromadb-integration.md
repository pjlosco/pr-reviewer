# ChromaDB Integration for Semantic Search

## Overview

This document describes the ChromaDB integration in the PR Review Agent that enables semantic search across Confluence documentation when specific page IDs are not available. **This feature is now implemented** and available for use.

## Current State

### Current Approach

The agent currently uses **direct tool calls** to fetch specific Confluence pages:

1. **Known Page ID**: Agent extracts Confluence page ID from PR metadata → calls `get_domain_context(page_id)`
2. **Keyword Search**: Agent uses `search_documentation(query)` for basic text search (CQL or stub-based)
3. **On-Demand Fetching**: All content is fetched in real-time from Confluence API

### Limitations

- **Keyword Search Limitations**: Current `search_documentation()` uses simple text matching or CQL queries, which may miss semantically related content
- **No Semantic Understanding**: Can't find relevant pages based on code changes without exact keyword matches
- **API Overhead**: Every search requires API calls, even for similar queries
- **No Caching**: Repeated searches for similar content still hit the API

## Proposed ChromaDB Integration

### Use Case

ChromaDB would be most valuable when:

1. **No Page ID Specified**: PR doesn't reference specific Confluence pages
2. **Semantic Search Needed**: Agent needs to find relevant documentation based on code changes (not just keywords)
3. **Large Documentation Corpus**: Organization has extensive Confluence documentation
4. **Performance Optimization**: Reduce API calls through caching and local search

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PR Review Agent                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 1. Extract context from PR
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Context Extraction Node                        │
│  - Parse PR description, code changes                       │
│  - Extract keywords, topics, domain concepts                │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 2. Search for relevant docs
                            ▼
                    ┌───────┴────────┐
                    │                │
          ┌─────────▼─────────┐  ┌───▼──────────────────┐
          │   ChromaDB        │  │  Confluence MCP      │
          │   (Semantic)      │  │  (Direct API)        │
          │                   │  │                      │
          │  - Vector search  │  │  - Known page IDs    │
          │  - Similarity     │  │  - Keyword search    │
          │  - Cached docs    │  │  - Real-time fetch   │
          └─────────┬─────────┘  └───┬──────────────────┘
                    │                │
                    └───────┬────────┘
                            │ 3. Retrieve relevant pages
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Documentation Context                           │
│  - Relevant Confluence pages (from ChromaDB or API)         │
│  - Ranked by relevance/similarity                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 4. Use in code review
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Code Review Analysis                            │
│  - Uses domain context from Confluence                      │
│  - Validates against architectural guidelines               │
└─────────────────────────────────────────────────────────────┘
```

### Integration Points

#### 1. New MCP Tool: `search_documentation_semantic()`

Add a new tool that uses ChromaDB for semantic search:

```python
@mcp.tool()
def search_documentation_semantic(
    query: str,
    limit: int = 5,
    min_similarity: float = 0.7
) -> list[dict]:
    """
    Search Confluence documentation using semantic similarity.
    
    This tool uses ChromaDB to find relevant Confluence pages based on
    semantic meaning rather than just keyword matching. It's particularly
    useful when the agent needs to find relevant documentation based on
    code changes or PR context.
    
    Args:
        query: Natural language query describing what documentation is needed
        limit: Maximum number of results to return (default: 5)
        min_similarity: Minimum similarity score (0.0-1.0, default: 0.7)
        
    Returns:
        List of relevant Confluence pages with similarity scores:
        [
            {
                "id": str,
                "title": str,
                "space": {"key": str, "name": str},
                "excerpt": str,
                "similarity_score": float,
                "url": str
            }
        ]
    """
    # Implementation would:
    # 1. Generate embedding for query
    # 2. Search ChromaDB for similar documents
    # 3. Filter by min_similarity
    # 4. Return top N results with metadata
    pass
```

#### 2. ChromaDB Service Module

Create a new module for ChromaDB operations:

```python
# mcp_servers/chromadb_service.py

import os
from typing import List, Dict, Optional
from chromadb import Client, Settings
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

class ConfluenceChromaService:
    """
    Service for managing Confluence documentation in ChromaDB.
    
    Handles:
    - Ingesting Confluence pages into vector store
    - Semantic search across documentation
    - Updating cached content
    """
    
    def __init__(self):
        self.collection_name = "confluence_docs"
        self.embeddings = OpenAIEmbeddings()
        self.client = self._init_chromadb()
        self.vectorstore = self._init_vectorstore()
    
    def search_semantic(
        self, 
        query: str, 
        limit: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """Search for relevant documentation using semantic similarity."""
        # Implementation
        pass
    
    def ingest_page(self, page_data: Dict) -> None:
        """Add or update a Confluence page in the vector store."""
        # Implementation
        pass
    
    def bulk_ingest(self, pages: List[Dict]) -> None:
        """Ingest multiple pages at once."""
        # Implementation
        pass
    
    def update_page(self, page_id: str, page_data: Dict) -> None:
        """Update an existing page in the vector store."""
        # Implementation
        pass
```

#### 3. Agent Workflow Integration

Update the agent's `extract_context_ids_node` to use semantic search when no page ID is found:

```python
def extract_context_ids_node(state: AgentState) -> AgentState:
    """
    Extract context IDs or search for relevant documentation.
    """
    pr_details = state["pr_details"]
    
    # Try to extract explicit page IDs first (current approach)
    confluence_page_id = extract_page_id_from_pr(pr_details)
    
    if confluence_page_id:
        # Use direct page fetch (current approach)
        state["confluence_page_id"] = confluence_page_id
        return state
    
    # No page ID found - use semantic search
    # Extract context from PR for semantic search
    search_query = build_semantic_query(pr_details)
    
    # Use semantic search tool
    relevant_pages = search_documentation_semantic(
        query=search_query,
        limit=3,  # Top 3 most relevant pages
        min_similarity=0.7
    )
    
    if relevant_pages:
        # Use the most relevant page
        state["confluence_page_id"] = relevant_pages[0]["id"]
        state["confluence_context"] = {
            "pages": relevant_pages,
            "search_method": "semantic"
        }
    
    return state
```

## Implementation Steps

### Phase 1: ChromaDB Setup

1. **Add Dependencies**
   ```bash
   pip install chromadb langchain-openai
   ```

2. **Create ChromaDB Service Module**
   - `mcp_servers/chromadb_service.py`
   - Initialize ChromaDB client
   - Set up embedding model (OpenAI or alternative)
   - Create collection for Confluence docs

3. **Configuration**
   ```bash
   # Environment variables
   CHROMADB_PATH=./chroma_db  # Local persistent storage
   # OR
   CHROMADB_HOST=localhost
   CHROMADB_PORT=8000
   
   # Embedding model
   OPENAI_API_KEY=...  # For OpenAI embeddings
   # OR use alternative embedding model
   ```

### Phase 2: Ingestion Pipeline

1. **Initial Ingestion**
   - Create script to ingest all Confluence pages
   - Extract text content from pages
   - Generate embeddings
   - Store in ChromaDB with metadata (page_id, title, space, url)

2. **Incremental Updates**
   - Periodic sync job to update changed pages
   - Handle page deletions
   - Update embeddings when content changes

3. **Ingestion Options**
   ```python
   # Option A: One-time bulk ingestion
   python scripts/ingest_confluence.py --all
   
   # Option B: Incremental sync
   python scripts/ingest_confluence.py --since 2024-01-01
   
   # Option C: Single page
   python scripts/ingest_confluence.py --page-id 123456
   ```

### Phase 3: MCP Tool Integration

1. **Add Semantic Search Tool**
   - Implement `search_documentation_semantic()` in `confluence_server.py`
   - Integrate with ChromaDB service
   - Return results in same format as existing search

2. **Hybrid Search Strategy**
   - Try semantic search first (ChromaDB)
   - Fall back to keyword search (current approach) if needed
   - Combine results for best coverage

### Phase 4: Agent Integration

1. **Update State Machine**
   - Modify `extract_context_ids_node` to use semantic search
   - Add fallback logic (semantic → keyword → skip)

2. **Query Building**
   - Extract relevant context from PR (code changes, description)
   - Build natural language query for semantic search
   - Use LLM to generate better search queries if needed

## Code Structure

```
mcp_servers/
├── confluence_server.py          # Existing (add semantic search tool)
├── chromadb_service.py           # NEW: ChromaDB operations
│   ├── ConfluenceChromaService   # Main service class
│   ├── ingestion                 # Ingestion utilities
│   └── search                    # Search utilities
└── ...

scripts/
├── ingest_confluence.py          # NEW: Ingestion script
│   ├── bulk_ingest()             # Ingest all pages
│   ├── incremental_sync()        # Sync changed pages
│   └── single_page()             # Ingest single page
└── ...

agent/
└── review_agent.py               # Update to use semantic search
    └── extract_context_ids_node  # Add semantic search logic
```

## Configuration

### Environment Variables

```bash
# ChromaDB Configuration
CHROMADB_PATH=./chroma_db                    # Local file-based storage
# OR
CHROMADB_HOST=localhost                       # Remote ChromaDB server
CHROMADB_PORT=8000

# Embedding Model
OPENAI_API_KEY=sk-...                         # For OpenAI embeddings
# OR
EMBEDDING_MODEL=text-embedding-3-small        # Model name
EMBEDDING_PROVIDER=openai                     # openai, huggingface, etc.

# Ingestion Settings
CONFLUENCE_INGEST_SPACES=ENG,DEV,DOCS         # Spaces to ingest
CONFLUENCE_INGEST_LIMIT=1000                  # Max pages to ingest
CONFLUENCE_INGEST_UPDATE_INTERVAL=24h          # How often to sync
```

### ChromaDB Storage Options

1. **Local File-Based** (Recommended for single instance)
   ```python
   CHROMADB_PATH=./chroma_db
   ```

2. **In-Memory** (For testing)
   ```python
   # Ephemeral, no persistence
   ```

3. **Remote Server** (For multi-instance deployments)
   ```python
   CHROMADB_HOST=chromadb.example.com
   CHROMADB_PORT=8000
   ```

## Benefits

### Advantages

1. **Semantic Understanding**: Finds relevant docs even without exact keywords
2. **Performance**: Local search is faster than API calls
3. **Caching**: Reduces load on Confluence API
4. **Better Relevance**: Vector similarity often better than keyword matching
5. **Scalability**: Can handle large documentation corpora efficiently

### Use Cases

- **Code Change Analysis**: "Find docs about authentication patterns" when PR adds auth code
- **Domain Context**: "What are our API design guidelines?" when PR modifies API
- **Architecture Patterns**: "Show me examples of microservice communication" for service changes
- **Best Practices**: "What's our error handling standard?" for error handling code

## Trade-offs

### Disadvantages

1. **Additional Infrastructure**: Requires ChromaDB setup and maintenance
2. **Ingestion Overhead**: Need to sync Confluence content regularly
3. **Storage Requirements**: Vector embeddings require disk space
4. **Staleness Risk**: Cached content may be outdated
5. **Complexity**: More moving parts to maintain
6. **Embedding Costs**: Generating embeddings (if using paid API)

### When NOT to Use ChromaDB

- **Small Documentation Set**: If you have < 100 pages, keyword search may suffice
- **Frequent Updates**: If docs change constantly, keeping ChromaDB in sync is hard
- **Simple Use Cases**: If page IDs are always available, direct fetch is simpler
- **Resource Constraints**: Limited infrastructure for running ChromaDB

## Migration Path

### Option 1: Gradual Rollout

1. **Phase 1**: Implement ChromaDB alongside existing search (both available)
2. **Phase 2**: Agent tries semantic search first, falls back to keyword
3. **Phase 3**: Make semantic search primary, keyword as fallback
4. **Phase 4**: Remove keyword search if semantic works well

### Option 2: Feature Flag

```python
# Environment variable to enable/disable
USE_CHROMADB_SEMANTIC_SEARCH=true  # or false

def search_documentation(query: str):
    if os.getenv("USE_CHROMADB_SEMANTIC_SEARCH") == "true":
        return search_documentation_semantic(query)
    else:
        return search_documentation_keyword(query)  # Current implementation
```

## Testing Strategy

### Unit Tests

- Test ChromaDB service initialization
- Test embedding generation
- Test semantic search queries
- Test ingestion pipeline

### Integration Tests

- Test end-to-end: PR → semantic search → context retrieval
- Test fallback: semantic search fails → keyword search
- Test with real Confluence data (if available)

### Performance Tests

- Measure search latency (semantic vs keyword)
- Measure ingestion time for large corpora
- Test concurrent searches

## Example Usage

### Scenario: PR Adds Authentication Code

**Without ChromaDB** (Current):
```
1. Agent extracts keywords: "authentication", "OAuth2"
2. Calls search_documentation("authentication OAuth2")
3. Gets keyword matches (may miss semantically related pages)
```

**With ChromaDB** (Proposed):
```
1. Agent analyzes code changes: "Added OAuth2 login flow"
2. Calls search_documentation_semantic("OAuth2 authentication implementation patterns")
3. ChromaDB finds pages with similar semantic meaning:
   - "Authentication Architecture" (similarity: 0.89)
   - "OAuth2 Integration Guide" (similarity: 0.85)
   - "Security Best Practices" (similarity: 0.78)
4. Agent uses most relevant pages for context
```

## Future Enhancements

1. **Multi-Modal Search**: Combine semantic + keyword + metadata filters
2. **Query Expansion**: Use LLM to improve search queries
3. **Relevance Feedback**: Learn from which docs are actually useful
4. **Automatic Ingestion**: Auto-sync on Confluence page updates (webhook)
5. **Cross-Reference**: Link related pages based on semantic similarity

## Conclusion

ChromaDB integration would significantly enhance the agent's ability to find relevant documentation when page IDs aren't specified. However, it adds complexity and infrastructure requirements. 

**Recommendation**: Implement this enhancement when:
- You have a large Confluence documentation corpus (> 500 pages)
- Page IDs are frequently missing from PRs
- You have infrastructure to run and maintain ChromaDB
- Semantic search would provide clear value over keyword search

For now, the current direct tool call approach with keyword search is sufficient for most use cases.

