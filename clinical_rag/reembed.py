# -*- coding: utf-8 -*-
"""
🧬 Re-Embed Tool — بازسازی ایندکس از روی چانک‌های خام (بدون پارس مجدد PDF)

چرا: مرحله‌ی گران/کند در ساخت ایندکس، «پارس PDF» است (LlamaParse/Marker/Fitz).
faiss_ingest.py چانک‌های خام هر کتاب را در knowledge_base/<book>/chunks.jsonl ذخیره می‌کند.
این اسکریپت همان چانک‌ها را می‌خواند و فقط دوباره embed می‌کند → ایندکس را با مدلِ فعلیِ
config (EMBEDDING_PROVIDER) از نو می‌سازد.

کاربرد اصلی: وقتی مدل امبدینگ عوض شد (مثلاً bge-m3 → مدل جدیدتر).
    1) در .env مقدار EMBEDDING_PROVIDER (یا ARVAN_EMBEDDING_MODEL) را عوض کن.
    2) python -m clinical_rag.reembed
بازسازی کل کتابخانه چند دقیقه طول می‌کشد، بدون لمس PDFها.

نکته: chunks.jsonl همه‌ی metadata (source/page/type/...) را حفظ می‌کند،
پس آدرس‌دهی صفحه (citation) دقیقاً مثل ساخت اصلی باقی می‌ماند.
"""
import os
import sys
import json
import glob
import pickle

# مسیر ریشه‌ی پروژه برای import ماژول‌های بالادست
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from embeddings import get_rag_embeddings
from clinical_rag.merger_of_indexes import merge_and_save

KNOWLEDGE_BASE_DIR = "knowledge_base"
BRAIN_INDEX_DIR = "brain_index"
CHUNKS_FILENAME = "chunks.jsonl"
BM25_FILENAME = "bm25_retriever.pkl"
BATCH_SIZE = 100


def load_chunks(jsonl_path: str):
    """خواندن چانک‌های خام یک کتاب از chunks.jsonl → لیست Document."""
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            docs.append(Document(
                page_content=rec["page_content"],
                metadata=rec.get("metadata", {}),
            ))
    return docs


def reembed_book(book_dir: str, embeddings) -> bool:
    """بازسازی FAISS + BM25 یک کتاب از روی chunks.jsonl آن."""
    chunks_path = os.path.join(book_dir, CHUNKS_FILENAME)
    if not os.path.exists(chunks_path):
        print(f"   ⏭️  رد شد (chunks.jsonl ندارد): {os.path.basename(book_dir)}")
        return False

    docs = load_chunks(chunks_path)
    if not docs:
        print(f"   ⚠️ خالی: {os.path.basename(book_dir)}")
        return False

    print(f"   🔄 {os.path.basename(book_dir)} — {len(docs)} چانک")

    # 1. FAISS (embed دسته‌ای داخل get_rag_embeddings انجام می‌شود)
    vector_store = None
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        if vector_store is None:
            vector_store = FAISS.from_documents(batch, embedding=embeddings)
        else:
            vector_store.add_documents(batch)
    vector_store.save_local(book_dir)

    # 2. BM25
    try:
        retriever_bm25 = BM25Retriever.from_documents(docs)
        retriever_bm25.k = 5
        with open(os.path.join(book_dir, BM25_FILENAME), "wb") as f:
            pickle.dump(retriever_bm25, f)
    except Exception as e:
        print(f"   ⚠️ BM25 ساخته نشد: {e}")

    return True


def reembed_all():
    """بازسازی کل کتابخانه از روی chunks.jsonl + ادغام در brain_index."""
    from config import EMBEDDING_PROVIDER, EMBEDDING_DIM
    print(f"🧬 Re-Embed با provider={EMBEDDING_PROVIDER} (dim={EMBEDDING_DIM})")

    if not os.path.exists(KNOWLEDGE_BASE_DIR):
        print(f"❌ مسیر {KNOWLEDGE_BASE_DIR} یافت نشد.")
        return

    # هر پوشه‌ای که chunks.jsonl دارد یک کتاب است
    book_dirs = sorted(
        os.path.dirname(p) for p in glob.glob(
            os.path.join(KNOWLEDGE_BASE_DIR, "**", CHUNKS_FILENAME), recursive=True
        )
    )
    if not book_dirs:
        print(f"❌ هیچ {CHUNKS_FILENAME} پیدا نشد. اول کتاب‌ها را با faiss_ingest بساز.")
        return

    print(f"📚 {len(book_dirs)} کتاب با چانک خام پیدا شد.")
    embeddings = get_rag_embeddings()

    rebuilt = 0
    for book_dir in book_dirs:
        if reembed_book(book_dir, embeddings):
            rebuilt += 1

    print(f"\n✅ {rebuilt}/{len(book_dirs)} کتاب بازسازی شد.")

    # ادغام نهایی در brain_index (همان مسیری که ربات می‌خواند)
    if rebuilt:
        print("🔗 ادغام در brain_index...")
        merge_and_save(output_dir=BRAIN_INDEX_DIR)
        print("🎉 تمام — ایندکس با مدل جدید آماده است.")


if __name__ == "__main__":
    reembed_all()
