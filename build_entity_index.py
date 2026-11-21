# -*- coding: utf-8 -*-
"""
Build entity index from existing knowledge base chunks.
Loads chunks from FAISS index.pkl and extracts medical entities.
"""
import sys
import os
import json

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from entity_extractor import EntityExtractor
from async_rag_search import safe_pickle_load


def load_chunks_from_index(index_path: str) -> list:
    """Load document chunks from FAISS index.pkl using safe pickle loading."""
    data = safe_pickle_load(index_path)
    if data is None:
        print(f"  ⚠️ Failed to load {index_path}")
        return []

    chunks = []

    # Handle langchain FAISS tuple format: (InMemoryDocstore, {index: doc_id})
    if isinstance(data, tuple) and len(data) == 2:
        docstore = data[0]
        # Access internal _dict of InMemoryDocstore
        if hasattr(docstore, '_dict'):
            docs = docstore._dict
            for doc_id, doc in docs.items():
                if hasattr(doc, 'page_content'):
                    chunks.append({
                        "content": doc.page_content,
                        "metadata": getattr(doc, 'metadata', {})
                    })
            print(f"  Extracted {len(chunks)} chunks from InMemoryDocstore._dict")
            return chunks

    if isinstance(data, dict):
        # Could be langchain format with 'docstore' or 'documents'
        docs = data.get('documents') or data.get('docstore') or []
        if hasattr(docs, '_dict'):
            docs = docs._dict
        elif hasattr(docs, 'dict'):
            docs = list(docs.dict().values()) if hasattr(docs, 'dict') else list(docs)
        elif isinstance(docs, dict):
            docs = list(docs.values())
        for doc in docs:
            if hasattr(doc, 'page_content'):
                chunks.append({
                    "content": doc.page_content,
                    "metadata": getattr(doc, 'metadata', {})
                })
            elif isinstance(doc, dict):
                chunks.append({
                    "content": doc.get('content') or doc.get('page_content', ''),
                    "metadata": doc.get('metadata', {})
                })
    elif isinstance(data, list):
        for item in data:
            if hasattr(item, 'page_content'):
                chunks.append({
                    "content": item.page_content,
                    "metadata": getattr(item, 'metadata', {})
                })
            elif isinstance(item, dict):
                chunks.append({
                    "content": item.get('content') or item.get('page_content', ''),
                    "metadata": item.get('metadata', {})
                })

    return chunks


def main():
    print("=" * 60)
    print("  Building Entity Index from Knowledge Base")
    print("=" * 60)

    ext = EntityExtractor(storage_path="entity_index.json")

    # Load chunks from all FAISS indexes
    index_dir = "brain_index"
    all_chunks = []

    # Load from main index.pkl
    main_index = os.path.join(index_dir, "index.pkl")
    if os.path.exists(main_index):
        print(f"\nLoading chunks from {main_index}...")
        chunks = load_chunks_from_index(main_index)
        print(f"  Loaded {len(chunks)} chunks")
        all_chunks.extend(chunks)

    # Build entity index
    print(f"\nExtracting entities from {len(all_chunks)} chunks...")
    ext.build_index_from_chunks(all_chunks, source="knowledge_base")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Entity Index Summary")
    print(f"{'=' * 60}")
    print(f"  Total entities: {len(ext.entities)}")
    print(f"  Total relationships: {len(ext.relationships)}")

    # Category breakdown
    categories = {}
    for ent in ext.entities.values():
        cat = ent["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n  By category:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    print(f"\n  Entity index saved to: {ext.storage_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
