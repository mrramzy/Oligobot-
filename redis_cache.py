# -*- coding: utf-8 -*-
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class RAGCache:
    """
    Robust Caching System.
    Attempts to use Redis, falls back to in-memory dictionary if Redis is unavailable.
    """
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.redis_client = None
        self.memory_cache = {}
        self._connect_redis()

    def _connect_redis(self):
        try:
            import redis
            from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
            
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=1
            )
            self.redis_client.ping()
            logger.info("✅ Redis connected successfully.")
        except ImportError:
            logger.warning("⚠️ Redis module not installed. Using in-memory cache.")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Using in-memory cache.")
            self.redis_client = None

    def _generate_key(self, text: str, user_id: int, intent: str = "UNKNOWN") -> str:
        # ✅ Smart Caching Architecture:
        # - Educational/Casual: Shared across all users (increases cache hit rate, faster)
        # - Diagnostic/Others: Strictly per-user (privacy & security for patient data)
        import hashlib
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        if intent in ["EDUCATIONAL", "CASUAL"]:
            return f"rag_cache:shared:{intent}:{text_hash}"
        else:
            return f"rag_cache:private:{user_id}:{text_hash}"

    def get(self, text: str, user_id: int, intent: str = "UNKNOWN") -> Optional[Dict[str, Any]]:
        key = self._generate_key(text, user_id, intent)
        
        # Try Redis
        if self.redis_client:
            try:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # Fallback to Memory
        return self.memory_cache.get(key)

    def set(self, text: str, user_id: int, data: Dict[str, Any], intent: str = "UNKNOWN"):
        key = self._generate_key(text, user_id, intent)
        
        # Try Redis
        if self.redis_client:
            try:
                self.redis_client.setex(key, self.ttl, json.dumps(data))
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # Always save to Memory (as backup)
        self.memory_cache[key] = data