import os
import sys
import re
from datetime import datetime

# Add parent directory to sys.path to allow importing modules from the parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path
from collections import defaultdict
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np

# 🔧 PATCH: Fix for NumPy 2.0 compatibility (ChromaDB issue)
if hasattr(np, 'float64') and not hasattr(np, 'float_'):
    np.float_ = np.float64
if hasattr(np, 'int64') and not hasattr(np, 'int_'):
    np.int_ = np.int64
if hasattr(np, 'uint64') and not hasattr(np, 'uint'):
    np.uint = np.uint64

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.html import partition_html

# NEW: Import the citation manager
from citation_manager import CitationManager

# ------------------ Settings ------------------
KNOWLEDGE_BASE_DIR = "./knowledge_base"
CHROMA_PATH = "./chroma_clinical_v2"
EMBED_MODEL = "BAAI/bge-m3"

def parse_filename_to_metadata(filename: str) -> dict:
    """Extracts metadata from a filename, with fallback for non-standard names."""
    stem = Path(filename).stem
    parts = stem.split("_")
    
    # 1. Try Strict Format (Domain_Subdomain_TestName_Source_Year)
    if len(parts) >= 5 and parts[-1].isdigit() and len(parts[-1]) == 4:
        try:
            domain, subdomain, test_name, source, year = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            content_type = "guideline" if "guideline" in filename.lower() else "sop"
            audience_map = {
                "MOH": ["lab_technician", "clinician"],
                "Harrison": ["medical_student", "resident"],
                "CLSI": ["lab_technician", "pathologist"]
            }
            audience = audience_map.get(source, ["lab_technician"])

            return {
                "domain": domain, "subdomain": subdomain, "test_name": test_name.replace("-", " "),
                "content_type": content_type, "target_audience": audience,
                "language": "fa" if "fa" in filename.lower() else "en",
                "source": source, "year": int(year),
                "is_diagnostic": domain in ["microbiology", "hematology", "clinical_biochemistry"],
                "educational_level": "intermediate"
            }
        except Exception:
            pass # Fallback to heuristic

    # 2. Heuristic Fallback (Smart Auto-Detection)
    print(f"⚠️ Non-standard filename detected: '{filename}'. Using heuristic metadata extraction.")
    
    stem_lower = stem.lower()
    
    # Extract Year
    year_match = re.search(r'\b(19|20)\d{2}\b', stem)
    year = int(year_match.group(0)) if year_match else datetime.now().year

    # Detect Source
    source = "Unknown"
    if "who" in stem_lower: source = "WHO"
    elif "cdc" in stem_lower: source = "CDC"
    elif "clsi" in stem_lower: source = "CLSI"
    elif "moh" in stem_lower: source = "MOH"
    elif "fda" in stem_lower: source = "FDA"
    
    # Detect Content Type
    content_type = "document"
    if "guideline" in stem_lower: content_type = "guideline"
    elif "sop" in stem_lower: content_type = "sop"
    elif "protocol" in stem_lower: content_type = "protocol"

    # Detect Domain (Simple keywords)
    domain = "General"
    if any(x in stem_lower for x in ["heme", "blood", "iron", "ferritin", "cbc", "anemia"]): domain = "Hematology"
    elif any(x in stem_lower for x in ["chem", "glucose", "liver", "kidney", "enzyme"]): domain = "Clinical Biochemistry"
    elif any(x in stem_lower for x in ["micro", "bact", "virus", "culture"]): domain = "Microbiology"
    elif any(x in stem_lower for x in ["urine", "renal"]): domain = "Urinalysis"

    return {
        "domain": domain,
        "subdomain": "General",
        "test_name": stem.replace("_", " "), # Use filename as title
        "content_type": content_type,
        "target_audience": ["clinician", "lab_technician"],
        "language": "fa" if "fa" in stem_lower or any(c > '\u0600' for c in stem) else "en",
        "source": source,
        "year": year,
        "is_diagnostic": False,
        "educational_level": "intermediate"
    }


def load_and_chunk(target_file=None):
    """Loads documents, chunks them, and filters for plagiarism risk."""
    docs = []
    
    # Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", ". ", "• ", ";"],
        is_separator_regex=False
    )
    
    # NEW: Initialize the Citation Manager to check for plagiarism
    citation_manager = CitationManager()

    if target_file:
        files_to_process = [Path(target_file)]
    else:
        files_to_process = Path(KNOWLEDGE_BASE_DIR).rglob('*')

    for file_path in files_to_process:
        if not file_path.is_file():
            continue

        try:
            base_meta = parse_filename_to_metadata(file_path.name)
        except Exception as e:
            print(f"⚠️ Skipping file with invalid name format: {file_path.name} -> {e}")
            continue

        if file_path.suffix == ".pdf":
            try:
                # Try Hi-Res first (Better for tables, requires Poppler)
                elements = partition_pdf(str(file_path), strategy="hi_res")
            except Exception:
                # Fallback to Fast (Standard text extraction, no Poppler needed)
                print(f"⚠️ Poppler not found. Falling back to 'fast' strategy for: {file_path.name}")
                elements = partition_pdf(str(file_path), strategy="fast")
        elif file_path.suffix == ".html":
            elements = partition_html(str(file_path))
        else:
            continue

        content_by_page = defaultdict(list)
        for element in elements:
            page_num = element.metadata.page_number
            # Ensure there is always a page number key
            page_key = page_num if page_num is not None else 1
            content_by_page[page_key].append(str(element))

        for page_num, page_content_list in content_by_page.items():
            page_text = "\n\n".join(page_content_list)
            chunks = text_splitter.split_text(page_text)
            
            for i, chunk in enumerate(chunks):
                # Only process meaningful chunks
                if len(chunk) < 100:
                    continue

                chunk_meta = base_meta.copy()
                chunk_meta["page"] = page_num
                docs.append(Document(page_content=chunk, metadata=chunk_meta))
                
    return docs

def build_db(single_file_path=None):
    """Builds and persists the ChromaDB vector store."""
    docs = load_and_chunk(single_file_path)
    if not docs:
        print("No documents were processed. Make sure files are in the knowledge base and named correctly.")
        return
        
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL, model_kwargs={"device": "cpu"})
    
    # Ensure the target directory exists
    os.makedirs(CHROMA_PATH, exist_ok=True)
    
    db = Chroma.from_documents(docs, embeddings, persist_directory=CHROMA_PATH)
    db.persist()
    print(f"✅ Database built successfully: {len(docs)} chunks stored in {CHROMA_PATH}")

if __name__ == "__main__":
    build_db()
