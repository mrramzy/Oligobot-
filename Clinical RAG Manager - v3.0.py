# -*- coding: utf-8 -*-
"""
Oligosoft Clinical RAG Manager - v3.0 (Refactored)

Key upgrade:
- Smart index routing INSIDE manager
- Automatic decision: FAISS+Google vs Chroma+Local
- Clean separation of concerns
"""

import argparse
import os
import sys
import time
import shutil
import pickle
from pathlib import Path
import numpy as np
import PyPDF2

# 🔧 PATCH: Fix for NumPy 2.0 compatibility (ChromaDB issue)
if hasattr(np, 'float64') and not hasattr(np, 'float_'):
    np.float_ = np.float64
if hasattr(np, 'int64') and not hasattr(np, 'int_'):
    np.int_ = np.int64
if hasattr(np, 'uint64') and not hasattr(np, 'uint'):
    np.uint = np.uint64

# 🔧 PATCH: Fix for LangChain Core 0.3+ & Pydantic v2 compatibility
# This restores 'langchain_core.pydantic_v1' which was removed in newer versions
try:
    from langchain_core import pydantic_v1
except ImportError:
    import langchain_core
    try:
        from pydantic import v1 as pydantic_v1
    except ImportError:
        import pydantic as pydantic_v1
    
    # ✅ CRITICAL FIX: Inject into sys.modules to satisfy 'from langchain_core.pydantic_v1 import ...'
    sys.modules["langchain_core.pydantic_v1"] = pydantic_v1
    langchain_core.pydantic_v1 = pydantic_v1

# --- Existing engines ---
# ✅ Import ChromaDB engines from clinical_rag folder
try:
    from clinical_rag.ingest import build_db as build_chroma_db
    from clinical_rag.vision import build_image_db, ImageSearch
    from clinical_rag.retrieve import ClinicalRAG
except ImportError as e:
    print(f"⚠️ Error importing Chroma modules: {e}")
    build_chroma_db = None
    build_image_db = None

# --- FAISS engine (New Architecture) ---
from clinical_rag.faiss_ingest import ingest_book
from clinical_rag.merger_of_indexes import merge_and_save as merge_faiss_indexes
# --- ATLAS engine (Vision-to-Text image indexing) ---
from clinical_rag.atlas_ingest import ingest_atlas

# --- UI Utilities ---
try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm is not installed
    def tqdm(iterable, **kwargs): return iterable

# ---------------- CONFIG ----------------
KNOWLEDGE_BASE_DIR = "./knowledge_base"
CHROMA_PATH = "./chroma_clinical-v2"
VISION_PATH = "./chroma_vision"
# ✅ ALIGNED WITH async_rag_search.py
DOCUMENTS_DIR = KNOWLEDGE_BASE_DIR     # Staging area for PDFs (Unified)
FAISS_INDEX_DIR = "./brain_index"      # FAISS Output
CHROMA_BASE_DIR = "./vector_stores/chroma" # Chroma Output

# ANSI Colors for TUI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

# ---------------- ROUTER ----------------
def decide_index_engine(file_path: str) -> str:
    """Decide which index engine should ingest this file."""
    name = file_path.lower()
    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    # 🖼️ Atlas (image-heavy) → Vision-to-Text engine (caption images, index descriptions)
    if any(k in name for k in ["atlas", "rodak"]):
        return "ATLAS"

    # Explicit textbook detection → FAISS (text)
    if any(k in name for k in ["textbook", "tietz", "harrison", "henry", "hoffbrand"]):
        return "FAISS"

    # Guidelines / SOPs
    if any(k in name for k in ["guideline", "sop", "protocol", "clsi", "who"]):
        return "CHROMA"

    # Heuristic by size
    if size_mb > 50:
        return "FAISS"

    return "CHROMA"

