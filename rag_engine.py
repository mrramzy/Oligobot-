# -*- coding: utf-8 -*-
"""
Main RAG Engine - DEFINITIVE & FULLY RESTORED (v13.0)

This is the definitive, correct, and final version.
It restores ALL original components, including the on-demand specialized
prompt loader and all original imports. The dual-mode RAG search logic.


"""

import os
import tempfile
import asyncio
import json
from collections import defaultdict
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
import numpy as np
from PIL import Image
import torch
from sentence_transformers import CrossEncoder

# ✅ ALL ORIGINAL CORE COMPONENTS ARE RESTORED.
from redis_cache import RAGCache
from keyword_extractor import KeywordExtractor
from citation_manager import CitationManager
from input_validator import InputValidator
from exceptions import InvalidInputError
from logging_config import setup_logging, get_logger # CORRECT IMPORT

# ✅ ALL ORIGINAL AI, SEARCH, AND UTILITY MODULES ARE RESTORED.
from ai_models import generate_response, generate_response_stream, refine_search_query, analyze_image_for_rag
from embeddings import MyGoogleEmbeddings, LocalEmbeddings, get_rag_embeddings
from async_rag_search import async_text_search, async_image_search
from utils import detect_clinical_domain, get_time_prompt_hint
from config import ROUTER, RERANKER_MODEL, EMBEDDING_MODEL # Import main heavy model & Reranker
from key_manager import KeyManager # ✅ Key Rotation Manager
from eadl_manager import EADLManager # ✅ EADL Manager
from prompt_builder import build_system_prompt, VIP_SOURCES, GUIDELINE_SOURCES
from entity_extractor import get_entity_extractor
from token_config import (
    RAG_MAX_DOCS, RAG_MAX_DOC_CHARS, ENTITY_TOP_K,
    ENTITY_RELATED_PER_ENTITY, ENTITY_MAX_RELATIONSHIPS,
    MEMORY_MAX_TOPICS, MEMORY_KEYWORDS_PER_TOPIC
)

setup_logging()
logger = get_logger(__name__)


class PromptCache:
    def __init__(self, core_prompt_keys: List[str]):
        self.prompts = {}
        self.core_prompt_keys = core_prompt_keys
        from config import PSL_PATH
        self.psl_path = PSL_PATH
        self._load_core_prompts()

    def _load_core_prompts(self):
        for key in self.core_prompt_keys:
            try:
                path = os.path.join(self.psl_path, f"{key}.md")
                with open(path, "r", encoding="utf-8") as f:
                    self.prompts[key] = f.read()
            except Exception as e:
                logger.error(f"CRITICAL: Failed to cache core prompt '{key}': {e}")

    def get_all_core(self) -> List[str]:
        return [self.prompts.get(key, "") for key in self.core_prompt_keys]

    def get(self, key: str) -> str:
        return self.prompts.get(key, "")


