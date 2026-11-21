# -*- coding: utf-8 -*-
import asyncio
import warnings
from typing import List, Dict
from enum import Enum, auto

import structlog

warnings.filterwarnings("ignore", category=FutureWarning)
from google import genai as google_genai

from config import GOOGLE_API_KEY, AVAILABLE_MODELS
from key_manager import KeyManager

logger = structlog.get_logger(__name__)

class Intent(Enum):
    DIAGNOSTIC = auto()
    EDUCATIONAL = auto()
    CASUAL = auto()
    IRRELEVANT = auto()

CASUAL_KEYWORDS = [
    "سلام", "درود", "وقت بخیر", "خوبی", "چطوری", "مرسی", "ممنون", "تشکر",
    "hi", "hello", "thanks", "thank you", "tnx", "ok", "okay",
    "ساعت", "هوا", "time", "weather"
]

IRRELEVANT_KEYWORDS = [
    "قیمت", "دلار", "یورو", "ارز", "سکه", "طلا", "بورس", "سهام",
    "فوتبال", "استقلال", "پرسپولیس", "لیگ", "بازی",
    "آهنگ", "فیلم", "سریال", "بازیگر",
    "آشپزی", "غذا", "recipe",
    "قیمت روز", "today price", "stock", "crypto", "bitcoin",
]

class IntentManager:
    """
    The 'Smart Traffic Cop' for OLIGOBOT.
    Classifies user input into one of four strategic buckets.
    """
    def __init__(self):
        self.lite_model_name = AVAILABLE_MODELS["gemini"]["light_model"]
        if GOOGLE_API_KEY:
            try:
                first_key = GOOGLE_API_KEY.split(',')[0].strip()
                self.client = google_genai.Client(api_key=first_key)
                logger.info("intent_manager.initialized", model=self.lite_model_name)
            except Exception as e:
                logger.error("intent_manager.init_failed", error=str(e))
                self.client = None
        else:
            self.client = None
            logger.warning("intent_manager.no_api_key", message="Google API Key not found. LLM-based intent detection disabled.")

    def _fast_casual_check(self, text: str) -> bool:
        """A quick, non-LLM check for obviously casual messages."""
        text_lower = text.lower().strip()
        if len(text_lower.split()) < 7:
            for keyword in CASUAL_KEYWORDS:
                if keyword in text_lower:
                    return True
        return False

    async def detect_intent(self, text: str, history: List[Dict[str, str]]) -> Intent:
        """
        Classifies user input into one of the four main intents.
        Uses fast keyword checks first, then falls back to a lightweight LLM.
        """
        # Fast path 1: Casual (keyword-based, instant)
        if self._fast_casual_check(text):
            logger.info("intent_manager.fast_check_hit", intent="CASUAL")
            return Intent.CASUAL

        # Fast path 2: Irrelevant (non-medical keywords, instant)
        text_lower = text.lower().strip()
        if any(kw in text_lower for kw in IRRELEVANT_KEYWORDS):
            logger.info("intent_manager.fast_check_hit", intent="IRRELEVANT")
            return Intent.IRRELEVANT

        # Fast path 3: Diagnostic (patient case patterns, instant)
        import re
        has_numbers = bool(re.search(r'\d+[\.\d]*\s*(mg|dl|mmol|%|g|ml|µ|میلی|نرمال|بالا|پایین|افتاده|افزایش|کاهش)', text_lower))
        has_patient_markers = any(w in text_lower for w in ["بیمار", "مرد", "زن", "ساله", "مراجعه", "شکایت", "علائم"])
        if has_numbers or (has_patient_markers and any(c.isdigit() for c in text)):
            logger.info("intent_manager.fast_check_hit", intent="DIAGNOSTIC")
            return Intent.DIAGNOSTIC

        # Slow path: LLM classification (for remaining ambiguous cases)
        if not self.client:
            logger.warning("intent_manager.llm_fallback", reason="Model not initialized.")
            # Fallback logic: if it contains numbers, assume diagnostic, else educational.
            if any(char.isdigit() for char in text):
                return Intent.DIAGNOSTIC
            return Intent.EDUCATIONAL

        history_str = "\n".join(f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in history[-2:])
        
        prompt = f"""
        Your task is to classify the user's **most recent query**. Use the chat history for context, but the classification MUST be based on the LATEST QUERY.
        Classify into ONE of these categories: DIAGNOSTIC, EDUCATIONAL, CASUAL, IRRELEVANT.

        - **DIAGNOSTIC**: Specific patient case, lab results (e.g., "Hb=9"), patient descriptions.
        - **EDUCATIONAL**: General medical/lab knowledge question (e.g., "What causes anemia?").
        - **CASUAL**: Greetings, thanks, small talk, questions about the bot itself (e.g., "Hello", "How are you?").
        - **IRRELEVANT**: Non-medical topics (e.g., sports, politics).

        **CRITICAL RULE:** Even if the history is medical, if the LATEST QUERY is simple small talk like "How are you?" or "Thanks", the intent is **CASUAL**.

        ---
        CHAT HISTORY:
        {history_str}
        ---
        LATEST USER QUERY:
        "{text}"
        ---

        CATEGORY (ONLY ONE WORD):
        """

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.lite_model_name, contents=prompt
            )
            result_text = response.text.strip().upper()
            logger.info("intent_manager.llm_result", raw_text=result_text)
            return Intent[result_text]
        except Exception as e:
            # 🔄 Auto-Rotate Key on Quota Error
            if "429" in str(e) or "quota" in str(e).lower() or "resource" in str(e).lower():
                logger.warning("intent_manager.quota_exceeded", message="Rotating key and retrying...")
                KeyManager.get_instance().rotate()
                try:
                    from config import GOOGLE_API_KEY
                    new_key = GOOGLE_API_KEY.split(',')[0].strip()
                    self.client = google_genai.Client(api_key=new_key)
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.lite_model_name, contents=prompt
                    )
                    result_text = response.text.strip().upper()
                    return Intent[result_text]
                except Exception as e2:
                    logger.error("intent_manager.retry_failed", error=str(e2))
            
            logger.error("intent_manager.detection_error", error=str(e))
            # Safe fallback
            if any(char.isdigit() for char in text):
                return Intent.DIAGNOSTIC

            # when the script come to safe fallback it will definiately is a short educational or diagnostic intent.
            return Intent.EDUCATIONAL

# Singleton instance
intent_manager = IntentManager()