# ---------------- MANAGER ACTIONS ----------------
def add_source(file_path: str, dry_run: bool = False):
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    engine = decide_index_engine(file_path)
    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    if dry_run:
        print("\n[DRY-RUN MODE]")
        print(f"File: {Path(file_path).name}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"Selected engine: {engine}")

        if engine == "ATLAS":
            print("Estimated impact:")
            print("  • Image-heavy atlas (Vision-to-Text)")
            print("  • One Arvan vision call per content page")
            print("  • Output: caption chunks in bge-m3 space + extracted images")
            print("  • Destination: ./knowledge_base/<atlas>/ → merged into ./brain_index")
        elif engine == "FAISS":
            print("Estimated impact:")
            print("  • Heavy textbook")
            print("  • High chunk count")
            print("  • Embedding cost: bge-m3 (Arvan)")
            print("  • Destination: ./brain_index")
        else:
            print("Estimated impact:")
            print("  • Lightweight guideline / SOP")
            print("  • Local embedding")
            print("  • Token cost: ~0")
            print("  • Destination: ./vector_stores/chroma")

        print("\nNo databases were modified.")
        return

    print(f"➕ Ingesting '{Path(file_path).name}' using [{engine}]")

    # Check if file is already inside KNOWLEDGE_BASE_DIR (recursive check)
    abs_file_path = os.path.abspath(file_path)
    abs_kb_dir = os.path.abspath(KNOWLEDGE_BASE_DIR)

    if abs_file_path.startswith(abs_kb_dir):
        # File is already in the knowledge base structure, use it directly
        dest_path = file_path
        print(f"📂 File is already in knowledge base: {dest_path}")
    else:
        # File is outside, copy to root of knowledge base
        dest_path = os.path.join(DOCUMENTS_DIR, Path(file_path).name)
        if not os.path.exists(DOCUMENTS_DIR):
            os.makedirs(DOCUMENTS_DIR)
        shutil.copy(file_path, dest_path)
        print(f"📂 Copied to staging: {dest_path}")

    if engine == "ATLAS":
        # 🖼️ Vision-to-Text: تصاویر اطلس کپشن‌گذاری و در همان فضای bge-m3 ایندکس می‌شوند.
        print("\n" + "-"*40)
        print("🖼️  ATLAS VISION-TO-TEXT INGESTION")
        print("-"*40)
        print("هر صفحه‌ی محتوایی: تصویر + متن → توصیف مورفولوژیک (آروان) → ایندکس متنی.")
        lim_raw = input(f"\n{CYAN}چند صفحه؟ (Enter = همه، یا عدد برای تستِ نمونه): {RESET}").strip()
        limit = int(lim_raw) if lim_raw.isdigit() else None
        ingest_atlas(dest_path, output_dir=KNOWLEDGE_BASE_DIR, limit=limit)
        merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)
        print("✅ Ingestion completed.")
        return

    if engine == "FAISS":
        print("\n" + "-"*40)
        print("⚙️  EXTRACTION STRATEGY SELECTION")
        print("-"*40)
        print("[1] ☁️  Full Online (LlamaParse) - Best Quality (Text+Tables via API)")
        print("[2] 🚀 Hybrid (Auto)           - Optimized (Local Text + Online Tables)")
        print("[3] 🏠 Local AI (Marker)       - High Quality Local (GPU required)")
        print("[4] ⚡ Local Fast (PyMuPDF)    - Text Only (No API cost)")
        
        m_choice = input(f"\n{CYAN}Select mode [1-4]: {RESET}").strip()
        mode_map = {'1': 'online', '2': 'local_marker', '3': 'local_fast', '4': 'auto'}
        mode_map = {'1': 'online', '2': 'auto', '3': 'local_marker', '4': 'local_fast'}
        selected_mode = mode_map.get(m_choice, 'auto')

        # 1. Ingest the specific book
        ingest_book(dest_path, output_dir=KNOWLEDGE_BASE_DIR, extraction_mode=selected_mode)
        
        # 2. Merge all indexes
        merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)
        
    else:
        if build_chroma_db:
            print(f"🔥 Updating Chroma DB with: {Path(dest_path).name}")
            build_chroma_db(single_file_path=dest_path)
        else:
            print("⚠️ Chroma builder script not linked yet.")

    print("✅ Ingestion completed.")


