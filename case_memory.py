# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, Any, Optional
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

logger = logging.getLogger(__name__)

class CaseMemoryStore:
    """
    Manages clinical case data for users.
    Uses Redis for persistence if available, otherwise falls back to in-memory storage.
    """
    def __init__(self):
        self.redis_client = None
        self.local_memory = {}
        self._connect_redis()

    def _connect_redis(self):
        try:
            import redis
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=1, # Fast fail if Redis is down
                socket_timeout=1
            )
            self.redis_client.ping()
            logger.info("✅ CaseMemory: Redis connected successfully.")
        except Exception as e:
            logger.warning(f"⚠️ CaseMemory: Redis unavailable ({e}). Switching to IN-MEMORY mode.")
            self.redis_client = None

    def _get_key(self, user_id: int) -> str:
        return f"case_memory:{user_id}"

    def update_case(self, user_id: int, data: Dict[str, Any]):
        """Updates the case data for a user (merges with existing)."""
        current_data = self.get_raw_case(user_id)
        current_data.update(data)
        self._save(user_id, current_data)

    def get_raw_case(self, user_id: int) -> Dict[str, Any]:
        """Retrieves the raw dictionary of case data."""
        # Try Redis
        if self.redis_client:
            try:
                data_str = self.redis_client.get(self._get_key(user_id))
                if data_str:
                    return json.loads(data_str)
            except Exception as e:
                logger.error(f"Redis read error: {e}")
        
        # Fallback to Memory
        return self.local_memory.get(user_id, {})

    def _save(self, user_id: int, data: Dict[str, Any]):
        """Internal method to save data to storage."""
        # Save to Redis
        if self.redis_client:
            try:
                self.redis_client.setex(self._get_key(user_id), 86400, json.dumps(data)) # 24h TTL
            except Exception as e:
                logger.error(f"Redis write error: {e}")
        
        # Always save to Memory
        self.local_memory[user_id] = data

    def get_case_summary(self, user_id: int) -> str:
        """Returns a formatted string of the case for the LLM."""
        data = self.get_raw_case(user_id)
        if not data:
            return ""
        
        summary = ["--- CLINICAL CONTEXT ---"]
        for k, v in data.items():
            summary.append(f"{k}: {v}")
        return "\n".join(summary)

    def clear_case(self, user_id: int):
        """Clears the case memory for a user."""
        if self.redis_client:
            try:
                self.redis_client.delete(self._get_key(user_id))
            except Exception:
                pass
        if user_id in self.local_memory:
            del self.local_memory[user_id]

# Singleton instance to be imported by other modules
case_store = CaseMemoryStore()