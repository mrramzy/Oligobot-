# -*- coding: utf-8 -*-
"""
🏗️ Local Index Builder
این اسکریپت فایل‌های PDF را خوانده و ایندکس FAISS آفلاین (Local) می‌سازد.
مدل استفاده شده: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
"""

import os
import glob
from typing import List
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# تنظیمات
DOCS_DIR = "knowledge_base"      # پوشه حاوی فایل‌های PDF
INDEX_DIR = "brain_index"        # پوشه خروجی ایندکس
INDEX_NAME = "index_local"       # نام فایل ایندکس
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# کلاس Wrapper برای سازگاری با LangChain
class LocalEmbeddings:
    def __init__(self, model_name: str):
        print(f"⏳ Loading embedding model: {model_name}...")
        # print(f"⏳ Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("✅ Model loaded.")
        # print("✅ Model loaded.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text], convert_to_numpy=True)[0].tolist()
    
    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)

def build_index(source_dir: str = DOCS_DIR, output_dir: str = INDEX_DIR):
    """
    Builds FAISS index from documents in source_dir and saves to output_dir.
    Callable from other scripts.
    """
    # 1. بررسی پوشه‌ها
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"📁 Created '{DOCS_DIR}' folder. Please put your PDF files here and run again.")
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)
        print(f"📁 Created '{source_dir}' folder. Please put your PDF files here.")
        return

    if not os.path.exists(INDEX_DIR):
        os.makedirs(INDEX_DIR)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 2. یافتن فایل‌ها
    pdf_files = glob.glob(os.path.join(DOCS_DIR, "*.pdf"))
    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
    if not pdf_files:
        print(f"❌ No PDF files found in '{DOCS_DIR}'.")
        print(f"❌ No PDF files found in '{source_dir}'.")
        return

    print(f"📚 Found {len(pdf_files)} PDF files.")
    print(f"📚 Found {len(pdf_files)} PDF files in {source_dir}")

    # 3. لود و پردازش فایل‌ها
    all_docs = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", ".", " ", ""]
    )

    for pdf_path in pdf_files:
        try:
            print(f"📖 Processing: {os.path.basename(pdf_path)}...")
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            
            # افزودن متادیتا (نام فایل به عنوان منبع)
            source_name = os.path.splitext(os.path.basename(pdf_path))[0]
            for doc in docs:
                doc.metadata["source"] = source_name
                # اصلاح شماره صفحه (از 0 به 1)
                if "page" in doc.metadata:
                    doc.metadata["page"] = doc.metadata["page"] + 1
            
            splits = text_splitter.split_documents(docs)
            all_docs.extend(splits)
            print(f"   -> Extracted {len(splits)} chunks.")
            
        except Exception as e:
            print(f"   ❌ Error processing file: {e}")

    if not all_docs:
        print("❌ No documents were processed successfully.")
        return

    print(f"\n🧩 Total chunks to index: {len(all_docs)}")

    # 4. ساخت ایندکس
    try:
        embeddings = LocalEmbeddings(MODEL_NAME)
        print("🚀 Building FAISS index (this may take a while)...")
        
        vectorstore = FAISS.from_documents(all_docs, embeddings)
        
        # 5. ذخیره سازی
        save_path = os.path.join(INDEX_DIR, INDEX_NAME) # LangChain adds .faiss automatically usually, but save_local takes folder
        vectorstore.save_local(INDEX_DIR, INDEX_NAME)
        vectorstore.save_local(output_dir, INDEX_NAME)
        
        print(f"\n✅ SUCCESS! Index saved to '{INDEX_DIR}/{INDEX_NAME}'")
        print(f"\n✅ SUCCESS! Index saved to '{output_dir}/{INDEX_NAME}'")
        print("   Files created:")
        print(f"   - {INDEX_NAME}.faiss")
        print(f"   - {INDEX_NAME}.pkl")
        
    except Exception as e:
        print(f"\n❌ Failed to build index: {e}")

def main():
    build_index()

if __name__ == "__main__":
    main()