# --- The Definitive, Correctly Restored RAG System ---
class RAGSystem:
    def __init__(self):
        self.cache = RAGCache()
        self.citation_manager = CitationManager()
        self.validator = InputValidator()
        self.keyword_extractor = KeywordExtractor()
        core_prompts = ["system_core", "human_interaction", "prompt_injection_shield", "diagnostic_protocol"]
        self.prompt_cache = PromptCache(core_prompt_keys=core_prompts)
        self.eadl = EADLManager() # ✅ Initialize EADL
        from eadl_semantic_store import get_semantic_store
        self.eadl_store = get_semantic_store()
        self.eadl.semantic_store = self.eadl_store
        from config import PSL_PATH
        self.psl_path = PSL_PATH

        # Entity extraction for enhanced retrieval
        self.entity_extractor = get_entity_extractor()

        # Initialize Cross-Encoder for Advanced Reranking
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.reranker = CrossEncoder(RERANKER_MODEL, device=device)

        # 🧠 Initialize models for semantic grouping
        # ✅ منبع واحد امبدینگ: FAISS با همان مدلی که ایندکس را ساخته (آروان bge-m3) گروه‌بندی می‌شود،
        #    نه مدل مرده‌ی گوگل. وگرنه dedup با وکتورهای ناهماهنگ/۴۰۳ خراب می‌شود.
        # ⚠️ ChromaDB فعلاً غیرفعال است (PROVIDER_PRIORITY=["FAISS"])، پس embedderِ لوکالِ آن
        #    لود نمی‌شود تا مدلِ سنگینِ ~۲GB بیخود در رم نیاید. وقتی Chroma پر و فعال شد،
        #    یک ردیف "ChromaDB": LocalEmbeddings("BAAI/bge-m3") به این dict برگردان.
        rag_embedder = get_rag_embeddings()
        self.embedding_models = {
            "FAISS": rag_embedder,
        }
        
        # ✅ ORIGINAL INIT MESSAGE RESTORED.
        logger.info(f"RAGSystem initialized with Reranker ({RERANKER_MODEL}) on {device} and {len(self.embedding_models)} embedders for grouping.")

    # ✅ SPECIALIZED PROMPT LOADER METHOD RESTORED.
    def _load_specialized_prompt(self, domain: str) -> Optional[str]:
        """Loads a single specialized prompt file from disk ON-DEMAND for images."""
        try:
            path = os.path.join(self.psl_path, f"{domain}.md")
            with open(path, "r", encoding="utf-8") as f:
                logger.info(f"✅ On-Demand Load: Reading specialized prompt for image domain: {domain}")
                return f.read()
        except FileNotFoundError:
            logger.info(f"No specialized image prompt file found for domain: {domain}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to load specialized prompt for {domain}: {e}")
            return None

    async def parallel_searches(self, queries: List[str], k: int = 5) -> List[Any]:
        """Executes multiple search queries in parallel to boost speed and coverage."""
        tasks = [
            async_text_search(query=q, k=k) for q in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Flatten list of lists, skip failed queries
        flat = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"⚠️ Parallel search task failed: {r}")
                continue
            flat.extend(r)
        return flat

    def _calculate_authority_score(self, source_name: str, query: str = "") -> float:
        """
        Calculates authority boost dynamically based on query intent.
        If query asks for 'treatment/protocol', Guidelines get extra boost.
        """
        if not source_name:
            return 0.0
        
        source_lower = str(source_name).lower()
        query_lower = query.lower()
        score = 0.0

        # 1. Base VIP Boost (Gold Standard Textbooks)
        for vip in VIP_SOURCES:
            if vip in source_lower:
                score += 2.0
                break

        # 2. Dynamic Guideline Boost (Context-Aware)
        # If query implies need for standards/protocols, boost Guidelines significantly
        guideline_triggers = ["guideline", "protocol", "treatment", "criteria", "algorithm", "درمان", "پروتکل", "معیار", "استاندارد", "دستورالعمل"]
        
        is_guideline_query = any(t in query_lower for t in guideline_triggers)
        is_guideline_source = any(g in source_lower for g in GUIDELINE_SOURCES)

        if is_guideline_query and is_guideline_source:
             score += 3.0 # 🚀 Extra boost: Guidelines > Textbooks for protocols
             logger.info(f"⚖️ Dynamic Boost: Guideline preferred for '{source_name}' due to query intent.")
        
        return score

    async def _select_diverse_candidates(self, docs: List[Any], similarity_threshold: float = 0.95, max_candidates: int = 8) -> List[Any]:
        """
        Groups documents by semantic similarity and selects a representative from each group.
        This implements the "Semantic Grouping" and "Representative Selection" stages.
        """
        if not docs or len(docs) <= max_candidates:
            return docs

        logger.info(f"🧠 Starting semantic grouping on {len(docs)} initial candidates...")

        # 1. Group documents by their provider
        docs_by_provider = defaultdict(list)
        for doc in docs:
            provider_name = doc.get('provider_source', 'Unknown')
            docs_by_provider[provider_name].append(doc)

        all_representatives = []

        # 2. Process each group independently
        for provider, doc_list in docs_by_provider.items():
            provider_key = "FAISS" if "FAISS" in provider else "ChromaDB" if "ChromaDB" in provider else None
            if not provider_key or provider_key not in self.embedding_models:
                # If provider is unknown, just take the first few docs
                all_representatives.extend(doc_list[:2])
                continue

            embedding_model = self.embedding_models[provider_key]
            doc_contents = [d.get('content', '') or d.get('page_content', '') for d in doc_list]
            
            try:
                doc_embeddings = await asyncio.to_thread(embedding_model.embed_documents, doc_contents)
            except Exception as e:
                logger.error(f"Failed to embed documents for grouping ({provider_key}): {e}")
                all_representatives.extend(doc_list[:2]) # Fallback
                continue

            # 3. Iterative Grouping and Selection for this provider's docs
            representatives = []
            representative_embeddings = []
            for i, doc in enumerate(doc_list):
                embedding = np.array(doc_embeddings[i])
                if np.linalg.norm(embedding) == 0: continue # Skip empty embeddings

                is_similar = False
                for rep_embedding in representative_embeddings:
                    sim = np.dot(embedding, rep_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(rep_embedding))
                    if sim > similarity_threshold:
                        is_similar = True
                        break
                
                if not is_similar:
                    representatives.append(doc)
                    representative_embeddings.append(embedding)

            all_representatives.extend(representatives)

        # Sort by original distance/score before returning, to keep best candidates first
        all_representatives.sort(key=lambda d: d.get('distance', 1.0))
        
        final_candidates = all_representatives[:max_candidates]
        logger.info(f"   ↳ Selected {len(final_candidates)} diverse candidates for reranking (from {len(all_representatives)} groups).")
        return final_candidates

    def _rerank_documents(self, docs: List[Any], query: str, search_queries: List[str]) -> List[Any]:
        """
        🏆 ADVANCED RERANKING SYSTEM (Cross-Encoder + Authority)
        Applies expensive reranking ONLY to the pre-selected diverse candidates.
        """
        if not docs:
            return []

        # Prepare inputs for CrossEncoder
        doc_contents = []
        for doc in docs:
            if isinstance(doc, dict):
                doc_contents.append(doc.get('content', '') or doc.get('page_content', ''))
            else:
                doc_contents.append(getattr(doc, 'page_content', ''))
        
        # Create pairs [Query, Document Text]
        pairs = [[query, content] for content in doc_contents]
        
        # Predict scores (Logits) - Higher is better
        ce_scores = self.reranker.predict(pairs, show_progress_bar=False)
        
        scored_docs = []
        for i, doc in enumerate(docs):
            # Extract metadata
            if isinstance(doc, dict):
                metadata = doc
            else:
                metadata = getattr(doc, 'metadata', {})
            
            # 1. Cross-Encoder Score (Semantic Relevance)
            ce_score = float(ce_scores[i])
            
            # 2. Authority Score (Trust)
            source_name = metadata.get('source', '')
            auth_score = self._calculate_authority_score(source_name, query) # ✅ Pass query for context-aware boosting
            
            # 3. Final Score = Semantic + Authority
            final_score = ce_score + auth_score
            
            # Attach score for debugging transparency
            if isinstance(doc, dict):
                doc['rerank_score'] = final_score
                doc['debug_info'] = f"CE:{ce_score:.2f} | Auth:{auth_score:.1f}"
            
            scored_docs.append((final_score, doc))
            
        # Sort by Final Score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Log the winner for debugging
        if scored_docs:
            top_doc = scored_docs[0][1]
            top_meta = top_doc.get('metadata', {}) if isinstance(top_doc, dict) else getattr(top_doc, 'metadata', {})
            top_source = top_meta.get('source', 'Unknown')
            debug_str = top_doc.get('debug_info', 'N/A') if isinstance(top_doc, dict) else "N/A"
            logger.info(f"🏆 Top Doc after Cross-Encoder: {debug_str} | Source={top_source}")
            
        return [doc for score, doc in scored_docs]

    async def _prepare_llm_payload(
        self, user_id: int, user_query: str, chat_history: List[Dict[str, str]],
        strategy: Dict[str, Any], image_obj: Optional[Image.Image] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[list, List[Any], Dict[str, Any]]:
        # This private method contains all the logic to prepare the data for the LLM

        # STEP 1: VALIDATE INPUT (Original)
        self.validator.validate_query(user_query)

        # STEP 2: EXTRACT KEYWORDS & DOMAIN (Original)
        # Run fast offline operations concurrently with each other
        keywords_task = asyncio.to_thread(self.keyword_extractor.enrich_query, user_query)
        domain_task = asyncio.to_thread(detect_clinical_domain, user_query)
        keywords, domain = await asyncio.gather(keywords_task, domain_task, return_exceptions=True)
        # Handle exceptions from either task
        if isinstance(keywords, Exception):
            logger.warning(f"⚠️ Keyword extraction failed: {keywords}")
            keywords = []
        if isinstance(domain, Exception):
            logger.warning(f"⚠️ Domain detection failed: {domain}")
            domain = ""

        if metadata:
            metadata['detected_domain'] = domain

        # STEP 3: PERFORM RAG SEARCH (The only new part)
        retrieved_docs = []
        img_keywords = ""
        img_findings = ""
        img_parasite_stage = ""
        img_count_estimate = ""
        img_category = "OTHER"

        if strategy.get("use_rag", False):
            mode = strategy.get("mode")
            if mode == "image" and image_obj:
                # 1. Run legacy image search AND vision analysis concurrently
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    image_obj.save(tmp.name)
                    image_path = tmp.name

                legacy_docs_task = async_image_search(image_path=image_path, k=3)
                vision_analysis_task = analyze_image_for_rag(image_obj, expected_category=domain.upper() if domain else None)
                legacy_docs, analysis_result = await asyncio.gather(legacy_docs_task, vision_analysis_task, return_exceptions=True)
                if isinstance(legacy_docs, Exception):
                    logger.warning(f"⚠️ Legacy image search failed: {legacy_docs}")
                    legacy_docs = []
                if isinstance(analysis_result, Exception):
                    logger.warning(f"⚠️ Vision analysis failed: {analysis_result}")
                    analysis_result = {"keywords": "", "category": "OTHER", "findings": ""}
                os.remove(image_path)

                # 2. Vision-to-Text RAG (Enhanced with domain-specific findings)
                img_keywords = analysis_result.get("keywords", "")
                img_category = analysis_result.get("category", "OTHER")
                img_findings = analysis_result.get("findings", "")
                img_parasite_stage = analysis_result.get("parasite_stage", "")
                img_count_estimate = analysis_result.get("count_estimate", "")

                text_rag_docs = []
                search_queries = []

                if img_keywords:
                    # Primary: combined category + keywords
                    search_queries.append(f"{img_category} {img_keywords}")

                    # Split keywords for broader coverage
                    kw_list = [k.strip() for k in img_keywords.replace(",", " ").split() if len(k.strip()) > 2]
                    for kw in kw_list:
                        search_queries.append(f"{img_category} {kw}")

                    # Add findings as additional search terms (e.g. "Döhle bodies", "ring stage")
                    if img_findings:
                        finding_terms = [f.strip() for f in img_findings.replace(",", " ").split() if len(f.strip()) > 3]
                        search_queries.extend([f"{img_category} {ft}" for ft in finding_terms[:3]])

                    # Add parasite stage if present
                    if img_parasite_stage:
                        search_queries.append(f"{img_category} {img_parasite_stage}")

                    # Deduplicate
                    search_queries = list(dict.fromkeys(search_queries))
                    logger.info(f"🔍 Image-derived search queries: {search_queries}")

                    # Execute Parallel Search
                    text_rag_docs = await self.parallel_searches(search_queries, k=10)
                else:
                    logger.warning("⚠️ Vision analysis returned no keywords.")

                # 3. Combine & Rerank
                all_docs = text_rag_docs + legacy_docs
                
                if all_docs:
                    # Rerank based on the generated keywords
                    rerank_query = f"{img_category} {img_keywords}" if img_keywords else "Medical Image"
                    retrieved_docs = self._rerank_documents(all_docs, rerank_query, search_queries)
                    retrieved_docs = retrieved_docs[:5]
                else:
                    retrieved_docs = []

            elif mode in ["text", "document"]:
                # Skip query refinement API for non-RAG intents (saves 2+ seconds)
                intent_name = strategy.get("intent", "")
                if intent_name in ("CASUAL", "IRRELEVANT"):
                    search_queries = [user_query]
                else:
                    # PARALLEL SEARCH STRATEGY (Cross-Domain Aware)
                    refined_query = await refine_search_query(user_query, chat_history)

                search_queries = []
                # Priority 1: Refined English Query (e.g., "normal range of bilirubin")
                if refined_query and refined_query != "SKIP":
                    # Support multiple queries separated by || (Multi-Query Strategy)
                    for q in refined_query.split("||"):
                        if q.strip():
                            search_queries.append(q.strip())

                # Priority 2: Original Query
                search_queries.append(user_query)

                # Priority 3: Specific Keywords (Filter out generic noise)
                if keywords:
                    if isinstance(keywords, list):
                        # Filter generics like "normal range" to avoid noise
                        safe_keywords = [k for k in keywords if len(k.split()) < 3 and k.lower() not in ["normal range", "رنج نرمال", "reference values", "محدوده طبیعی"]]
                        search_queries.extend(safe_keywords[:2])
                    else:
                        search_queries.append(f"{keywords}")

                # Priority 4: TABLE-PRIORITY SEARCH for reference range / criteria queries
                ref_keywords = ["reference range", "normal range", "رنج نرمال", "محدوده طبیعی",
                               "reference values", "crit", "criteria", "criteria for",
                               "WHO classification", "classification", "grading", "staging"]
                is_ref_query = any(k in user_query.lower() for k in ref_keywords)
                if is_ref_query:
                    # Add table-specific search terms
                    search_queries.append(f"{user_query} reference range table")
                    search_queries.append(f"{user_query} g/dL mg/dL normal")

                # Deduplicate
                search_queries = list(dict.fromkeys(search_queries))

                logger.info(f"⚡ Dispatching PARALLEL searches for: {search_queries}")
                # Fast Retrieval (Recall-focused) — k=15 per query, enough after dedup
                retrieved_docs = await self.parallel_searches(search_queries, k=15)
                
                # ✅ OPTIMIZATION: Deduplicate results based on content
                # Since we run multiple queries, the same doc might appear multiple times.
                unique_docs_map = {}
                for doc in retrieved_docs:
                    if isinstance(doc, dict):
                        content = doc.get('content', '') or doc.get('page_content', '')
                    else:
                        content = getattr(doc, 'page_content', '')
                    
                    # Use content as key to filter duplicates
                    if content and content not in unique_docs_map:
                        unique_docs_map[content] = doc
                
                unique_docs = list(unique_docs_map.values())

                # Semantic Grouping — skip if candidates are already few (saves cross-encoder time)
                if len(unique_docs) <= 20:
                    golden_candidates = unique_docs
                else:
                    golden_candidates = await self._select_diverse_candidates(unique_docs)

                # 4️⃣ Adaptive Reranking (on golden candidates)
                if golden_candidates:
                    # ✅ FIX: Use the English refined query for the Cross-Encoder so it matches the English textbooks!
                    rerank_q = search_queries[0] if search_queries else user_query
                    reranked_docs = self._rerank_documents(golden_candidates, rerank_q, search_queries)
                    # 📉 TOKEN OPTIMIZATION: Keep only top K docs after reranking
                    # This prevents sending too much context (e.g. 10 docs) to the LLM
                    retrieved_docs = reranked_docs[:RAG_MAX_DOCS]
                else:
                    retrieved_docs = []

        # STEP 4: BUILD PROMPT - Intent-Aware & Mode-Specific
        llm_chat_history = []
        intent = strategy.get("intent", "EDUCATIONAL") # Default to educational if not passed
        # Normalize unexpected/unknown intents to a safe default so prompt selection
        # always hits a valid branch (prevents malformed returns downstream).
        if intent not in ("DIAGNOSTIC", "EDUCATIONAL", "CASUAL"):
            logger.warning(f"Unknown intent '{intent}' received; defaulting to EDUCATIONAL.")
            intent = "EDUCATIONAL"
        mode = strategy.get("mode", "text")
        
        logger.info(f"🔍 Intent: {intent} | Mode: {mode}")
        
        # ✅ INJECT TIME CONTEXT (Fixes "Wrong Time" Hallucination)
        if metadata and "time_meta" in metadata:
            time_hint = get_time_prompt_hint(metadata["time_meta"])
            llm_chat_history.append({"role": "system", "content": f"CURRENT TIME & CONTEXT: {time_hint}"})

        # ✅ INJECT USER MEMORY (Cross-conversation topic memory)
        try:
            from user_memory import get_user_memory
            user_memory = get_user_memory()
            memory_context = user_memory.get_context(user_id, max_topics=MEMORY_MAX_TOPICS)
            if memory_context:
                llm_chat_history.append({"role": "system", "content": memory_context})
                logger.info(f"🧠 User memory injected for user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ User memory injection skipped: {e}")

        # ✅ STEP 4.5: EADL INJECTION (Experience-Aware Diagnostic Layer)
        # "Science is Static, Experience is Dynamic"
        eadl_status_msg = ""
        eadl_meta = {} # ✅ FIX: Initialize to prevent NameError
        # ✅ حلقه‌ی یادگیری: domain/keywords واقعی را برای ثبت درستِ کیس برگردان (مستقل از intent).
        #    قبلاً handlers مقدار غلط "DIAGNOSTIC"/[] ذخیره می‌کرد و آمار هرگز match نمی‌شد.
        eadl_meta["domain"] = domain
        eadl_meta["keywords"] = keywords if isinstance(keywords, list) else [keywords]

        # 🧠 STEP 4.5a: SEMANTIC CORRECTION INJECTION (مستقل از intent)
        #    مرتبط‌ترین اصلاحیه‌های متخصص برای این سوال را معنایی بازیابی و تزریق کن.
        #    توکن ثابت می‌ماند چون فقط top-K بالای آستانه می‌آید، نه همه‌ی اصلاحیه‌ها.
        try:
            from config import EADL_ENABLED, EADL_TOP_K, EADL_SIM_THRESHOLD
            if EADL_ENABLED and getattr(self, "eadl_store", None) and self.eadl_store.enabled:
                corrections = await self.eadl_store.retrieve(
                    user_query, k=EADL_TOP_K, threshold=EADL_SIM_THRESHOLD
                )
                injection = self.eadl_store.build_injection_text(corrections)
                if injection:
                    logger.info(f"🧠 EADL Correction injection: {len(corrections)} اصلاحیه‌ی مرتبط")
                    llm_chat_history.append({"role": "system", "content": injection})
        except Exception as e:
            logger.warning(f"⚠️ EADL correction retrieval skipped: {e}")

        if intent == "DIAGNOSTIC":
            # Use self.eadl instead of passed case_store
            eadl_stats = await self.eadl.get_stats(domain, keywords if isinstance(keywords, list) else [keywords])
            total_fb = eadl_stats.get("total_feedback", 0)
            status = eadl_stats.get("status", "NEUTRAL")
            error_rate = eadl_stats.get("error_rate", 0.0)
            confidence = eadl_stats.get("confidence_score", 0.8)

            # Update meta for UI
            eadl_meta["confidence_score"] = confidence
            eadl_meta["status"] = status
            
            if total_fb > 0:
                eadl_msg = f"🧠 **EXPERIENCE MEMORY (EADL - Dynamic Layer):**\n"
                eadl_msg += f"- Similar past cases analyzed: {total_fb}\n"
                
                if status == "CAUTION":
                    eadl_msg += f"- ⚠️ CAUTION: Low confidence score ({int(confidence*100)}%). Experts have flagged similar cases as tricky.\n"
                    eadl_msg += "- ACTION: Lower your confidence. Be skeptical. Explicitly mention that this type of case is tricky."
                elif status == "TRUSTED":
                    eadl_msg += "- ✅ TRUST: High historical accuracy for this topic. You can be more confident."
                    eadl_status_msg = f"\n\n✅ **Community Verified**: High Expert Consensus."
                
                # Inject into System Prompt
                logger.info(f"🧠 EADL Injection: {status} (Conf: {confidence:.2f})")
                llm_chat_history.append({"role": "system", "content": eadl_msg})

        # ✅ STEP 4.6: CONSTRUCT RAG CONTEXT & CITATION INSTRUCTIONS
        context_str_parts = []
        
        if retrieved_docs:
            # Instruct the LLM based on user's preference
            if strategy.get("show_references", True):
                # 🎯 دستورِ فرمتِ رفرنس از منبع واحد (book_aliases.json) می‌آید — نه هاردکد.
                context_str_parts.append(self.citation_manager.get_citation_instruction(lang='fa'))
                context_str_parts.append(
                    "5. **FALLBACK:** If the answer is NOT in the references, you MAY use your internal medical knowledge, "
                    "BUT you MUST explicitly state: '⚠️ (این بخش بر اساس دانش عمومی پزشکی است و در منابع جستجو شده یافت نشد)'."
                )
            else:
                context_str_parts.append(
                    "You MUST NOT mention any books, sources, or references in your answer."
                )

            context_str_parts.append("\n--- VERIFIED REFERENCES (RAG CORE) ---")
            for i, doc in enumerate(retrieved_docs):
                # Handle dict vs object & Flattened Metadata
                if isinstance(doc, dict):
                    content = doc.get('content') or doc.get('page_content', 'No content available.')
                    # If flattened (from async_rag_search), doc IS the metadata container
                    metadata = doc.get('metadata', doc)
                else:
                    content = getattr(doc, 'page_content', 'No content available.')
                    metadata = getattr(doc, 'metadata', {})
                    
                source_key = str(metadata.get("source", "Unknown")).lower()
                page = metadata.get("page")
                # شماره‌ی جدول/شکلِ این چانک (اگر داشته باشد) — منبع ساختاریافته برای ارجاع به جدول
                visual = metadata.get("visuals")

                # Use alias from citation manager
                source_display = self.citation_manager.get_display_name(source_key)

                context_str_parts.append(f"\n--- Ref [{i+1}] ---")
                context_str_parts.append(f"Source: {source_display}")
                if page:
                    context_str_parts.append(f"Page: {page}")
                if visual and str(visual).strip().lower() not in ("none", "", "null"):
                    context_str_parts.append(f"Visual: {visual}")
                context_str_parts.append(f"Content: {content}")
            context_str_parts.append("\n--- END OF REFERENCES ---")

            # Entity-enhanced context: search entity index for related entities
            try:
                entity_context_parts = []
                # Search for entities mentioned in the query
                query_entities = self.entity_extractor.search_entities(user_query, top_k=ENTITY_TOP_K)
                for ent in query_entities:
                    ctx = self.entity_extractor.get_entity_context(ent["name"])
                    if ctx:
                        entity_context_parts.append(ctx)
                # Search for related entities of found entities
                for ent in query_entities[:ENTITY_RELATED_PER_ENTITY]:
                    related = self.entity_extractor.get_related_entities(ent["name"])
                    for rel in related[:ENTITY_MAX_RELATIONSHIPS]:
                        entity_context_parts.append(
                            f"Relationship: {rel['source']} → [{rel['type']}] → {rel['target']}"
                        )
                if entity_context_parts:
                    entity_text = "\n".join(entity_context_parts)
                    context_str_parts.append(f"\n--- ENTITY CONTEXT ---\n{entity_text}\n--- END ENTITY CONTEXT ---")
            except Exception as e:
                logger.warning(f"Entity context injection skipped: {e}")
        else:
            # Fallback Mode
            # ✅ FIX: Do not add warning for CASUAL or CONCEPTUAL intents
            conceptual_keywords = ["best", "بهترین", "opinion", "بنظرت", "compare", "مقایسه", "which is better", "کدومه"]
            is_conceptual = any(kw in user_query.lower() for kw in conceptual_keywords)

            if intent != "CASUAL" and not is_conceptual:
                logger.warning("⚠️ No RAG documents retrieved. Forcing fallback mode.")
                context_str_parts.append(
                    "**NOTICE:** No internal library references were found for this specific query.\n"
                    "**INSTRUCTION:** Answer using your general medical knowledge.\n"
                    "**MANDATORY:** You MUST explicitly state at the start: '⚠️ (این بخش بر اساس دانش عمومی پزشکی است و در منابع جستجو شده یافت نشد)'."
                )
            elif is_conceptual:
                 logger.info("ℹ️ Conceptual query detected. RAG fallback will be seamless (no warning).")
            

        # Only add the context if there's something to add
        if context_str_parts:
            final_context_str = "\n".join(context_str_parts)
            # Prepend this to the chat history so it's a high-priority system message
            llm_chat_history.insert(0, {"role": "system", "content": final_context_str})

        # --- DYNAMIC PROMPT SELECTION STRATEGY (delegated to prompt_builder) ---
        prompt_messages = build_system_prompt(
            intent=intent,
            prompt_cache=self.prompt_cache,
            career_context=strategy.get('career_context', ''),
            mode=mode,
            domain=domain,
            load_specialized_prompt=self._load_specialized_prompt
        )
        llm_chat_history.extend(prompt_messages)

        llm_chat_history.extend(chat_history)

        # Append the current user query to the structured history
        llm_chat_history.append({"role": "user", "content": user_query})

        # For text mode, the payload is the structured list of messages.
        if image_obj:
            # Inject vision analysis findings into the prompt for the LLM
            if img_keywords or img_findings:
                vision_context_parts = [f"VISION ANALYSIS RESULT (category: {img_category}):"]
                if img_keywords:
                    vision_context_parts.append(f"Keywords: {img_keywords}")
                if img_findings:
                    vision_context_parts.append(f"Findings: {img_findings}")
                if img_parasite_stage:
                    vision_context_parts.append(f"Parasite stage: {img_parasite_stage}")
                if img_count_estimate:
                    vision_context_parts.append(f"Cell count estimate: {img_count_estimate}")
                vision_context = "\n".join(vision_context_parts)
                llm_chat_history.insert(1, {"role": "system", "content": vision_context})

            # For image mode, flatten the text parts for multimodal input
            text_parts = [msg['content'] for msg in llm_chat_history if isinstance(msg, dict)]
            full_text_prompt = "\n\n".join(text_parts)
            api_payload = [full_text_prompt, image_obj]
        else:
            # For text-only, pass the structured history
            api_payload = llm_chat_history
        
        return api_payload, retrieved_docs, eadl_meta

    async def process_query(
        self, user_id: int, user_query: str, chat_history: List[Dict[str, str]],
        strategy: Dict[str, Any], image_obj: Optional[Image.Image] = None,
        metadata: Optional[Dict[str, Any]] = None,
        case_store: Optional[Any] = None  # Deprecated
    ) -> Tuple[str, str, Dict[str, Any]]:
        try:
            api_payload, retrieved_docs, eadl_meta = await self._prepare_llm_payload(
                user_id, user_query, chat_history, strategy, image_obj, metadata
            )

            llm_response_text = await generate_response(
                user_id=user_id,
                api_payload=api_payload,
                admin_id=0,
                model=ROUTER["text_gen"]
            )

            final_answer = self.citation_manager.format_answer_with_citations(
                retrieved_docs=retrieved_docs, llm_response=llm_response_text,
                show_references=strategy.get("show_references", True)
            )
            sources_text = ""

            # ✅ FIX BUG-001: Cache is managed centrally in app.py to prevent per-user isolation issues.
            # Do NOT cache here to avoid duplicate caching and shared-response security vulnerability.

            return final_answer, sources_text, eadl_meta
        except InvalidInputError as e:
            logger.warning(f"Invalid input detected: {e}")
            return str(e), "", {}
        except Exception as e:
            logger.critical(f"CRITICAL ERROR in RAG pipeline: {e}", exc_info=True)
            return ("متاسفانه یک خطای داخلی بسیار جدی در سیستم رخ داده است.", "", {})

    async def process_query_stream(
        self, user_id: int, user_query: str, chat_history: List[Dict[str, str]],
        strategy: Dict[str, Any], image_obj: Optional[Image.Image] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[AsyncGenerator[str, None], List[Any], Dict[str, Any]]:
        """
        Streaming version of process_query. Returns a generator and metadata.
        """
        try:
            api_payload, retrieved_docs, eadl_meta = await self._prepare_llm_payload(
                user_id, user_query, chat_history, strategy, image_obj, metadata
            )

            llm_stream = generate_response_stream(
                user_id=user_id,
                api_payload=api_payload,
                admin_id=0,
                model=ROUTER["text_gen"]
            )

            return llm_stream, retrieved_docs, eadl_meta
        except Exception as e:
            logger.critical(f"CRITICAL ERROR in streaming RAG pipeline: {e}", exc_info=True)
            async def _error_stream():
                yield "متاسفانه خطایی در پردازش درخواست رخ داد."
            return _error_stream(), [], {}
