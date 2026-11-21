
# -*- coding: utf-8 -*-
"""
Oligosoft Clinical RAG Manager - v2.1

Command-line interface for managing the advanced clinical RAG knowledge base,
now with integrated multi-modal (text + image) capabilities.

Updates in v2.1:
- New `search_image` command to test vision search.
- `rebuild` command now builds both text and image databases.
- File paths and structures updated to `knowledge_base` directory.
"""
import argparse
import os
import shutil
from clinical_rag.ingest import build_db as build_text_db
from clinical_rag.vision import build_image_db, ImageSearch
from clinical_rag.retrieve import ClinicalRAG

# The root directory for all source materials
KNOWLEDGE_BASE_DIR = "./knowledge_base"

def add_source(file_path: str):
    """Ingests a single new document or image into the knowledge base."""
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found at '{file_path}'")
        return

    print(f"➕ Ingesting new source: {os.path.basename(file_path)}")
    # For simplicity, we trigger a full rebuild. A more optimized approach
    # would be to add just the single file to the corresponding DB.
    rebuild_database()
    print("✅ Ingestion complete.")

def list_sources():
    """Lists all documents currently in the TEXT vector store."""
    print("\n--- 📚 Indexed Textual Sources (from ChromaDB) ---")
    try:
        rag = ClinicalRAG()
        results = rag.vectorstore.get()
        if not results or not results.get('ids'):
            print("   [Empty] The text knowledge base is empty.")
            return

        sources = { (m.get('source'), m.get('year')) for m in results.get('metadatas', []) }
        print(f"Total unique text sources found: {len(sources)}\n")
        for i, (source, year) in enumerate(sorted(sources), 1):
            print(f"{i}. {source} ({year})")
        print("\n" + "="*50 + "\n")

    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {e}")

def rebuild_database():
    """Clears and rebuilds BOTH the text and image databases."""
    print("🔥 Rebuilding the entire multi-modal knowledge base...")
    
    # --- Text Database ---
    print("\n  (1/2) Processing Textual Sources...")
    if os.path.exists("./chroma_clinical_v2"):
        print("    - Deleting old text database...")
        shutil.rmtree("./chroma_clinical_v2")
    build_text_db()
    
    # --- Image Database ---
    print("\n  (2/2) Processing Visual Sources (Atlases)...")
    if os.path.exists("./chroma_vision"):
        print("    - Deleting old image database...")
        shutil.rmtree("./chroma_vision")
    build_image_db()

    print("\n✅ All databases rebuilt successfully!")

def query_system(query_text: str):
    """Performs a test query using the ClinicalRAG text system."""
    # (Implementation remains the same as before)
    print(f"\n🔍 Running text query: '{query_text}'")
    try:
        rag = ClinicalRAG()
        results = rag.retrieve(query=query_text)
        if not results: return print("\n-- No relevant results found. --")
        print("\n🎯 Top Text Results (after re-ranking):")
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] (Score: {r['relevance_score']:.3f}) | Source: {r['source']}, p. {r['page']} ({r['year']})")
            print(f"   Text: {r['text'][:350]}...")
    except Exception as e: print(f"❌ Error during query: {e}")

def search_image_system(image_path: str):
    """Performs a test similarity search using the vision system."""
    if not os.path.exists(image_path):
        return print(f"❌ Error: Query image not found at '{image_path}'")
    
    print(f"\n🖼️ Searching for images similar to '{os.path.basename(image_path)}'...")
    try:
        searcher = ImageSearch()
        results = searcher.search(image_path)
        if not results: return print("\n-- No similar images found. --")
        print("\n🎯 Top Image Results:")
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] Source: {r['source']} (Figure: {r['figure_id']}) | Domain: {r['domain']}")
            print(f"   Path: {r['path']}")
    except Exception as e: print(f"❌ Error during image search: {e}")


def main():
    parser = argparse.ArgumentParser(description="Oligosoft Clinical RAG Manager v2.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Rebuild, List, Add, Query (Text)
    subparsers.add_parser("rebuild", help="Rebuild all text and image databases.")
    subparsers.add_parser("list", help="List all unique sources in the text knowledge base.")
    add_parser = subparsers.add_parser("add", help="Add a source file (triggers a full rebuild).")
    add_parser.add_argument("file_path", type=str, help="Path to the document/image file.")
    query_parser = subparsers.add_parser("query", help="Run a test query on the text RAG system.")
    query_parser.add_argument("text", type=str, help="The query text.")

    # Search (Image)
    img_search_parser = subparsers.add_parser("search_image", help="Find similar images in the atlas database.")
    img_search_parser.add_argument("image_path", type=str, help="Path to the query image.")

    args = parser.parse_args()

    if args.command == "rebuild": rebuild_database()
    elif args.command == "list": list_sources()
    elif args.command == "add": add_source(args.file_path)
    elif args.command == "query": query_system(args.text)
    elif args.command == "search_image": search_image_system(args.image_path)

if __name__ == "__main__":
    main()
