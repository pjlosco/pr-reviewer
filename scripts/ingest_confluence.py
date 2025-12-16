#!/usr/bin/env python3
"""
Confluence ChromaDB Ingestion Script

This script ingests Confluence pages into ChromaDB for semantic search.
It can be run manually or as part of a periodic sync job.

Usage:
    # Ingest all pages from a space
    python scripts/ingest_confluence.py --space-key ENG --all
    
    # Ingest specific pages
    python scripts/ingest_confluence.py --page-ids 123456 789012
    
    # Ingest from stub data
    python scripts/ingest_confluence.py --from-stubs
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.chromadb_service import get_chromadb_service
from mcp_servers.confluence_server import (
    should_use_real_api,
    get_confluence_loader,
    fetch_page_real_api,
    get_stub_data,
)


def ingest_from_real_api(space_key: str = None, page_ids: list = None):
    """Ingest pages from real Confluence API."""
    if not should_use_real_api():
        print("Error: Real Confluence API credentials not configured")
        print("Set CONFLUENCE_URL, CONFLUENCE_EMAIL, and CONFLUENCE_API_TOKEN")
        return False
    
    service = get_chromadb_service()
    if not service:
        print("Error: ChromaDB is not available")
        print("Install with: pip install chromadb langchain-community")
        return False
    
    try:
        loader = get_confluence_loader()
        
        if page_ids:
            # Ingest specific pages
            pages = []
            for page_id in page_ids:
                try:
                    page_data = fetch_page_real_api(page_id)
                    pages.append(page_data)
                    print(f"Fetched page: {page_data.get('title', page_id)}")
                except Exception as e:
                    print(f"Warning: Failed to fetch page {page_id}: {e}")
            
            if pages:
                stats = service.bulk_ingest(pages, skip_existing=True)
                print(f"✓ Ingested {stats['ingested']} pages into ChromaDB")
                if stats['skipped'] > 0:
                    print(f"  (Skipped {stats['skipped']} existing pages)")
                if stats['failed'] > 0:
                    print(f"  (Failed {stats['failed']} pages)")
                return True
        elif space_key:
            # Ingest all pages from a space
            # Note: This requires using the underlying Confluence client
            # to list all pages in a space, then fetch each one
            print(f"Ingesting all pages from space: {space_key}")
            print("Note: Full space ingestion not yet implemented")
            print("Use --page-ids to ingest specific pages")
            return False
        else:
            print("Error: Must specify --space-key or --page-ids")
            return False
            
    except Exception as e:
        print(f"Error: Failed to ingest from real API: {e}")
        return False


def ingest_from_stubs():
    """Ingest pages from stub data."""
    service = get_chromadb_service()
    if not service:
        print("Error: ChromaDB is not available")
        print("Install with: pip install chromadb langchain-community")
        return False
    
    try:
        stub_data = get_stub_data()
        pages = stub_data.get("pages", {})
        
        if not pages:
            print("No pages found in stub data")
            return False
        
        # Convert stub pages to list format
        page_list = []
        for page_id, page_data in pages.items():
            page_list.append(page_data)
        
        stats = service.bulk_ingest(page_list, skip_existing=True)
        print(f"✓ Ingested {stats['ingested']} pages from stub data into ChromaDB")
        if stats['skipped'] > 0:
            print(f"  (Skipped {stats['skipped']} existing pages)")
        if stats['failed'] > 0:
            print(f"  (Failed {stats['failed']} pages)")
        return True
        
    except Exception as e:
        print(f"Error: Failed to ingest from stubs: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Confluence pages into ChromaDB for semantic search"
    )
    
    parser.add_argument(
        "--space-key",
        type=str,
        help="Confluence space key to ingest all pages from"
    )
    
    parser.add_argument(
        "--page-ids",
        nargs="+",
        help="Specific page IDs to ingest"
    )
    
    parser.add_argument(
        "--from-stubs",
        action="store_true",
        help="Ingest from stub data instead of real API"
    )
    
    parser.add_argument(
        "--chromadb-path",
        type=str,
        help="Path to ChromaDB storage (default: in-memory or CHROMADB_PATH env var)"
    )
    
    args = parser.parse_args()
    
    # Set ChromaDB path if provided
    if args.chromadb_path:
        os.environ["CHROMADB_PATH"] = args.chromadb_path
    
    if args.from_stubs:
        success = ingest_from_stubs()
    elif args.page_ids:
        success = ingest_from_real_api(page_ids=args.page_ids)
    elif args.space_key:
        success = ingest_from_real_api(space_key=args.space_key)
    else:
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