def rebuild_chroma():
    print("🔥 Rebuilding Chroma (text + vision)...")
    # Logic to clear CHROMA_BASE_DIR and rebuild
    print("⚠️ Feature pending integration with ingest.py")

    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
    if os.path.exists(VISION_PATH):
        shutil.rmtree(VISION_PATH)

    build_chroma_db()
    build_image_db()

    print("✅ Chroma rebuilt successfully.")


def list_sources():
    print("\n" + "="*50)
    print("      📂 KNOWLEDGE BASE INVENTORY      ")
    print("="*50)

    # 1. FAISS (Brain Index)
    print("\n🧠 [FAISS] Brain Index Contents (Merged Books):")
    index_pkl_path = os.path.join(FAISS_INDEX_DIR, "index.pkl")
    
    if os.path.exists(index_pkl_path):
        try:
            # Use SafeUnpickler for security (SEC-006)
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
            from async_rag_search import safe_pickle_load
            data = safe_pickle_load(index_pkl_path)
            
            if data is None:
                print("   ❌ Failed to load index.pkl (unsafe pickle rejected)")
            # LangChain FAISS format: (docstore, index_to_docstore_id)
            elif isinstance(data, tuple) and len(data) == 2:
                docstore = data[0]
                if hasattr(docstore, "_dict"):
                    docs = docstore._dict.values()
                    # Extract unique sources and count chunks per source
                    source_stats = {}
                    for doc in docs:
                        if hasattr(doc, "metadata"):
                            src = doc.metadata.get("source", "Unknown")
                            src_name = os.path.basename(src)
                            # Remove extension for cleaner look
                            src_name = os.path.splitext(src_name)[0]
                            source_stats[src_name] = source_stats.get(src_name, 0) + 1
                    
                    if not source_stats:
                        print("   (Index exists but no source metadata found)")
                    else:
                        for i, (src, count) in enumerate(sorted(source_stats.items()), 1):
                            print(f"   {i}. {src:<40} ({count} chunks)")
                else:
                    print("   (Unknown docstore format)")
            else:
                print("   (Unknown pickle format)")
        except Exception as e:
            print(f"   ❌ Error reading metadata: {e}")
    else:
        print(f"   ❌ No index.pkl found in {FAISS_INDEX_DIR}")

    # 2. ChromaDB (disabled — noted for reference)
    print("\n🔥 [Chroma] Collections (Guidelines/SOPs):")
    print("   (ChromaDB provider is currently disabled)")
    
    print("\n" + "="*50 + "\n")


def query_system(query_text: str):
    print(f"\n🔍 Query: {query_text}")
    rag = ClinicalRAG()
    results = rag.retrieve(query=query_text)
    print("Use the main bot interface for querying.")

    if not results:
        print("-- No results --")
        return

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] Score: {r['relevance_score']:.3f} | {r['source']} p.{r['page']}")
        print(r['text'][:400])


def search_image(image_path: str):
    searcher = ImageSearch()
    results = searcher.search(image_path)
    print("Use the main bot interface for image search.")

    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['source']} | Fig {r['figure_id']}")

