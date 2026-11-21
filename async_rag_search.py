# -*- coding: utf-8 -*-
"""
Async Search Module - UNIVERSAL KNOWLEDGE BASE (v9.0)

This module provides public APIs for comprehensive RAG search across ALL knowledge types:

SUPPORTED KNOWLEDGE TYPES:
1. **Images**: Medical slides, microscopy, pathology images
2. **Documents**: PDFs, Word files, uploaded documents
3. **Books**: Medical textbooks, references (indexed in vector store)
4. **Atlases**: Medical atlases and visual references
5. **Guidelines**: Clinical protocols, diagnostic guidelines

VECTOR STORE ARCHITECTURES:
1. **FAISS** (Current - brain_index/):
   - Single comprehensive index for all knowledge types
   - Fast vector search
   - Legacy system

2. **ChromaDB** (Future - vector_stores/chroma_*):
   - Separate or combined collections per knowledge type
   - Flexible metadata
   - Modern architecture
   - Will be added alongside or replace FAISS

UNIVERSAL DESIGN:
- Agnostic to underlying vector store (FAISS or ChromaDB)
- Supports multiple vector stores simultaneously
- Priority: ChromaDB < FAISS (if both exist)
- Graceful fallback for missing knowledge bases
- Extensible for new document types
"""
import asyncio
import os
import json
import logging
import pickle
import io
from typing import List, Dict, Any, Optional, Tuple

# --- Generic Libraries ---
from PIL import Image
# Removed AI_MODEL import
import numpy as np

# 🔧 PATCH: Fix for NumPy 2.0 compatibility (ChromaDB issue)
if hasattr(np, 'float64') and not hasattr(np, 'float_'):
    np.float_ = np.float64
if hasattr(np, 'int64') and not hasattr(np, 'int_'):
    np.int_ = np.int64
if hasattr(np, 'uint64') and not hasattr(np, 'uint'):
    np.uint = np.uint64

from embeddings import MyGoogleEmbeddings, MyOpenAIEmbeddings, LocalEmbeddings, get_rag_embeddings
from exceptions import SearchError

# --- Hybrid Search Dependencies ---
try:
    from langchain_community.retrievers import BM25Retriever
except ImportError:
    BM25Retriever = None # Graceful fallback

# --- Text Search Dependencies ---
# from clinical_rag.retrieve import ClinicalRAG  <-- REMOVED to enforce Universal Architecture

# Setup logging
logger = logging.getLogger(__name__)

# =============================================================
# 🔒 SAFE PICKLE LOADING (SEC-006)
# =============================================================
# Restricted unpickler that only allows safe built-in types.
# Prevents arbitrary code execution via malicious pickle files.

class SafeUnpickler(pickle.Unpickler):
    """Restricts pickle loading to safe built-in types only."""

    # Set of (module, name) tuples that are allowed
    _ALLOWED_MODULES = {
        ('builtins', 'set'),
        ('builtins', 'frozenset'),
        ('collections', 'OrderedDict'),
        ('collections', 'defaultdict'),
        ('numpy', 'ndarray'),
        ('numpy', 'dtype'),
        ('numpy', 'float64'),
        ('numpy', 'int64'),
        ('numpy', 'uint64'),
        # Langchain classes used in FAISS metadata pickles
        ('langchain_community.docstore.in_memory', 'InMemoryDocstore'),
        ('langchain_community.vectorstores.faiss', 'FAISS'),
        ('langchain_community.vectorstores', 'FAISS'),
        ('langchain_community.embeddings', 'FakeEmbeddings'),
        ('langchain_core.documents', 'Document'),
        ('langchain_core.documents.base', 'Document'),
        ('langchain_core.embeddings', 'Embeddings'),
    }

    def find_class(self, module: str, name: str):
        # Allow basic Python types (dict, list, tuple, str, int, float, bool, None)
        if module == 'builtins' and name in ('dict', 'list', 'tuple', 'str', 'int', 'float', 'bool', 'set', 'frozenset', 'bytes', 'bytearray'):
            return super().find_class(module, name)
        # Allow explicitly whitelisted classes
        if (module, name) in self._ALLOWED_MODULES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Forbidden class: {module}.{name}. "
            f"Only safe built-in types are allowed in pickle files."
        )


