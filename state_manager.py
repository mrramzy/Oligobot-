import json
import logging
import asyncio
import redis
from typing import List, Dict, Any
from utils import get_time_metadata


class RedisStateManager:
    """
    Manages persistent state in Redis to replace fragile global variables.
    Handles: Chat History, Verified Users, Usage Counts.
    Uses asyncio.to_thread for all Redis calls to avoid blocking the event loop.
    """
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        try:
            self.client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
            self.client.ping()
            logging.info("✅ Redis State Manager connected successfully.")
        except redis.ConnectionError:
            logging.error("❌ Redis Connection Failed! Falling back to in-memory (NOT RECOMMENDED FOR PRODUCTION).")
            self.client = None
            self._memory_fallback = {}

    def get_history(self, user_id: int) -> List[Dict[str, str]]:
        if self.client:
            data = self.client.get(f"history:{user_id}")
            return json.loads(data) if data else []
        return self._memory_fallback.get(f"history:{user_id}", [])

    def save_history(self, user_id: int, history: List[Dict[str, str]], ttl: int = 86400):
        if self.client:
            self.client.set(f"history:{user_id}", json.dumps(history), ex=ttl)
        else:
            self._memory_fallback[f"history:{user_id}"] = history

    def is_verified(self, user_id: int) -> bool:
        if self.client:
            return bool(self.client.sismember("verified_users", str(user_id)))
        return str(user_id) in self._memory_fallback.get("verified_users", set())

    def add_verified_user(self, user_id: int):
        if self.client:
            self.client.sadd("verified_users", str(user_id))
        else:
            if "verified_users" not in self._memory_fallback:
                self._memory_fallback["verified_users"] = set()
            self._memory_fallback["verified_users"].add(str(user_id))

    def _get_daily_key(self, base: str, user_id: int) -> str:
        today_str = get_time_metadata()["date"]
        return f"{base}:{user_id}:{today_str}"

    def get_usage(self, user_id: int) -> int:
        if self.client:
            key = self._get_daily_key("usage", user_id)
            val = self.client.get(key)
            return int(val) if val else 0

        today_date = get_time_metadata()["date"]
        usage_data = self._memory_fallback.get("daily_usage", {})
        user_daily_data = usage_data.get(user_id, {})
        if user_daily_data.get("date") != today_date:
            return 0
        return user_daily_data.get("count", 0)

    def increment_usage(self, user_id: int):
        if self.client:
            key = self._get_daily_key("usage", user_id)
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 86400)
            pipe.execute()
        else:
            today_date = get_time_metadata()["date"]
            if "daily_usage" not in self._memory_fallback:
                self._memory_fallback["daily_usage"] = {}

            user_daily_data = self._memory_fallback["daily_usage"].get(user_id, {})

            if user_daily_data.get("date") != today_date:
                self._memory_fallback["daily_usage"][user_id] = {"count": 1, "date": today_date}
            else:
                user_daily_data["count"] += 1

    def set_key(self, key: str, value: Any, ttl: int = 86400):
        if self.client:
            self.client.set(key, json.dumps(value), ex=ttl)
        else:
            self._memory_fallback[key] = value

    def get_key(self, key: str) -> Any:
        if self.client:
            data = self.client.get(key)
            return json.loads(data) if data else None
        return self._memory_fallback.get(key)

    # --- Async versions for use in async handlers ---

    async def async_get_history(self, user_id: int) -> List[Dict[str, str]]:
        if self.client:
            data = await asyncio.to_thread(self.client.get, f"history:{user_id}")
            return json.loads(data) if data else []
        return self._memory_fallback.get(f"history:{user_id}", [])

    async def async_save_history(self, user_id: int, history: List[Dict[str, str]], ttl: int = 86400):
        if self.client:
            await asyncio.to_thread(self.client.set, f"history:{user_id}", json.dumps(history), ex=ttl)
        else:
            self._memory_fallback[f"history:{user_id}"] = history

    async def async_is_verified(self, user_id: int) -> bool:
        if self.client:
            return bool(await asyncio.to_thread(self.client.sismember, "verified_users", str(user_id)))
        return str(user_id) in self._memory_fallback.get("verified_users", set())

    async def async_add_verified_user(self, user_id: int):
        if self.client:
            await asyncio.to_thread(self.client.sadd, "verified_users", str(user_id))
        else:
            if "verified_users" not in self._memory_fallback:
                self._memory_fallback["verified_users"] = set()
            self._memory_fallback["verified_users"].add(str(user_id))

    async def async_increment_usage(self, user_id: int):
        if self.client:
            key = self._get_daily_key("usage", user_id)
            await asyncio.to_thread(self._increment_redis_usage, key)
        else:
            self.increment_usage(user_id)

    async def async_get_usage(self, user_id: int) -> int:
        if self.client:
            key = self._get_daily_key("usage", user_id)
            val = await asyncio.to_thread(self.client.get, key)
            return int(val) if val else 0

        today_date = get_time_metadata()["date"]
        usage_data = self._memory_fallback.get("daily_usage", {})
        user_daily_data = usage_data.get(user_id, {})
        if user_daily_data.get("date") != today_date:
            return 0
        return user_daily_data.get("count", 0)

    def _increment_redis_usage(self, key: str):
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        pipe.execute()