def check_and_resume_checkpoints():
    """Checks for existing checkpoints and allows resuming."""
    clear_console()
    print_banner()
    print("\n--- 🔄 Resume Interrupted Ingestion ---")
    
    temp_dir = "temp_ingest"
    if not os.path.exists(temp_dir):
        print(f"\n{YELLOW}⚠️  No temporary ingestion folder found (temp_ingest).{RESET}")
        navigation_prompt()
        return

    checkpoints = [f for f in os.listdir(temp_dir) if f.endswith("_checkpoint.pkl")]
    
    if not checkpoints:
        print(f"\n{GREEN}✅ No interrupted sessions found.{RESET}")
        navigation_prompt()
        return

    print(f"\nFound {len(checkpoints)} interrupted sessions:\n")
    
    valid_resumes = []
    
    for i, ckpt in enumerate(checkpoints, 1):
        # Extract book name: "Tietz_checkpoint.pkl" -> "Tietz"
        book_name = ckpt.replace("_checkpoint.pkl", "")
        
        # Find original PDF
        found_pdf = None
        if os.path.exists(KNOWLEDGE_BASE_DIR):
            for root, _, files in os.walk(KNOWLEDGE_BASE_DIR):
                for file in files:
                    if os.path.splitext(file)[0] == book_name and file.lower().endswith(".pdf"):
                        found_pdf = os.path.join(root, file)
                        break
                if found_pdf: break
        
        if found_pdf:
            print(f"[{i}] {book_name} (Ready to resume)")
            valid_resumes.append((ckpt, found_pdf))
        else:
            print(f"[{i}] {book_name} (⚠️ Original PDF not found)")
            valid_resumes.append((ckpt, None))

    print(f"\n[0] Back to Menu")
    
    try:
        raw_choice = input(f"\n{CYAN}Select session to resume [1-{len(checkpoints)}]: {RESET}").strip()
        if raw_choice == '0': return
        choice = int(raw_choice)
        
        ckpt_file, pdf_path = valid_resumes[choice-1]
        
        print(f"\nSelected Session: {BOLD}{book_name}{RESET}")
        print(f"[1] ▶️  Resume Ingestion")
        print(f"[2] 🗑️  Delete Checkpoint")
        print(f"[0] Cancel")

        action = input(f"\n{CYAN}Select action: {RESET}").strip()

        if action == '1':
            if not pdf_path:
                print(f"\n{RED}❌ Cannot resume: Original PDF file is missing.{RESET}")
                navigation_prompt()
                return
                
            print(f"\n🚀 Resuming ingestion for: {os.path.basename(pdf_path)}")
            # We default to 'auto' because the checkpoint logic handles the rest, 
            # but calling ingest_book triggers the resume logic inside it.
            ingest_book(pdf_path, output_dir=KNOWLEDGE_BASE_DIR, extraction_mode="auto")
            
            # Merge after finish
            print(f"\n{CYAN}🔄 Updating Brain Index...{RESET}")
            merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)

        elif action == '2':
            confirm = input(f"\nAre you sure you want to delete this checkpoint? (y/n): ").lower()
            if confirm in ['y', 'yes']:
                try:
                    os.remove(os.path.join(temp_dir, ckpt_file))
                    print(f"\n{GREEN}✅ Checkpoint deleted successfully.{RESET}")
                except Exception as e:
                    print(f"\n{RED}❌ Error deleting file: {e}{RESET}")
            else:
                print("\nDeletion cancelled.")

    except (ValueError, IndexError):
        print("\n❌ Invalid selection.")
    
    navigation_prompt()