def safe_pickle_load(file_path: str, allowed_classes: set = None) -> Any:
    """
    Load a pickle file with restricted deserialization.
    
    Args:
        file_path: Path to the pickle file
        allowed_classes: Optional set of {(module, name)} tuples to allow
                        in addition to the built-in safe types.
    
    Returns:
        Deserialized object, or None on failure.
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        # Validate file is within expected directory (no path traversal)
        real_path = os.path.realpath(file_path)
        
        with open(real_path, 'rb') as f:
            if allowed_classes:
                # Create a custom unpickler with additional allowed classes
                class CustomSafeUnpickler(SafeUnpickler):
                    _ALLOWED_MODULES = SafeUnpickler._ALLOWED_MODULES | allowed_classes
                data = CustomSafeUnpickler(f).load()
            else:
                data = SafeUnpickler(f).load()
        return data
    except pickle.UnpicklingError as e:
        logger.error(f"❌ SEC-006: Unsafe pickle rejected: {file_path} — {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Failed to load pickle: {file_path} — {e}")
        return None


# BM25 retriever needs additional classes allowed
BM25_PICKLE_ALLOWED = {
    ('langchain_community.retrievers.bm25', 'BM25Retriever'),
    ('langchain_community.retrievers.bm25', 'default_preprocessing_func'),
    ('langchain_community.retrievers', 'BM25Retriever'),
    ('langchain_community.vectorstores', 'BM25Retriever'),
    ('langchain.retrievers', 'BM25Retriever'),
    ('langchain_core.documents.base', 'Document'),
    ('langchain_core.documents', 'Document'),
    ('rank_bm25', 'BM25Okapi'),
}

# =============================================================
# 🚀 ARCHITECTURE CONFIGURATION
# =============================================================
# Change the order to set priority. The system will load all available providers.
# Example: ["FAISS", "CHROMA"] -> FAISS is primary, Chroma is secondary.
# Example: ["CHROMA"] -> Only ChromaDB will be used.
# ⚠️ ChromaDB (chroma_clinical_v2) فعلاً خالی است (۰ بردار) و فقط یک مدل لوکال bge-m3 (~۲GB)
#    را بیخود لود می‌کند. تا وقتی این collection پر شود غیرفعالش کردیم.
#    برای فعال‌سازی دوباره: "CHROMA" را به لیست برگردان.
PROVIDER_PRIORITY = ["FAISS"]


# =============================================================
#  UNIVERSAL KNOWLEDGE BASE CONFIGURATION
# =============================================================

class KnowledgeBaseConfig:
    """
    Universal configuration for all knowledge types.
    Supports FAISS legacy index and future ChromaDB collections.
    """
    
    # Base directories
    BASE_DIR = os.path.dirname(__file__)
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_stores")
    BRAIN_INDEX_DIR = os.path.join(BASE_DIR, "brain_index")
    
    # ==========================================
    # UNIVERSAL FAISS INDEX (Current)
    # ==========================================
    # Single comprehensive FAISS index for ALL knowledge types
    # (Images, Documents, Books, Atlases, Guidelines)
    FAISS_CONFIGS = [
        # Legacy/Standard location - COMPREHENSIVE INDEX
        (BRAIN_INDEX_DIR, "index.faiss", "index.pkl"),
    ]
    
    FAISS_FALLBACK_CONFIGS = [
        (BRAIN_INDEX_DIR, "index_local.faiss", "index_local.pkl"),
    ]
    
    # ==========================================
    # FUTURE CHROMA COLLECTIONS (Scalable)
    # ==========================================
    # Multiple collections for different knowledge types
    CHROMA_BASE_DIR = os.path.join(VECTOR_STORE_DIR, "chroma")
    
    CHROMA_COLLECTIONS = {
        # Knowledge type -> Chroma directory
        "unified": os.path.join(VECTOR_STORE_DIR, "chroma_image_v1"),
        "combined": os.path.join(VECTOR_STORE_DIR, "chroma"),
        "clinical_v2": os.path.join(BASE_DIR, "chroma_clinical_v2"), # ✅ ADDED: Link to your new index
        "images": os.path.join(CHROMA_BASE_DIR, "chroma_images"),
        "documents": os.path.join(CHROMA_BASE_DIR, "chroma_documents"),
        "books": os.path.join(CHROMA_BASE_DIR, "chroma_books"),
        "atlases": os.path.join(CHROMA_BASE_DIR, "chroma_atlases"),
        "guidelines": os.path.join(CHROMA_BASE_DIR, "chroma_guidelines"),
    }
    
    # Default embedding model (Standard for text RAG - 384 dimensions)
    # ✅ UPDATED: Match the model used in ChromaDB ingest.py (BAAI/bge-m3)
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    
    @staticmethod
    def find_faiss_index(configs=None) -> Optional[Tuple[str, str, str]]:
        """Find comprehensive FAISS index for all knowledge types."""
        # Search in current dir AND parent dir (Old system logic)
        search_dirs = [
            KnowledgeBaseConfig.BRAIN_INDEX_DIR,
            os.path.join(os.path.dirname(KnowledgeBaseConfig.BASE_DIR), "brain_index")
        ]
        
        target_configs = configs if configs else KnowledgeBaseConfig.FAISS_CONFIGS
        
        for base_dir in search_dirs:
            # logger.info(f"🔍 Searching for index in: {base_dir}") # Reduced log noise
            for _, index_file, metadata_file in target_configs:
                index_path = os.path.join(base_dir, index_file)
                metadata_path = os.path.join(base_dir, metadata_file)
                
                if os.path.exists(index_path) and os.path.exists(metadata_path):
                    try:
                        metadata = safe_pickle_load(metadata_path)
                        if metadata is None:
                            continue
                        logger.info(f"✅ Found FAISS index ({index_file}): {base_dir}")
                        return (base_dir, index_file, metadata_file)
                    except Exception:
                        pass
        return None
    
    @staticmethod
    def find_chroma_collections() -> Dict[str, str]:
        """Find available Chroma collections (for different knowledge types)."""
        found_collections = {}
        for collection_type, collection_path in KnowledgeBaseConfig.CHROMA_COLLECTIONS.items():
            if os.path.isdir(collection_path):
                try:
                    if any(f in os.listdir(collection_path) for f in ["chroma.sqlite3", ".chroma"]):
                        logger.info(f"✅ Found Chroma collection: {collection_type}")
                        found_collections[collection_type] = collection_path
                except Exception as e:
                    pass
        return found_collections

# ================================================
# 🔍 KNOWLEDGE BASE SEARCH (UNIVERSAL)
# ================================================

class KnowledgeBaseProvider:
    """Abstract interface for knowledge base search."""
    async def search(self, query: str, k: int) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return provider metadata."""
        return {"type": "unknown", "size": 0}

