# -*- coding: utf-8 -*-
"""
User Memory System — Cross-Conversation Topic/Keyword Memory

Persists important medical topics and keywords per user across sessions.
Uses the light LLM model to extract key topics from each conversation,
then injects them into the prompt for personalized responses.
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from config import USER_MEMORY_PATH
MEMORY_FILE = USER_MEMORY_PATH
MAX_TOPICS_PER_USER = 30
MAX_KEYWORDS_PER_TOPIC = 5
TOPIC_RELEVANCE_THRESHOLD = 0.3


class UserMemoryStore:
    """
    Persistent per-user memory store.
    
    Schema per user:
    {
        "topics": [
            {"name": "iron deficiency anemia", "keywords": ["ferritin", "iron", "TIBC"], "relevance": 0.9, "last_seen": "2026-07-09"},
            ...
        ],
        "last_updated": "2026-07-09T15:00:00",
        "total_queries": 42
    }
    """
    
    def __init__(self, filepath: str = MEMORY_FILE):
        self.filepath = filepath
        self._data: Dict[str, Any] = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load memory data from disk."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load user memory: {e}")
        return {}
    
    def _save(self):
        """Save memory data to disk atomically."""
        try:
            tmp_path = f"{self.filepath}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            logger.error(f"Failed to save user memory: {e}")
    
    def _ensure_user(self, user_id: int):
        """Ensure user entry exists."""
        uid = str(user_id)
        if uid not in self._data:
            self._data[uid] = {
                "topics": [],
                "last_updated": datetime.now().isoformat(),
                "total_queries": 0
            }
    
    def add_topics(self, user_id: int, topics: List[Dict[str, Any]]):
        """
        Add or update topics for a user.
        
        Each topic dict should have:
            - name: str (e.g., "iron deficiency anemia")
            - keywords: List[str] (e.g., ["ferritin", "iron", "TIBC"])
            - relevance: float (0-1, how relevant to user's interests)
        """
        if not topics:
            return
        
        self._ensure_user(user_id)
        uid = str(user_id)
        user_data = self._data[uid]
        
        existing_topics = {t["name"]: t for t in user_data["topics"]}
        
        for topic in topics:
            name = topic.get("name", "").strip()
            if not name:
                continue
            
            keywords = topic.get("keywords", [])
            relevance = topic.get("relevance", 0.5)
            today = datetime.now().strftime("%Y-%m-%d")
            
            if name in existing_topics:
                # Update existing topic
                existing = existing_topics[name]
                # Merge keywords (deduplicate)
                all_kw = list(set(existing.get("keywords", []) + keywords))
                existing["keywords"] = all_kw[:MAX_KEYWORDS_PER_TOPIC]
                existing["relevance"] = max(existing.get("relevance", 0), relevance)
                existing["last_seen"] = today
            else:
                # Add new topic
                existing_topics[name] = {
                    "name": name,
                    "keywords": keywords[:MAX_KEYWORDS_PER_TOPIC],
                    "relevance": relevance,
                    "last_seen": today
                }
        
        # Sort by relevance (descending) and keep top N
        sorted_topics = sorted(existing_topics.values(), key=lambda t: t.get("relevance", 0), reverse=True)
        user_data["topics"] = sorted_topics[:MAX_TOPICS_PER_USER]
        user_data["last_updated"] = datetime.now().isoformat()
        user_data["total_queries"] = user_data.get("total_queries", 0) + 1
        
        self._save()
        logger.info(f"Memory updated for user {user_id}: {len(user_data['topics'])} topics")
    
    def get_context(self, user_id: int, max_topics: int = 5) -> str:
        """
        Get a formatted string of user's past topics for prompt injection.
        Returns empty string if no memory exists.
        """
        self._ensure_user(user_id)
        uid = str(user_id)
        topics = self._data[uid].get("topics", [])
        
        if not topics:
            return ""
        
        # Filter by relevance threshold
        relevant = [t for t in topics if t.get("relevance", 0) >= TOPIC_RELEVANCE_THRESHOLD]
        if not relevant:
            return ""
        
        # Take top N most relevant
        top_topics = relevant[:max_topics]
        
        lines = ["The user has previously discussed these medical topics:"]
        for t in top_topics:
            kw_str = ", ".join(t.get("keywords", [])[:3])
            lines.append(f"- {t['name']} ({kw_str})")
        
        return "\n".join(lines)
    
    def get_all_topics(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all topics for a user."""
        self._ensure_user(user_id)
        return self._data[str(user_id)].get("topics", [])
    
    def clear(self, user_id: int):
        """Clear all memory for a user."""
        uid = str(user_id)
        if uid in self._data:
            self._data[uid] = {
                "topics": [],
                "last_updated": datetime.now().isoformat(),
                "total_queries": 0
            }
            self._save()
            logger.info(f"Memory cleared for user {user_id}")
    
    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Get memory stats for a user."""
        self._ensure_user(user_id)
        uid = str(user_id)
        user_data = self._data[uid]
        return {
            "topic_count": len(user_data.get("topics", [])),
            "total_queries": user_data.get("total_queries", 0),
            "last_updated": user_data.get("last_updated", "never")
        }


# Singleton
_user_memory_store: Optional[UserMemoryStore] = None


def get_user_memory() -> UserMemoryStore:
    """Get or create the singleton UserMemoryStore."""
    global _user_memory_store
    if _user_memory_store is None:
        _user_memory_store = UserMemoryStore()
    return _user_memory_store


async def extract_topics_from_conversation(
    user_query: str, 
    assistant_response: str,
    model: str = "gemini"
) -> List[Dict[str, Any]]:
    """
    Use the light LLM model to extract key medical topics from a conversation turn.
    Returns list of {name, keywords, relevance} dicts.
    """
    from config import GEMINI_LIGHT_MODEL, GOOGLE_API_KEY
    from ai_models import _gemini_client, _gemini_generate
    
    extraction_prompt = f"""Extract 2-4 key medical/laboratory science topics from this conversation.
For each topic, provide:
- name: the topic name (in English, e.g., "iron deficiency anemia")
- keywords: 2-4 related medical keywords
- relevance: float 0-1 (how central this topic is to the conversation)

User: {user_query[:500]}
Assistant: {assistant_response[:500]}

Return ONLY a JSON array. No explanation. Example:
[{{"name": "CBC interpretation", "keywords": ["hemoglobin", "WBC", "platelet"], "relevance": 0.8}}]

If the conversation is casual/irrelevant to medical science, return an empty array: []"""

    try:
        api_key = GOOGLE_API_KEY.split(',')[0].strip() if GOOGLE_API_KEY else None
        client = _gemini_client(api_key)
        response = _gemini_generate(client, GEMINI_LIGHT_MODEL, extraction_prompt)
        
        text = response.text.strip()
        # Extract JSON array from response
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            topics = json.loads(text[start:end])
            # Validate structure
            valid = []
            for t in topics:
                if isinstance(t, dict) and "name" in t:
                    valid.append({
                        "name": str(t["name"])[:100],
                        "keywords": [str(k)[:50] for k in t.get("keywords", [])[:MAX_KEYWORDS_PER_TOPIC]],
                        "relevance": min(1.0, max(0.0, float(t.get("relevance", 0.5))))
                    })
            return valid
    except Exception as e:
        logger.warning(f"Topic extraction failed: {e}")
    
    return []