def remove_book_index():
    """Allows the architect to remove a specific reference (book/atlas) and re-merge."""
    clear_console()
    print_banner()
    print("\n--- 🗑️ Remove Reference (Undo Merge) ---")

    # هر مرجع = یک پوشه‌ی مینی‌ایندکس زیر knowledge_base که index.faiss دارد.
    # (پوشه‌های خامِ atlases/books/guidelines index.faiss ندارند و خودکار رد می‌شوند.)
    candidates = []
    if os.path.exists(KNOWLEDGE_BASE_DIR):
        for d in sorted(os.listdir(KNOWLEDGE_BASE_DIR)):
            folder = os.path.join(KNOWLEDGE_BASE_DIR, d)
            if os.path.isdir(folder) and os.path.exists(os.path.join(folder, "index.faiss")):
                candidates.append(folder)

    if not candidates:
        print(f"\n{RED}❌ No individual reference indexes found in {KNOWLEDGE_BASE_DIR}.{RESET}")
        navigation_prompt()
        return

    print(f"\nFound {len(candidates)} references. Deleting one removes it from the Brain after re-merge.\n")

    for i, folder in enumerate(candidates, 1):
        name = os.path.basename(folder)
        try:
            faiss_mb = os.path.getsize(os.path.join(folder, "index.faiss")) / (1024 * 1024)
        except OSError:
            faiss_mb = 0.0
        print(f"[{i}] {name:<55} ({faiss_mb:.2f} MB)")

    print(f"\n[0] Back to Menu")
    print(f"[X] Exit Program")

    raw_choice = input(f"\n{CYAN}Select reference [1-{len(candidates)}] or option: {RESET}").strip().lower()

    if raw_choice == 'x': sys.exit(0)
    if raw_choice == '0' or raw_choice == 'b': return

    try:
        choice = int(raw_choice)
        target_folder = candidates[choice - 1]
    except (ValueError, IndexError):
        print("\n❌ Invalid selection.")
        navigation_prompt()
        return

    name = os.path.basename(target_folder)
    print(f"\n{YELLOW}⚠️  You are about to delete the entire reference folder:{RESET}")
    print(f"   - {target_folder}")
    print(f"{RED}   This removes '{name}' from the Brain Index (FAISS + BM25 + chunks).{RESET}")

    confirm = input(f"\nAre you sure? (yes/no): ").lower()
    if confirm not in ['y', 'yes']:
        print("\n❌ Operation cancelled.")
        navigation_prompt()
        return

    try:
        shutil.rmtree(target_folder)
        print(f"\n{GREEN}✅ Reference folder deleted.{RESET}")
    except Exception as e:
        print(f"\n{RED}❌ Failed to delete folder: {e}{RESET}")
        navigation_prompt()
        return

    # Re-merge (merge_and_save خودش BM25های قدیمیِ brain_index را پاک و بازسازی می‌کند)
    print(f"\n{CYAN}🔄 Re-merging remaining references to update Brain...{RESET}")
    merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)
    print(f"\n{BOLD}✅ Brain Index updated successfully.{RESET}")

    navigation_prompt()

def tui_partial_ingest():
    """Allows the user to slice a PDF and ingest only specific chapters."""
    clear_console()
    print_banner()
    print("\n--- ✂️ Partial Ingestion (Chapter Selection) ---")
    
    files = get_files_in_kb()
    if not files:
        print(f"\n{RED}❌ No files found in knowledge base.{RESET}")
        navigation_prompt()
        return

    print("\nSelect a book to slice:")
    for i, f in enumerate(files, 1):
        print(f"[{i}] {f}")
    
    print(f"\n[0] Back to Menu")
    print(f"[X] Exit Program")
    
    raw_choice = input(f"\n{CYAN}Select file [1-{len(files)}] or option: {RESET}").strip().lower()
    if raw_choice == 'x': sys.exit(0)
    if raw_choice == '0' or raw_choice == 'b': return
    try:
        choice = int(raw_choice)
        target_file = os.path.join(KNOWLEDGE_BASE_DIR, files[choice-1])
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        time.sleep(1)
        return

    print(f"\nSelected: {BOLD}{os.path.basename(target_file)}{RESET}")
    
    # Pre-check file info to show total pages
    try:
        reader_preview = PyPDF2.PdfReader(target_file)
        print(f"   📄 Total PDF Pages: {BOLD}{len(reader_preview.pages)}{RESET}")
    except Exception:
        pass

    print("-" * 60)
    print(f"{YELLOW}⚠️  CRITICAL: PAGE NUMBERING{RESET}")
    print("   The system works with **PDF Page Numbers** (Absolute Count).")
    print("   This is the number shown in your PDF viewer's toolbar (e.g., 120 of 3000).")
    print("   It is NOT the page number printed on the footer of the book page.")
    print("-" * 60)
    print("Enter page ranges to extract (e.g., '10-50, 100-120').")
    
    ranges_input = input(f"\n{CYAN}Page Ranges: {RESET}").strip()
    
    try:
        # Parse ranges
        ranges = []
        parts = ranges_input.split(',')
        for part in parts:
            start, end = map(int, part.split('-'))
            ranges.append((start, end))
        
        # Process PDF
        reader = PyPDF2.PdfReader(target_file)
        writer = PyPDF2.PdfWriter()
        
        total_pages = len(reader.pages)
        print(f"\nProcessing {total_pages} pages...")
        
        for start, end in ranges:
            # Adjust for 0-based index, but keep user input logic (1-based) usually expected
            # Let's assume user inputs 1-based page numbers
            for i in range(start - 1, end):
                if 0 <= i < total_pages:
                    writer.add_page(reader.pages[i])
        
        # Save new file
        base_name = os.path.splitext(os.path.basename(target_file))[0]
        new_filename = f"{base_name}_selected_p{ranges_input.replace(',','_').replace(' ','')}.pdf"
        output_path = os.path.join(KNOWLEDGE_BASE_DIR, new_filename)
        
        with open(output_path, "wb") as f:
            writer.write(f)
            
        print(f"\n{GREEN}✅ Created partial PDF: {new_filename}{RESET}")
        
    except Exception as e:
        print(f"\n{RED}❌ Error slicing PDF: {e}{RESET}")
        navigation_prompt()
        return
    
    # Ask to ingest immediately (Outside try/except to avoid misleading error messages)
    confirm = input(f"\nDo you want to ingest this new file now? (y/n): ").lower()
    if confirm == 'y':
        add_source(output_path)

    navigation_prompt()