class FaissKnowledgeProvider(KnowledgeBaseProvider):
    """
    Universal FAISS provider for comprehensive knowledge base.
    Handles: Images, Documents, Books, Atlases, Guidelines
    
    Uses the proven load_brain_files() pattern for reliable loading.
    Compatible with LangChain's FAISS format (InMemoryDocstore + ID mapping).
    """
    
    def __init__(self, index_dir: str, index_file: str, metadata_file: str, forced_embeddings=None):
        try:
            self.index_dir = index_dir
            from langchain_community.vectorstores import FAISS
            
            logger.info(f"🔄 Initializing FAISS Knowledge Base from: {index_dir}")
            
            if forced_embeddings:
                self.embeddings = forced_embeddings
                logger.info(f"   Using FORCED embeddings: {type(self.embeddings).__name__}")
            else:
                # ✅ منبع واحد: همان مدلی که faiss_ingest با آن ساخته (پیش‌فرض bge-m3 روی آروان).
                # این تضمین می‌کند مدل ساخت و کوئری همیشه یکی باشند (ریشه‌ی باگ قبلی همین ناهماهنگی بود).
                from config import EMBEDDING_PROVIDER, EMBEDDING_DIM
                self.embeddings = get_rag_embeddings()
                logger.info(f"   Using RAG embeddings: provider={EMBEDDING_PROVIDER}, dim={EMBEDDING_DIM}")
            
            # Determine index name (remove extension)
            index_name = os.path.splitext(index_file)[0]
            
            # Load FAISS index using LangChain's load_local (Robust & Standard)
            # allow_dangerous_deserialization=True is required for pickle files
            self.vectorstore = FAISS.load_local(
                folder_path=index_dir,
                embeddings=self.embeddings,
                index_name=index_name,
                allow_dangerous_deserialization=True
            )
            
            # -------------------------------------------------------
            # 🔧 DIMENSION GUARD (fail-loud, no silent model switch)
            # -------------------------------------------------------
            # نکته‌ی مهم: سوییچ خودکار به یک مدل محلیِ دلخواه (صرفاً چون بُعد جور است) باگ قبلی را
            # پنهان می‌کرد — مدل کوئری باید *همان* مدلی باشد که ایندکس را ساخته، وگرنه بازیابی آشغال است
            # حتی اگر بُعدها برابر باشند. پس به‌جای سوییچ بی‌صدا، اینجا فقط هشدار واضح می‌دهیم.
            if not forced_embeddings:
              try:
                actual_d = self.vectorstore.index.d
                model_d = len(self.embeddings.embed_query("test"))
                if actual_d != model_d:
                    logger.error(
                        f"🚨 Embedding dimension mismatch! Index={actual_d}, current model={model_d}. "
                        f"ایندکس با مدل دیگری ساخته شده. ربات باید ایندکس را با همین "
                        f"EMBEDDING_PROVIDER فعلی بازسازی کند (یا provider را به مدلِ سازنده برگرداند). "
                        f"تا آن زمان نتایج RAG نامعتبر است."
                    )
                else:
                    logger.info(f"✅ Embedding dimension OK ({actual_d}) — index/model aligned.")
              except Exception as e:
                logger.warning(f"⚠️ Could not verify embedding dimension: {e}")

            # -------------------------------------------------------
            # 🔍 HYBRID SEARCH: Load BM25 Retrievers
            # -------------------------------------------------------
            self.bm25_retrievers = self._load_bm25_retrievers()
            
            logger.info(f"✅ FAISS Knowledge Base loaded successfully (Hybrid: {'Active' if self.bm25_retrievers else 'Inactive'})")
            self.name = "FAISS Knowledge Base"
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize FAISS: {e}")
            raise
    
    def _load_bm25_retrievers(self) -> List[Any]:
        """Scans for BM25 retrievers in the index directory (brain_index)."""
        retrievers = []
        if not BM25Retriever:
            return []

        # Scan brain_index for any BM25 pickle files (copied there by merger)
        if os.path.exists(self.index_dir):
            for root, dirs, files in os.walk(self.index_dir):
                for file in files:
                    if "bm25_retriever" in file and file.endswith(".pkl"):
                        path = os.path.join(root, file)
                        try:
                            retriever = safe_pickle_load(path, allowed_classes=BM25_PICKLE_ALLOWED)
                            if retriever is not None:
                                retrievers.append(retriever)
                                logger.info(f"   ✅ Loaded BM25 retriever: {file}")
                            else:
                                logger.warning(f"   ⚠️ BM25 pickle rejected (unsafe): {file}")
                        except Exception as e:
                            logger.warning(f"   ⚠️ Failed to load BM25 from {file}: {e}")
        
        if retrievers:
            logger.info(f"   ✅ Loaded {len(retrievers)} BM25 retrievers from {self.index_dir}")
        return retrievers

    def search(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Performs Hybrid Search (Vector + BM25) with RRF Fusion."""
        try:
            # 1. Vector Search (Semantic)
            vector_results = self.vectorstore.similarity_search_with_score(query, k=k)
            
            # 2. BM25 Search (Keyword) - if available
            bm25_results = []
            if self.bm25_retrievers:
                for retriever in self.bm25_retrievers:
                    try:
                        # BM25Retriever returns list of Documents
                        res = retriever.invoke(query)
                        bm25_results.extend(res[:k]) # Take top k from each book
                    except Exception:
                        pass
            
            # 3. Reciprocal Rank Fusion (RRF)
            # Combine results if we have BM25, otherwise just use vector
            if not bm25_results:
                final_docs = vector_results
            else:
                # RRF Algorithm
                fused_scores = {}
                
                # Process Vector Results
                for rank, (doc, score) in enumerate(vector_results):
                    content = doc.page_content
                    if content not in fused_scores:
                        fused_scores[content] = {'doc': doc, 'score': 0.0, 'vector_score': score}
                    fused_scores[content]['score'] += 1.0 / (rank + 60)
                    
                # Process BM25 Results
                for rank, doc in enumerate(bm25_results):
                    content = doc.page_content
                    if content not in fused_scores:
                        fused_scores[content] = {'doc': doc, 'score': 0.0, 'vector_score': 1.0} # Default distance
                    fused_scores[content]['score'] += 1.0 / (rank + 60)
                
                # Sort by RRF score descending
                sorted_items = sorted(fused_scores.values(), key=lambda x: x['score'], reverse=True)
                
                # Convert back to format expected by system (doc, score)
                # We use 1/RRF_score as 'distance' to maintain compatibility (lower is better logic? No, usually distance is lower=better)
                # Actually, rag_engine expects 'distance' or 'score'. 
                # Let's return the doc and attach the hybrid score to metadata.
                final_docs = []
                for item in sorted_items[:k]:
                    doc = item['doc']
                    # We fake a distance for compatibility, but real score is in metadata
                    doc.metadata['hybrid_score'] = item['score']
                    final_docs.append((doc, item.get('vector_score', 0.5)))

            results = []
            for doc, score in final_docs:
                # Extract metadata and content
                res = doc.metadata.copy()
                res['content'] = doc.page_content
                res['distance'] = float(score)
                if 'hybrid_score' in doc.metadata:
                    res['hybrid_score'] = doc.metadata['hybrid_score']
                results.append(res)
            
            return results
        except Exception as e:
            logger.error(f"❌ FAISS search error: {e}", exc_info=True)
            return []
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider": "FAISS (LangChain)",
            "vectors": self.vectorstore.index.ntotal if hasattr(self.vectorstore, 'index') else "Unknown",
            "format": "LangChain"
        }

class ChromaKnowledgeProvider(KnowledgeBaseProvider):
    """
    Modern ChromaDB provider with support for multiple knowledge types.
    Inspired by load_brain_files() pattern but adapted for Chroma.
    """
    
    def __init__(self, collections: Dict[str, str]):
        try:
            try:
                from langchain_chroma import Chroma
            except ImportError:
                from langchain_community.vectorstores import Chroma
            
            logger.info(f"🔄 Initializing ChromaDB Knowledge Base with {len(collections)} collection(s)")
            self.collections = {}
            
            # ✅ FIX: Use LocalEmbeddings wrapper instead of raw SentenceTransformer
            self.embedding_function = LocalEmbeddings(KnowledgeBaseConfig.EMBEDDING_MODEL_NAME)
            
            for collection_type, path in collections.items():
                try:
                    if not os.path.isdir(path):
                        logger.warning(f"   ⚠️ Path not found: {collection_type}")
                        continue
                    
                    db = Chroma(persist_directory=path, embedding_function=self.embedding_function)
                    self.collections[collection_type] = db
                    logger.info(f"   ✅ Loaded collection: {collection_type}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Failed to load {collection_type}: {e}")
            
            if self.collections:
                logger.info(f"✅ ChromaDB Knowledge Base initialized ({len(self.collections)} active collection(s))")
                self.name = "ChromaDB Knowledge Base"
            else:
                raise SearchError("No valid Chroma collections could be loaded", engine="chromadb")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            raise

    def search(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Search across all collections."""
        try:
            all_results = []
            
            for collection_type, db in self.collections.items():
                try:
                    # Encode query
                    query_embedding = self.embedding_function.embed_documents([query])
                    
                    # Search in this collection
                    results = db.similarity_search_by_vector(
                        embedding=query_embedding[0], 
                        k=k  # Trust the k passed (optimized by Orchestrator)
                    )
                    
                    # Add results with type annotation
                    for doc in results:
                        result = doc.metadata.copy() if hasattr(doc, 'metadata') else {}
                        result['knowledge_type'] = collection_type
                        if hasattr(doc, 'page_content'):
                            result['content'] = doc.page_content
                        all_results.append(result)
                except Exception as e:
                    logger.warning(f"   ⚠️ Error searching {collection_type}: {e}")
            
            # Return top k results across all collections
            return all_results[:k]
        except Exception as e:
            logger.error(f"❌ ChromaDB search error: {e}")
            return []
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider": "ChromaDB",
            "collections": list(self.collections.keys()),
            "count": len(self.collections)
        }

