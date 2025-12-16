"""
ChromaDB Service for Confluence Documentation

This module provides ChromaDB integration for semantic search across
Confluence documentation. It enables finding relevant pages based on
semantic similarity when specific page IDs are not available.

The service is optional - if ChromaDB is not configured, the system
falls back to keyword-based search.
"""

import os
from typing import List, Dict, Optional
from pathlib import Path

# Optional imports for ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from langchain_community.embeddings import OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_core.documents import Document
    LANGCHAIN_CHROMA_AVAILABLE = True
except ImportError:
    LANGCHAIN_CHROMA_AVAILABLE = False


class ConfluenceChromaService:
    """
    Service for managing Confluence documentation in ChromaDB.
    
    Handles:
    - Ingesting Confluence pages into vector store
    - Semantic search across documentation
    - Updating cached content
    
    This service is optional - if ChromaDB is not available or configured,
    the system gracefully falls back to keyword search.
    """
    
    def __init__(self):
        """Initialize the ChromaDB service."""
        self.collection_name = "confluence_docs"
        self.vectorstore: Optional[Chroma] = None
        self.embeddings = None
        self._initialized = False
    
    def is_available(self) -> bool:
        """
        Check if ChromaDB is available and configured.
        
        Returns:
            True if ChromaDB can be used, False otherwise
        """
        if not CHROMADB_AVAILABLE or not LANGCHAIN_CHROMA_AVAILABLE:
            return False
        
        # Check if ChromaDB path is configured or if we can use in-memory
        chromadb_path = os.getenv("CHROMADB_PATH")
        return True  # Can always use in-memory if path not set
    
    def _initialize(self):
        """Initialize ChromaDB client and vector store."""
        if self._initialized:
            return
        
        if not self.is_available():
            raise RuntimeError(
                "ChromaDB is not available. Install with: pip install chromadb langchain-community"
            )
        
        # Get ChromaDB configuration
        chromadb_path = os.getenv("CHROMADB_PATH")
        chromadb_host = os.getenv("CHROMADB_HOST")
        chromadb_port = int(os.getenv("CHROMADB_PORT", "8000"))
        
        # Initialize embeddings
        try:
            self.embeddings = OpenAIEmbeddings()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize embeddings: {e}")
        
        # Initialize ChromaDB client
        if chromadb_host:
            # Remote ChromaDB server
            client = chromadb.HttpClient(host=chromadb_host, port=chromadb_port)
            persist_directory = None
        elif chromadb_path:
            # Local persistent storage
            persist_directory = str(Path(chromadb_path).expanduser().resolve())
            client = None
        else:
            # In-memory (ephemeral)
            persist_directory = None
            client = None
        
        # Initialize vector store
        try:
            if client:
                # Remote server - use ChromaDB client directly
                # Note: LangChain's Chroma doesn't support remote clients directly
                # For now, we'll use local storage even with remote option
                self.vectorstore = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=persist_directory
                )
            else:
                # Local or in-memory
                self.vectorstore = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=persist_directory
                )
            
            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ChromaDB vector store: {e}")
    
    def search_semantic(
        self, 
        query: str, 
        limit: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """
        Search for relevant documentation using semantic similarity.
        
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
        if not self.is_available():
            return []
        
        try:
            self._initialize()
            
            # Perform semantic search
            results = self.vectorstore.similarity_search_with_score(
                query,
                k=limit
            )
            
            # Format results
            formatted_results = []
            for doc, score in results:
                # Convert similarity distance to similarity score (ChromaDB returns distance)
                # Distance of 0 = perfect match (score 1.0), higher distance = lower similarity
                similarity_score = 1.0 / (1.0 + score) if score > 0 else 1.0
                
                if similarity_score < min_similarity:
                    continue
                
                # Extract metadata from document
                metadata = doc.metadata
                page_id = metadata.get("page_id", "")
                title = metadata.get("title", doc.page_content[:100])
                space_key = metadata.get("space_key", "")
                space_name = metadata.get("space_name", space_key)
                
                # Get excerpt from document content
                excerpt = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                
                formatted_results.append({
                    "id": page_id,
                    "title": title,
                    "space": {
                        "key": space_key,
                        "name": space_name
                    },
                    "excerpt": excerpt,
                    "similarity_score": round(similarity_score, 3),
                    "url": metadata.get("url", f"https://confluence.example.com/pages/viewpage.action?pageId={page_id}")
                })
            
            return formatted_results
        except Exception as e:
            print(f"Warning: ChromaDB semantic search failed: {e}")
            return []
    
    def _page_exists(self, page_id: str) -> bool:
        """
        Check if a page already exists in the vector store.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            True if page exists, False otherwise
        """
        try:
            self._initialize()
            # Try to get the document by ID
            # ChromaDB's get() method returns documents by ID
            collection = self.vectorstore._collection
            results = collection.get(ids=[page_id])
            return len(results.get("ids", [])) > 0
        except Exception:
            # If collection doesn't exist or error, assume it doesn't exist
            return False
    
    def ingest_page(self, page_data: Dict, force_update: bool = False) -> bool:
        """
        Add or update a Confluence page in the vector store.
        
        Args:
            page_data: Dictionary containing page information:
                {
                    "id": str,
                    "title": str,
                    "space": {"key": str, "name": str},
                    "body": {"storage": {"value": str}},
                    "url": str (optional)
                }
            force_update: If True, update even if page exists (default: False)
            
        Returns:
            True if page was ingested, False if skipped (already exists)
        """
        if not self.is_available():
            raise RuntimeError("ChromaDB is not available")
        
        try:
            self._initialize()
            
            page_id = page_data.get("id", "")
            if not page_id:
                raise ValueError("Page data must include an 'id' field")
            
            # Check if page already exists (unless force update)
            if not force_update and self._page_exists(page_id):
                return False  # Page already exists, skip
            
            # Extract text content from page
            body_html = page_data.get("body", {}).get("storage", {}).get("value", "")
            # Simple HTML stripping (in production, use BeautifulSoup or similar)
            import re
            text_content = re.sub(r'<[^>]+>', '', body_html)
            text_content = text_content.strip()
            
            if not text_content:
                text_content = page_data.get("title", "")
            
            # Create document with metadata
            doc = Document(
                page_content=text_content,
                metadata={
                    "page_id": page_id,
                    "title": page_data.get("title", ""),
                    "space_key": page_data.get("space", {}).get("key", ""),
                    "space_name": page_data.get("space", {}).get("name", ""),
                    "url": page_data.get("url", "")
                }
            )
            
            # Add or update in vector store (ChromaDB updates if ID exists)
            self.vectorstore.add_documents([doc], ids=[page_id])
            
            return True  # Page was ingested
            
        except Exception as e:
            raise RuntimeError(f"Failed to ingest page: {e}")
    
    def bulk_ingest(self, pages: List[Dict], force_update: bool = False, skip_existing: bool = True) -> Dict[str, int]:
        """
        Ingest multiple pages at once.
        
        Args:
            pages: List of page dictionaries (same format as ingest_page)
            force_update: If True, update all pages even if they exist (default: False)
            skip_existing: If True, skip pages that already exist (default: True)
                          Only applies if force_update is False
            
        Returns:
            Dictionary with ingestion statistics:
            {
                "ingested": int,  # Number of pages ingested
                "skipped": int,   # Number of pages skipped (already exist)
                "failed": int     # Number of pages that failed to ingest
            }
        """
        if not self.is_available():
            raise RuntimeError("ChromaDB is not available")
        
        try:
            self._initialize()
            
            documents = []
            ids = []
            skipped = 0
            failed = 0
            
            for page_data in pages:
                page_id = page_data.get("id", "")
                if not page_id:
                    failed += 1
                    continue
                
                # Check if page exists (unless force update)
                if not force_update and skip_existing:
                    if self._page_exists(page_id):
                        skipped += 1
                        continue
                
                body_html = page_data.get("body", {}).get("storage", {}).get("value", "")
                import re
                text_content = re.sub(r'<[^>]+>', '', body_html)
                text_content = text_content.strip()
                
                if not text_content:
                    text_content = page_data.get("title", "")
                
                doc = Document(
                    page_content=text_content,
                    metadata={
                        "page_id": page_id,
                        "title": page_data.get("title", ""),
                        "space_key": page_data.get("space", {}).get("key", ""),
                        "space_name": page_data.get("space", {}).get("name", ""),
                        "url": page_data.get("url", "")
                    }
                )
                
                documents.append(doc)
                ids.append(page_id)
            
            # Batch add to vector store (only new/updated pages)
            if documents:
                try:
                    self.vectorstore.add_documents(documents, ids=ids)
                except Exception as e:
                    # If batch fails, try individual pages
                    print(f"Warning: Batch ingest failed, trying individual pages: {e}")
                    for doc, doc_id in zip(documents, ids):
                        try:
                            self.vectorstore.add_documents([doc], ids=[doc_id])
                        except Exception:
                            failed += 1
            
            ingested = len(documents)
            
            return {
                "ingested": ingested,
                "skipped": skipped,
                "failed": failed
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to bulk ingest pages: {e}")


# Global service instance
_chromadb_service: Optional[ConfluenceChromaService] = None


def get_chromadb_service() -> Optional[ConfluenceChromaService]:
    """
    Get or create the global ChromaDB service instance.
    
    Returns:
        ConfluenceChromaService instance if available, None otherwise
    """
    global _chromadb_service
    
    if _chromadb_service is None:
        _chromadb_service = ConfluenceChromaService()
    
    if not _chromadb_service.is_available():
        return None
    
    return _chromadb_service

