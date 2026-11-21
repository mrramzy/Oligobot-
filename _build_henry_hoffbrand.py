# -*- coding: utf-8 -*-
"""
اسکریپت موقت: ساخت ایندکس هنری + هافبراند با امبدینگ جدید (bge-m3 روی آروان).
- ingest هر کتاب با faiss_ingest (حالت local_fast / fitz) → knowledge_base/<book>/ (index + chunks.jsonl + bm25)
- ادغام کنترل‌شده‌ی *فقط همین دو کتاب* در brain_index/ (برای جلوگیری از crash روی پوشه‌های دیگر)
"""
import os
import sys
import shutil
import time

os.environ.setdefault("PYTHONUTF8", "1")

from clinical_rag.faiss_ingest import ingest_book, BM25_FILENAME, sanitize_ascii_name
from langchain_community.vectorstores import FAISS
from embeddings import get_rag_embeddings

KB = "knowledge_base"
BRAIN = "brain_index"

BOOKS = [
    os.path.join(KB, "books", "Henry’s clinical diagnosis and management by laboratory 24th edition.pdf"),
    os.path.join(KB, "books", "Hoffbrand's Postgraduate Haematology 8th edition.pdf"),
]


def main():
    t_start = time.time()
    built_folders = []

    for pdf in BOOKS:
        if not os.path.exists(pdf):
            print(f"❌ پیدا نشد: {pdf}", flush=True)
            continue
        book_name = os.path.splitext(os.path.basename(pdf))[0]
        print(f"\n{'='*70}\n\U0001f4d6 INGEST: {book_name}\n{'='*70}", flush=True)
        t0 = time.time()
        ingest_book(pdf, output_dir=KB, extraction_mode="local_fast")
        print(f"⏱️  {book_name}: {(time.time()-t0)/60:.1f} min", flush=True)
        folder = os.path.join(KB, sanitize_ascii_name(book_name))
        if os.path.exists(os.path.join(folder, "index.faiss")):
            built_folders.append(folder)
        else:
            print(f"⚠️ index.faiss ساخته نشد برای: {folder}", flush=True)

    if not built_folders:
        print("❌ هیچ ایندکسی ساخته نشد.", flush=True)
        return

    # --- ادغام کنترل‌شده‌ی فقط همین دو کتاب ---
    print(f"\n\U0001f517 ادغام {len(built_folders)} کتاب در {BRAIN}/ ...", flush=True)
    emb = get_rag_embeddings()
    merged = FAISS.load_local(built_folders[0], emb, allow_dangerous_deserialization=True)
    for folder in built_folders[1:]:
        sub = FAISS.load_local(folder, emb, allow_dangerous_deserialization=True)
        merged.merge_from(sub)

    # پاک‌کردن brain_index قدیمی (۷۶۸بعدی) و ذخیره‌ی جدید
    if os.path.exists(BRAIN):
        for f in os.listdir(BRAIN):
            fp = os.path.join(BRAIN, f)
            if os.path.isfile(fp):
                os.remove(fp)
    else:
        os.makedirs(BRAIN)
    merged.save_local(BRAIN, "index")
    print(f"✅ brain_index ذخیره شد | dim={merged.index.d} ntotal={merged.index.ntotal}", flush=True)

    # کپی BM25 هر کتاب به brain_index
    for folder in built_folders:
        src = os.path.join(folder, BM25_FILENAME)
        if os.path.exists(src):
            base = os.path.basename(folder)
            dst = os.path.join(BRAIN, f"bm25_retriever_{base}.pkl")
            shutil.copy(src, dst)
            print(f"   \U0001f4c4 BM25 کپی شد: {base}", flush=True)

    print(f"\n\U0001f389 تمام در {(time.time()-t_start)/60:.1f} دقیقه.", flush=True)


if __name__ == "__main__":
    main()