class UniversalKnowledgeOrchestrator:
    """
    Intelligent orchestrator for universal knowledge base search.
    
    Supports:
    - HYBRID search across multiple vector stores (FAISS + ChromaDB).
    - Configurable priority via PROVIDER_PRIORITY list.
    - Graceful fallback to LLM's base knowledge if no stores are found.
    
    """
    
    def __init__(self):
        self.providers: List[KnowledgeBaseProvider] = []
        self.provider_name: str = "None"
        
        logger.info("\n" + "="*70)
        logger.info("🔍 Universal Knowledge Base Orchestrator - Detecting stores...")
        logger.info(f"   Priority Order: {PROVIDER_PRIORITY}")
        logger.info("="*70)
        
        # Dynamically load providers based on priority list
        for provider_type in PROVIDER_PRIORITY:
            if provider_type == "FAISS":
                faiss_config = KnowledgeBaseConfig.find_faiss_index()
                if faiss_config:
                    try:
                        index_dir, index_file, metadata_file = faiss_config
                        faiss_provider = FaissKnowledgeProvider(index_dir, index_file, metadata_file)
                        self.providers.append(faiss_provider)
                        logger.info("✅ Loaded Provider: FAISS (Comprehensive Index)")
                    except Exception as e:
                        logger.warning(f"⚠️ FAISS initialization failed: {e}")
            
            elif provider_type == "CHROMA":
                chroma_collections = KnowledgeBaseConfig.find_chroma_collections()
                if chroma_collections:
                    try:
                        chroma_provider = ChromaKnowledgeProvider(chroma_collections)
                        self.providers.append(chroma_provider)
                        logger.info("✅ Loaded Provider: ChromaDB (Scalable Collections)")
                    except Exception as e:
                        logger.warning(f"⚠️ ChromaDB initialization failed: {e}")

        # Summary
        if not self.providers:
            logger.warning("⚠️ No knowledge base found!")
            logger.warning("   - No FAISS index found (brain_index/)")
            logger.warning("   - No ChromaDB collections detected")
            logger.info("   📝 RAG retrieval will be DISABLED. System will use base knowledge.")
            self.provider_name = "None (Fallback to Base LLM Knowledge)"
        else:
            names = [getattr(p, 'name', type(p).__name__) for p in self.providers]
            self.provider_name = " + ".join(names)
            logger.info(f"🚀 Active Providers: {self.provider_name}")
        
        logger.info("="*70 + "\n")

    @property
    def provider(self):
        """Legacy property for backward compatibility."""
        return self.providers[0] if self.providers else None

    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Perform universal knowledge base search across all active providers."""
        if not self.providers:
            logger.warning("❌ No knowledge provider available for search.")
            return []
        
        all_results = []
        loop = asyncio.get_running_loop()
        
        # Query ALL providers
        for p in self.providers:
            try:
                # Run in executor to avoid blocking main thread
                # 🧠 STRATEGY: Differentiate 'k' based on provider strength
                # FAISS (Legacy/Books): Needs wide net but not too wide to kill CPU.
                # Chroma (Precise/Guidelines): Stronger search, needs less noise (k=10).
                provider_k = k
                if isinstance(p, ChromaKnowledgeProvider):
                    provider_k = min(k, 10) # Cap Chroma at 10 results max
                elif isinstance(p, FaissKnowledgeProvider):
                    provider_k = k # Trust the engine's requested k (usually 10)

                provider_name = getattr(p, 'name', 'Unknown Provider')
                logger.info(f"   -> Querying {provider_name} (k={provider_k})...")
                results = await loop.run_in_executor(None, p.search, query, provider_k)
                if results:
                    # Add provider source to each result for debugging/tracing
                    for res in results:
                        res['provider_source'] = provider_name
                    all_results.extend(results)
                    logger.info(f"   <- Found {len(results)} results from {provider_name}.")
            except Exception as e:
                logger.error(f"❌ Search failed for {getattr(p, 'name', 'Unknown')}: {e}")
        
        # The main rag_engine will do the final reranking.
        logger.info(f"🔍 Total results from all providers: {len(all_results)}")
        return all_results

# --- Global Singleton Instance ---
knowledge_base_orchestrator = UniversalKnowledgeOrchestrator()

# ================================================
# 📖 TEXT SEARCH FUNCTION
# ================================================

# ================================================
# 🚀 PUBLIC API
# ================================================

async def async_knowledge_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Universal knowledge base search across all types:
    Images, Documents, Books, Atlases, Guidelines
    
    Args:
        query: Search query (text or can be based on image analysis)
        k: Number of results to return
    
    Returns:
        List of relevant knowledge items with metadata
    """
    if not knowledge_base_orchestrator.provider:
        logger.warning(f"⚠️ No knowledge base provider active")
        return []
    
    logger.info(f"🔍 Knowledge search using {knowledge_base_orchestrator.provider_name}: query_length={len(query)}")
    return await knowledge_base_orchestrator.search(query, k)

# Backward compatibility aliases
async def async_image_search(image_path: str, k: int = 3) -> List[Dict[str, Any]]:
    """Legacy API - redirects to universal knowledge search."""
    if not os.path.exists(image_path):
        logger.warning(f"❌ Image not found at: {image_path}")
        return []
    logger.info(f"🔍 Image-based knowledge search: {os.path.basename(image_path)}")
    # For backward compatibility, search by filename or generic query
    return await knowledge_base_orchestrator.search(f"image: {os.path.basename(image_path)}", k)

async def async_text_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Public API to perform non-blocking text RAG search.
    
    Returns:
        List of relevant documents from knowledge base.
        Empty list on error.
    """
    # ✅ FIX: Use the Universal Orchestrator to support both FAISS and Chroma dynamically
    return await knowledge_base_orchestrator.search(query, k)
