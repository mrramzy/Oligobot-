# -*- coding: utf-8 -*-
"""
Experience-Aware Diagnostic Layer (EADL) Manager.
Manages dynamic feedback and expert authorization.
"""
import json
import os
import asyncio
import uuid
import time
from typing import Dict, Any, List
from logging_config import get_logger

logger = get_logger(__name__)

class EADLManager:
    """
    Experience-Aware Diagnostic Layer (EADL) Manager.
    Features:
    1. Dynamic Knowledge: Records feedback on domains/keywords.
    2. Access Control: Only authorized 'experts' can provide feedback.
    """
    def __init__(self, storage_file: str = None, config_file: str = None):
        from config import EADL_MEMORY_PATH, EADL_CONFIG_PATH, EADL_CASES_PATH
        self.storage_path = storage_file or EADL_MEMORY_PATH
        self.config_path = config_file or EADL_CONFIG_PATH
        self.cases_path = EADL_CASES_PATH
        self.lock = asyncio.Lock()
        # لایه‌ی یادگیری معنایی (توسط RAGSystem تزریق می‌شود). اگر None باشد، فقط آمار کار می‌کند.
        self.semantic_store = None

        self._ensure_files()
        self.config = self._load_json(self.config_path, default={"experts": [], "admins": [], "requests": {}})

    def _ensure_files(self):
        if not os.path.exists(self.storage_path):
            self._write_json_sync(self.storage_path, {"domains": {}, "keywords": {}, "global_stats": {"total_feedback": 0}})
        
        if not os.path.exists(self.config_path):
            # Default config
            self._write_json_sync(self.config_path, {"experts": [], "admins": [], "requests": {}})
            
        if not os.path.exists(self.cases_path):
            self._write_json_sync(self.cases_path, {})

    def _load_json(self, path: str, default: Any) -> Any:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default

    def _write_json_sync(self, path: str, data: Any):
        # نوشتن اتمیک: اول به فایل موقت در همان پوشه، سپس os.replace (rename اتمیک).
        # اگر وسط نوشتن کرش شود، فایل اصلی سالم می‌ماند (نه نیمه‌نوشته/خراب).
        tmp_path = f"{path}.tmp.{os.getpid()}"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    async def _save_data(self, data: Dict[str, Any], path: str):
        await asyncio.to_thread(self._write_json_sync, path, data)

    # --- AUTHORIZATION ---
    def is_authorized(self, user_id: int) -> bool:
        admins = self.config.get("admins", [])
        experts = self.config.get("experts", [])
        return (user_id in admins) or (user_id in experts)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.config.get("admins", [])

    # --- ACCESS REQUEST MANAGEMENT ---
    async def request_access(self, user_id: int, user_info: str) -> bool:
        """Submits a request for EADL access."""
        async with self.lock:
            self.config = await asyncio.to_thread(self._load_json, self.config_path, {"experts": [], "admins": [], "requests": {}})
            
            if user_id in self.config["experts"] or user_id in self.config["admins"]:
                return False # Already authorized
            
            if "requests" not in self.config:
                self.config["requests"] = {}
                
            self.config["requests"][str(user_id)] = {
                "user_info": user_info,
                "timestamp": time.time()
            }
            await self._save_data(self.config, self.config_path)
            return True

    async def get_access_requests(self) -> Dict[str, Dict]:
        """Returns pending access requests."""
        self.config = await asyncio.to_thread(self._load_json, self.config_path, {"experts": [], "admins": [], "requests": {}})
        return self.config.get("requests", {})

    async def process_access_request(self, user_id: int, approved: bool):
        """Approves or rejects a request."""
        async with self.lock:
            self.config = await asyncio.to_thread(self._load_json, self.config_path, {"experts": [], "admins": [], "requests": {}})
            uid_str = str(user_id)
            
            # Remove from requests
            if "requests" in self.config and uid_str in self.config["requests"]:
                del self.config["requests"][uid_str]
            
            if approved:
                if user_id not in self.config["experts"]:
                    self.config["experts"].append(user_id)
            
            await self._save_data(self.config, self.config_path)

    # --- STATISTICS & SCORING ---
    async def get_stats(self, domain: str, keywords: List[str]) -> Dict[str, Any]:
        data = await asyncio.to_thread(self._load_json, self.storage_path, {"domains": {}, "keywords": {}})
        
        total_fb = 0
        score_sum = 0 
        
        # Domain Impact (20%)
        if domain and domain in data["domains"]:
            d_stats = data["domains"][domain]
            total_fb += d_stats.get("total", 0) * 0.2
            score_sum += (d_stats.get("correct", 0) - d_stats.get("incorrect", 0)) * 0.2

        # Keyword Impact (100%)
        for kw in keywords:
            if kw in data["keywords"]:
                k_stats = data["keywords"][kw]
                total_fb += k_stats.get("total", 0)
                score_sum += (k_stats.get("correct", 0) - k_stats.get("incorrect", 0))

        # Calculate Confidence (Base 0.8)
        base_confidence = 0.8
        modifier = 0.0
        if total_fb > 0:
            # Max +/- 0.2 impact based on consensus
            modifier = (score_sum / total_fb) * 0.2 
        
        final_confidence = min(1.0, max(0.1, base_confidence + modifier))
        
        status = "NEUTRAL"
        if final_confidence >= 0.9 and total_fb > 3:
            status = "TRUSTED"
        elif final_confidence <= 0.6:
            status = "CAUTION"

        return {
            "total_feedback": int(total_fb),
            "confidence_score": final_confidence,
            "status": status
        }

    # --- RECORD FEEDBACK ---
    async def record_feedback(self, user_id: int, domain: str, keywords: List[str], feedback_type: str) -> bool:
        if not self.is_authorized(user_id):
            return False

        async with self.lock:
            data = await asyncio.to_thread(self._load_json, self.storage_path, {})
            
            # Update Domain
            if domain:
                if domain not in data["domains"]:
                    data["domains"][domain] = {"total": 0, "correct": 0, "incorrect": 0}
                data["domains"][domain]["total"] += 1
                if feedback_type == "correct":
                    data["domains"][domain]["correct"] += 1
                elif feedback_type in ["incorrect", "warning"]:
                    data["domains"][domain]["incorrect"] += 1

            # Update Keywords
            for kw in keywords:
                if kw not in data["keywords"]:
                    data["keywords"][kw] = {"total": 0, "correct": 0, "incorrect": 0}
                data["keywords"][kw]["total"] += 1
                if feedback_type == "correct":
                    data["keywords"][kw]["correct"] += 1
                elif feedback_type in ["incorrect", "warning"]:
                    data["keywords"][kw]["incorrect"] += 1
            
            data["global_stats"]["total_feedback"] += 1
            await self._save_data(data, self.storage_path)
            logger.info(f"🧠 EADL Feedback: {feedback_type} | User: {user_id}")
            return True

    # --- CASE MANAGEMENT (NEW ARCHITECTURE) ---
    async def submit_case(self, user_id: int, query_text: str, response_text: str, domain: str, keywords: List[str], meta: Dict) -> str:
        """Submits a new case to the pending review queue."""
        case_id = str(uuid.uuid4())[:8]
        case_data = {
            "id": case_id,
            "user_id": user_id,
            "query": query_text,
            "response": response_text,
            "domain": domain,
            "keywords": keywords,
            "meta": meta,
            "timestamp": time.time(),
            "status": "PENDING"  # PENDING, REVIEWED
        }
        
        async with self.lock:
            all_cases = await asyncio.to_thread(self._load_json, self.cases_path, {})
            all_cases[case_id] = case_data
            await self._save_data(all_cases, self.cases_path)
        
        return case_id

    async def get_pending_cases(self) -> List[Dict]:
        """Retrieves all cases waiting for review."""
        all_cases = await asyncio.to_thread(self._load_json, self.cases_path, {})
        pending = [c for c in all_cases.values() if c["status"] == "PENDING"]
        # Sort by newest first
        return sorted(pending, key=lambda x: x["timestamp"], reverse=True)

    async def get_case(self, case_id: str) -> Dict:
        all_cases = await asyncio.to_thread(self._load_json, self.cases_path, {})
        return all_cases.get(case_id)

    async def resolve_case(self, case_id: str, reviewer_id: int, verdict: str, comment: str = ""):
        """Marks a case as reviewed and updates EADL stats + semantic store."""
        case = None
        async with self.lock:
            all_cases = await asyncio.to_thread(self._load_json, self.cases_path, {})
            if case_id in all_cases:
                all_cases[case_id]["status"] = "REVIEWED"
                all_cases[case_id]["verdict"] = verdict
                all_cases[case_id]["reviewer_id"] = reviewer_id
                all_cases[case_id]["comment"] = comment
                all_cases[case_id]["review_time"] = time.time()
                await self._save_data(all_cases, self.cases_path)
                # کپی برای استفاده‌ی بیرون از lock (record_feedback خودش lock می‌گیرد → جلوگیری از deadlock).
                case = dict(all_cases[case_id])

        if case is None:
            return

        # Update the core EADL statistics (record_feedback خودش lock می‌گیرد؛ بیرون از lock بالا).
        fb_type = "correct" if verdict == "APPROVE" else "incorrect"
        await self.record_feedback(reviewer_id, case.get("domain", ""), case.get("keywords", []), fb_type)

        # 🧠 SEMANTIC STORE: اصلاحیه‌ی متنی (verdict رد + comment) را معنایی ایندکس کن
        #    تا برای سوال‌های مشابه آینده بازیابی و تزریق شود.
        if self.semantic_store and comment.strip() and verdict != "APPROVE":
            try:
                await self.semantic_store.add_correction(case)
            except Exception as e:
                logger.error(f"EADL semantic_store add failed: {e}")

        # هرس کیس‌های قدیمی REVIEWED (نگه‌داشتن صف JSON کوچک؛ دانش در eadl_index می‌ماند).
        try:
            await self.prune_old_cases()
        except Exception as e:
            logger.warning(f"EADL prune skipped: {e}")

    async def prune_old_cases(self, retention_days: int = None):
        """کیس‌های REVIEWED قدیمی‌تر از retention_days را از صف JSON حذف می‌کند."""
        if retention_days is None:
            try:
                from config import EADL_CASE_RETENTION_DAYS
                retention_days = EADL_CASE_RETENTION_DAYS
            except Exception:
                retention_days = 30
        cutoff = time.time() - retention_days * 86400
        async with self.lock:
            all_cases = await asyncio.to_thread(self._load_json, self.cases_path, {})
            to_delete = [
                cid for cid, c in all_cases.items()
                if c.get("status") == "REVIEWED" and c.get("review_time", c.get("timestamp", 0)) < cutoff
            ]
            if to_delete:
                for cid in to_delete:
                    del all_cases[cid]
                await self._save_data(all_cases, self.cases_path)
                logger.info(f"🧹 EADL prune: {len(to_delete)} کیس قدیمی حذف شد.")