# ---------------- TUI (Terminal UI) ----------------
def navigation_prompt():
    print("\n" + "-"*40)
    choice = input(f"{CYAN}[Enter] Back to Menu{RESET} | {RED}[X] Exit{RESET}: ").strip().lower()
    if choice == 'x':
        print("Bye! 👋")
        sys.exit(0)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    print(CYAN + "="*60 + RESET)
    print(BOLD + "      🏥 OLIGOBOT CLINICAL RAG MANAGER - V3.0 (TUI)      " + RESET)
    print(CYAN + "="*60 + RESET)

def get_files_in_kb():
    if not os.path.exists(KNOWLEDGE_BASE_DIR):
        return []
    
    pdf_files = []
    for root, _, files in os.walk(KNOWLEDGE_BASE_DIR):
        for file in files:
            if file.lower().endswith('.pdf'):
                # Return relative path so it displays nicely (e.g., "books/Tietz.pdf")
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, KNOWLEDGE_BASE_DIR)
                pdf_files.append(rel_path)
    return pdf_files

def tui_scan():
    clear_console()
    print_banner()
    files = get_files_in_kb()
    print(f"\n📂 Found {len(files)} PDF files in '{KNOWLEDGE_BASE_DIR}':\n")
    
    print(f"{'Filename':<40} | {'Size (MB)':<10} | {'Engine':<10}")
    print("-" * 70)
    
    for f in files:
        path = os.path.join(KNOWLEDGE_BASE_DIR, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        engine = decide_index_engine(path)
        
        color = GREEN if engine == "CHROMA" else YELLOW
        print(f"{f[:37]+'...' if len(f)>37 else f:<40} | {size_mb:<10.2f} | {color}{engine}{RESET}")
    
    navigation_prompt()

def tui_auto_ingest():
    clear_console()
    print_banner()
    files = get_files_in_kb()
    if not files:
        print(RED + "❌ No files found in knowledge base." + RESET)
        time.sleep(2)
        return

    print(f"🚀 Starting Auto-Ingestion for {len(files)} files...\n")
    
    faiss_updates = False
    chroma_updates = False
    
    # Progress Bar Loop
    pbar = tqdm(files, desc="Processing", unit="file")
    
    for f in pbar:
        path = os.path.join(KNOWLEDGE_BASE_DIR, f)
        engine = decide_index_engine(path)
        pbar.set_description(f"Processing: {f[:15]}.. [{engine}]")

        try:
            if engine == "ATLAS":
                # 🖼️ Vision-to-Text atlas ingestion (full)
                ingest_atlas(path, output_dir=KNOWLEDGE_BASE_DIR)
                faiss_updates = True
            elif engine == "FAISS":
                # Ingest specific book
                ingest_book(path, output_dir=KNOWLEDGE_BASE_DIR)
                faiss_updates = True
            else:
                # Mark Chroma for update (Chroma rebuilds in bulk)
                chroma_updates = True
        except Exception as e:
            print(f"\n{RED}❌ Error processing {f}: {e}{RESET}")
    
    print("\n✅ Individual file processing complete.")
    
    if faiss_updates:
        print(f"\n{YELLOW}🧠 Merging FAISS indexes...{RESET}")
        merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)
    
    if chroma_updates:
        print(f"\n{GREEN}🔥 Rebuilding Chroma DB (Bulk)...{RESET}")
        rebuild_chroma()
        
    print(f"\n{BOLD}🎉 All tasks finished successfully.{RESET}")
    navigation_prompt()

