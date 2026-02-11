#!/usr/bin/env python3
"""
Index community chunks into ChromaDB for semantic search.

Usage:
    python3 indexer.py                                    # Index all in data/communities/
    python3 indexer.py --communities beltline seton        # Index specific ones
    python3 indexer.py --reindex                           # Wipe and rebuild all
    python3 indexer.py --stats                             # Show collection stats
"""

import argparse
import json
from pathlib import Path

import chromadb

from chunker import chunk_community, chunk_all


DATA_DIR = Path(__file__).parent / "data" / "communities"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "communities"


def get_client():
    """Get persistent ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_or_create_collection(client):
    """Get or create the communities collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Calgary community profiles for Q&A"}
    )


def index_chunks(collection, chunks, replace=False):
    """Add chunks to the collection."""
    if replace:
        # Remove existing chunks for these communities
        communities = set(c["community"] for c in chunks)
        for community in communities:
            existing = collection.get(where={"community": community})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "community": c["community"],
            "section": c["section"],
            "url": c["url"],
            "viz": json.dumps(c.get("viz", [])),
        }
        for c in chunks
    ]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def main():
    parser = argparse.ArgumentParser(description="Index communities into ChromaDB")
    parser.add_argument("--communities", nargs="+", help="Specific community slugs to index")
    parser.add_argument("--reindex", action="store_true", help="Wipe and rebuild entire index")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="Community JSON directory")
    args = parser.parse_args()

    client = get_client()

    if args.stats:
        try:
            collection = client.get_collection(COLLECTION_NAME)
            count = collection.count()
            print(f"Collection: {COLLECTION_NAME}")
            print(f"Total chunks: {count}")

            # Show per-community counts
            if count > 0:
                all_items = collection.get(include=["metadatas"])
                communities = {}
                for meta in all_items["metadatas"]:
                    c = meta["community"]
                    communities[c] = communities.get(c, 0) + 1
                print(f"Communities indexed: {len(communities)}")
                for c, n in sorted(communities.items()):
                    print(f"  {c}: {n} chunks")
        except Exception:
            print("No collection found. Run indexer first.")
        return

    if args.reindex:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("Deleted existing collection.")
        except Exception:
            pass

    collection = get_or_create_collection(client)

    if args.communities:
        # Index specific communities
        chunks = []
        data_dir = Path(args.data_dir)
        for slug in args.communities:
            filepath = data_dir / f"{slug}.json"
            if filepath.exists():
                community_chunks = chunk_community(filepath)
                chunks.extend(community_chunks)
                print(f"  Chunked {slug}: {len(community_chunks)} chunks")
            else:
                print(f"  ! {slug}.json not found in {data_dir}")
    else:
        # Index all
        chunks = chunk_all(args.data_dir)

    if chunks:
        count = index_chunks(collection, chunks, replace=True)
        communities = set(c["community"] for c in chunks)
        print(f"\nIndexed {count} chunks from {len(communities)} communities")
        print(f"Total in collection: {collection.count()}")
    else:
        print("No chunks to index.")


if __name__ == "__main__":
    main()
