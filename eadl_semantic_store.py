# -*- coding: utf-8 -*-
"""
🧠 EADL Semantic Correction Store

لایه‌ی یادگیری معنایی EADL — یک «RAG کوچک دوم».

اصلاحیه‌های متخصص در یک ChromaDB جدا (eadl_index) با همان امبدینگ bge-m3 آروان
(get_rag_embeddings) ذخیره می‌شوند. موقع هر سوال، فقط مرتبط‌ترین اصلاحیه‌ها (بالای آستانه‌ی
شباهت) بازیابی و به پرامپت تزریق می‌شوند — به‌جای تزریق همه‌ی اصلاحیه‌ها (که با رشد، بمب توکن است).

طراحی fail-safe: اگر آروان/Chroma در دسترس نبود، store غیرفعال می‌شود و ربات بدون اخلال
به کار ادامه می‌دهد (هیچ اصلاحیه‌ای تزریق نمی‌شود، ولی پاسخ‌دهی مختل نمی‌شود).
"""
import asyncio
import time
from typing import List, Dict, Any, Optional

from logging_config import get_logger

logger = get_logger(__name__)


class EADLSemanticStore:
    """ذخیره و بازیابی معنایی اصلاحیه‌های متخصص روی ChromaDB + bge-m3 آروان."""

    def __init__(self, index_path: Optional[str] = None):
        from config import EADL_INDEX_PATH
        self.index_path = index_path or EADL_INDEX_PATH
        self.db = None
        self.enabled = False
        self._init_db()

    def _init_db(self):
        """ساخت تنبل و fail-safe دیتابیس Chroma. خطا = غیرفعال‌سازی امن (نه کرش ربات)."""
        try:
            try:
                from langchain_chroma import Chroma
            except ImportError:
                from langchain_community.vectorstores import Chroma

            from embeddings import get_rag_embeddings

            # منبع واحد امبدینگ — همان مدلی که RAG اصلی استفاده می‌کند (bge-m3 @ 1024).
            embedding_function = get_rag_embeddings()
            self.db = Chroma(
                persist_directory=self.index_path,
                embedding_function=embedding_function,
                collection_name="eadl_corrections",
                # ⚠️ فاصله‌ی cosine اجباری: bge-m3 نرمال نیست؛ با L2 پیش‌فرض،
                #    relevance score خراب/منفی می‌شود. cosine → امتیاز معنادار در 0..1.
                collection_metadata={"hnsw:space": "cosine"},
            )
            self.enabled = True
            logger.info(f"✅ EADL Semantic Store آماده شد (مسیر: {self.index_path})")
        except Exception as e:
            self.db = None
            self.enabled = False
            logger.warning(
                f"⚠️ EADL Semantic Store غیرفعال شد ({e}). "
                f"ربات بدون تزریق اصلاحیه ادامه می‌دهد."
            )

    # ---------------------------------------------------------------
    # WRITE: افزودن اصلاحیه‌ی متخصص
    # ---------------------------------------------------------------
    def _add_correction_sync(self, case: Dict[str, Any]) -> bool:
        if not self.enabled or self.db is None:
            return False
        try:
            # سندِ قابل‌جستجو = متنِ سوال کاربر (تا سوال‌های مشابه آینده آن را پیدا کنند).
            query_text = (case.get("query") or "").strip()
            if not query_text:
                logger.warning("EADL Store: کیس بدون متن سوال؛ از افزودن صرف‌نظر شد.")
                return False

            correction_text = (case.get("comment") or "").strip()
            reviewer_id = int(case.get("reviewer_id", 0) or 0)
            kws = case.get("keywords") or []

            # 🗳️ CONSENSUS MERGE: اگر اصلاحیه‌ی هم‌موضوعی از قبل هست و متخصصِ دیگری ثبتش
            #    کرده، به‌جای رکورد تکراری، شمارنده‌ی تأیید را بالا ببر (اجماع واقعی).
            from config import EADL_CONSENSUS_MATCH_THRESHOLD
            try:
                similar = self.db.similarity_search_with_relevance_scores(query_text, k=1)
            except Exception:
                similar = []
            if similar:
                doc, score = similar[0]
                if score is not None and score >= EADL_CONSENSUS_MATCH_THRESHOLD:
                    md = dict(doc.metadata or {})
                    reviewers = [r for r in str(md.get("reviewer_ids", "")).split(",") if r]
                    if str(reviewer_id) in reviewers:
                        logger.info("EADL: همان متخصص قبلاً این مورد را ثبت کرده؛ تأیید تکراری نشد.")
                        return True
                    reviewers.append(str(reviewer_id))
                    md["confirmations"] = int(md.get("confirmations", 1)) + 1
                    md["reviewer_ids"] = ",".join(reviewers)
                    existing_id = md.get("case_id") or getattr(doc, "id", None)
                    if existing_id:
                        self.db._collection.update(ids=[str(existing_id)], metadatas=[md])
                        logger.info(f"🗳️ EADL consensus: اصلاحیه‌ی هم‌موضوع تأیید شد (confirmations={md['confirmations']}).")
                        return True

            # --- رکورد جدید (اولین متخصص) ---
            # Chroma متادیتا را فقط str/int/float/bool می‌پذیرد؛ keywords را به رشته تبدیل می‌کنیم.
            metadata = {
                "case_id": str(case.get("id", "")),
                "domain": str(case.get("domain", "general")),
                "keywords": ", ".join(kws) if isinstance(kws, list) else str(kws),
                "correction_text": correction_text,
                "correct_answer": (case.get("response") or "")[:1500],
                "reviewer_id": reviewer_id,
                "reviewer_ids": str(reviewer_id),
                "confirmations": 1,
                "verdict": str(case.get("verdict", "")),
                "timestamp": float(case.get("review_time", case.get("timestamp", time.time()))),
            }
            # id پایدار = case_id تا افزودن دوباره‌ی همان کیس، رکورد را به‌روزرسانی کند (نه تکرار).
            ids = [str(case.get("id"))] if case.get("id") else None
            self.db.add_texts(texts=[query_text], metadatas=[metadata], ids=ids)
            logger.info(f"🧠 EADL Store: اصلاحیه‌ی کیس {case.get('id')} ایندکس شد (متخصص جدید).")
            return True
        except Exception as e:
            logger.error(f"❌ EADL Store add_correction خطا: {e}")
            return False

    async def add_correction(self, case: Dict[str, Any]) -> bool:
        """اصلاحیه‌ی یک کیس بازبینی‌شده را به ایندکس معنایی اضافه می‌کند (non-blocking)."""
        return await asyncio.to_thread(self._add_correction_sync, case)

    # ---------------------------------------------------------------
    # READ: بازیابی اصلاحیه‌های مرتبط
    # ---------------------------------------------------------------
    def _retrieve_sync(self, query: str, k: int, threshold: float) -> List[Dict[str, Any]]:
        if not self.enabled or self.db is None or not (query or "").strip():
            return []
        try:
            # امتیاز relevance در بازه‌ی 0..1 (هرچه بزرگ‌تر، مرتبط‌تر).
            results = self.db.similarity_search_with_relevance_scores(query, k=max(1, k))
            out: List[Dict[str, Any]] = []
            for doc, score in results:
                if score is None or score < threshold:
                    continue
                md = doc.metadata or {}
                out.append({
                    "score": float(score),
                    "domain": md.get("domain", "general"),
                    "correction_text": md.get("correction_text", ""),
                    "correct_answer": md.get("correct_answer", ""),
                    "case_id": md.get("case_id", ""),
                    "confirmations": int(md.get("confirmations", 1)),
                    "matched_query": doc.page_content,
                })
            return out
        except Exception as e:
            logger.error(f"❌ EADL Store retrieve خطا: {e}")
            return []

    async def retrieve(self, query: str, k: int = 3, threshold: float = 0.75) -> List[Dict[str, Any]]:
        """مرتبط‌ترین اصلاحیه‌های متخصص برای یک سوال را برمی‌گرداند (فقط بالای آستانه)."""
        return await asyncio.to_thread(self._retrieve_sync, query, k, threshold)

    def build_injection_text(self, corrections: List[Dict[str, Any]]) -> str:
        """اصلاحیه‌های بازیابی‌شده را به یک پیام system برای تزریق به LLM تبدیل می‌کند.
        لحن بر اساس اجماع: تأییدشده توسط چند متخصص = قوی؛ تک‌متخصص = مقدماتی/با احتیاط."""
        if not corrections:
            return ""
        from config import EADL_MIN_CONSENSUS
        lines = [
            "🧠 **EXPERT CORRECTIONS (human specialist feedback for similar past cases):**",
            "نکات زیر را در پاسخت لحاظ کن. به سطح اعتبار هر مورد دقت کن:",
        ]
        added = 0
        for i, c in enumerate(corrections, 1):
            txt = (c.get("correction_text") or "").strip()
            if not txt:
                continue
            conf = int(c.get("confirmations", 1))
            if conf >= EADL_MIN_CONSENSUS:
                tag = f"✅ تأییدشده توسط {conf} متخصص — معتبر"
            else:
                tag = "🔶 نظر مقدماتی یک متخصص — با احتیاط و به‌عنوان نکته‌ی تکمیلی استفاده کن، نه قطعی"
            lines.append(f"{i}. [{tag}] (شباهت {int(c['score']*100)}%) {txt}")
            added += 1
        if added == 0:
            return ""
        return "\n".join(lines)


# Singleton — توسط app.py ساخته و به سیستم تزریق می‌شود.
_store_instance: Optional[EADLSemanticStore] = None


def get_semantic_store() -> EADLSemanticStore:
    """نمونه‌ی مشترک EADLSemanticStore (ساخت تنبل، یک‌بار)."""
    global _store_instance
    if _store_instance is None:
        _store_instance = EADLSemanticStore()
    return _store_instance
