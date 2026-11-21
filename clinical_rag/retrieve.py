
import os
import json
import torch
import numpy as np

# 🔧 PATCH: Fix for NumPy 2.0 compatibility (ChromaDB issue)
if hasattr(np, 'float64') and not hasattr(np, 'float_'):
    np.float_ = np.float64
if hasattr(np, 'int64') and not hasattr(np, 'int_'):
    np.int_ = np.int64
if hasattr(np, 'uint64') and not hasattr(np, 'uint'):
    np.uint = np.uint64

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from sentence_transformers import CrossEncoder
from tqdm import tqdm

CHROMA_PATH = "./chroma_clinical_v2"
EMBED_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-base" # for faster reranking - Synced with main config 
# use  Reranker Model: BAAI/bge-reranker-v2-m3 for better performance

class ClinicalRAG:
    def __init__(self):
        if not os.path.exists(CHROMA_PATH):
            raise FileNotFoundError(
                f"ChromaDB path not found: {CHROMA_PATH}. "
                f"Please build the database first using 'python -m clinical_rag.manager rebuild'"
            )
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL, model_kwargs={"device": self.device})
        self.vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=self.embeddings)
        self.reranker = CrossEncoder(RERANKER_MODEL, device=self.device)
    
    def retrieve(self, query: str, condition: str = None, population: str = None, k_initial=15, k_final=3):
        # 1. Metadata filtering
        filter_dict = {}
        if condition: filter_dict["condition"] = condition
        if population: filter_dict["population"] = population
        
        # 2. Initial retrieval from Chroma
        docs = self.vectorstore.similarity_search(query, k=k_initial, filter=filter_dict)
        
        if not docs:
            return []

        # 3. Re-ranking with CrossEncoder
        pairs = [(query, d.page_content) for d in docs]
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        
        # 4. Combine docs with their new scores and sort
        combined = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        
        # 5. Prepare final results with comprehensive metadata
        results = []
        for doc, score in combined[:k_final]:
            metadata = doc.metadata
            results.append({
                "text": doc.page_content,
                "source": metadata.get("source", "N/A"),
                "year": metadata.get("year", "N/A"),
                "page": metadata.get("page", "N/A"), # <<<---- **اضافه کردن شماره صفحه**
                "relevance_score": float(score)
            })
        return results

# --- Example Usage ---
if __name__ == "__main__":
    try:
        rag = ClinicalRAG()
        # Example query that might benefit from metadata
        res = rag.retrieve(
            query="What is the first-line antibiotic for UTI in pregnant women with a penicillin allergy?",
            condition="urinary tract infection",
            population="pregnant women"
        )
        
        print("\n🎯 Final Results (after re-ranking):")
        if not res:
            print("   No relevant documents found for the query.")
        else:
            for i, r in enumerate(res, 1):
                print(f"\n[{i}] (Score: {r['relevance_score']:.3f}) | Source: {r['source']}, p. {r['page']} ({r['year']})")
                print(f"   Text: {r['text'][:300]}...")

    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