def interactive_mode():
    while True:
        clear_console()
        print_banner()
        print("\n[1] 📂 Scan Knowledge Base (Status & Recommendations)")
        print("[2] 🚀 Start Auto-Indexing (Process All)")
        print("[3] 🛠️  Manual Ingestion (Pick a file)")
        print("[4] 🔄 Rebuild Chroma DB (Force)")
        print("[5] 🧠 Merge FAISS Indexes (Force)")
        print("[6] 🗑️ Remove a Book Index (Undo)")
        print("[7] 📜 List Indexed Content (Inventory)")
        print("[8] ✂️ Partial Ingestion (Specific Chapters)")
        print("[9] 🔄 Resume Interrupted Ingestion")
        print("[10] 🚪 Exit")
        
        choice = input(f"\n{CYAN}Select an option [1-10]: {RESET}").strip()
        
        if choice == '1': tui_scan()
        elif choice == '2': tui_auto_ingest()
        elif choice == '3':
            files = get_files_in_kb()
            if not files: continue
            print("\nAvailable files:")
            for i, f in enumerate(files, 1): print(f"{i}. {f}")
            try:
                idx = int(input("\nSelect file number: ")) - 1
                if 0 <= idx < len(files):
                    add_source(os.path.join(KNOWLEDGE_BASE_DIR, files[idx]))
                    input("Press Enter...")
            except ValueError: pass
        elif choice == '4':
            rebuild_chroma()
            input("Press Enter...")
        elif choice == '5':
            merge_faiss_indexes(output_dir=FAISS_INDEX_DIR)
            input("Press Enter...")
        elif choice == '6':
            remove_book_index()
        elif choice == '7':
            list_sources()
            input("Press Enter...")
        elif choice == '8':
            tui_partial_ingest()
        elif choice == '9':
            check_and_resume_checkpoints()
        elif choice == '10':
            print("Bye! 👋")
            sys.exit(0)

# ---------------- CLI ----------------
def main():
    # If no arguments provided, launch Interactive TUI
    if len(sys.argv) == 1:
        interactive_mode()
        return

    parser = argparse.ArgumentParser("Clinical RAG Manager v3")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("rebuild_chroma")
    sub.add_parser("list")

    add_p = sub.add_parser("add")
    add_p.add_argument("file_path")
    add_p.add_argument("--dry-run", action="store_true", help="Simulate ingestion without modifying databases")

    q = sub.add_parser("query")
    q.add_argument("text")

    img = sub.add_parser("search_image")
    img.add_argument("image_path")

    args = parser.parse_args()

    if args.cmd == "rebuild_chroma":
        rebuild_chroma()
    elif args.cmd == "list":
        list_sources()
    elif args.cmd == "add":
        add_source(args.file_path, dry_run=args.dry_run)
    elif args.cmd == "query":
        query_system(args.text)
    elif args.cmd == "search_image":
        search_image(args.image_path)


if __name__ == "__main__":
    main()
