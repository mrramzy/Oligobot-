# -*- coding: utf-8 -*-
import os
import sys
import logging
from logging_config import get_logger
logger = get_logger(__name__)
import json
import asyncio
# رفع باگ تداخل asyncio در ویندوز برای تلگرام و HTTPX
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from PIL import Image
from dotenv import load_dotenv
import numpy as np

# 🔧 PATCH: Fix for NumPy 2.0 compatibility (ChromaDB issue)
if hasattr(np, 'float64') and not hasattr(np, 'float_'):
    np.float_ = np.float64
if hasattr(np, 'int64') and not hasattr(np, 'int_'):
    np.int_ = np.int64
if hasattr(np, 'uint64') and not hasattr(np, 'uint'):
    np.uint = np.uint64

# Load environment variables FIRST
load_dotenv()

# ==========================================
# 🛡️ WARP PROXY SETTINGS (Network Config)
# ==========================================
# Enable WARP proxy to bypass ArvanCloud IP blocks.
# Port 40000 is default for WARP. Use 10809 for other panels.
# Uncomment the lines below to enable:
# os.environ['HTTP_PROXY'] = 'socks5://127.0.0.1:40000'
# os.environ['HTTPS_PROXY'] = 'socks5://127.0.0.1:40000'
# os.environ['ALL_PROXY'] = 'socks5://127.0.0.1:40000'

# Check if WARP proxy is enabled via .env
WARP_ENABLED = os.getenv("WARP_ENABLED", "0") == "1"
WARP_PORT = os.getenv("WARP_PORT", "40000")
if WARP_ENABLED:
    proxy_url = f"socks5://127.0.0.1:{WARP_PORT}"
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url
    os.environ['ALL_PROXY'] = proxy_url
    logger.info(f"🛡️ WARP Proxy ENABLED on port {WARP_PORT}")

import redis
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters

# --- FINAL ARCHITECTURE IMPORTS ---
# These are the high-level components our app orchestrates.
from rag_engine import RAGSystem
from conversation_manager import ConversationManager
from redis_cache import RAGCache

# --- SUPPORTING MODULE IMPORTS ---
# These provide specific, encapsulated functionalities.
import handlers
from feedback_handlers import handle_eadl_callback # ✅ Import Dashboard Handler
from user_manager import UserManager
from case_memory import CaseMemoryStore
from key_manager import KeyManager
from utils import (
    get_time_metadata,
    smart_log,
    detect_language
)
from config import TELEGRAM_TOKEN, ADMIN_ID, MODEL_NAME, PRIMARY_PROVIDER, EMBEDDING_MODEL, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, WEBHOOK_URL, PORT
from intent_manager import Intent # ✅ Import Intent for checking
from subscription_manager import subscription_manager
from state_manager import RedisStateManager

# ==========================================#
# 🔐 INITIALIZATION & CONFIGURATION
# ==========================================#
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

if not TELEGRAM_TOKEN:
    logger.error("❌ CRITICAL: TELEGRAM_TOKEN not found!")
    sys.exit(1)

# ==========================================#
# 💾 PERSISTENCE LAYER (REDIS MANAGER)
# ==========================================#


# ==========================================#
# 🧠 AI SYSTEM & GLOBAL STATE INITIALIZATION
# ==========================================#
key_manager = KeyManager()  # Initialize API key manager first
rag_system = RAGSystem()
convo_manager = ConversationManager()
user_manager = UserManager()
rag_cache = RAGCache(ttl=3600)  # Existing Cache for RAG responses
case_store = CaseMemoryStore()
eadl_manager = rag_system.eadl # Use the EADL manager instance from RAG system

# --- NEW: State Manager & Concurrency Control ---
state_manager = RedisStateManager(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    db=REDIS_DB, 
    password=REDIS_PASSWORD
)
processing_semaphore = asyncio.Semaphore(5) # Limit to 5 concurrent heavy RAG processes

logger.info(f"\n{'='*60}\n🤖 OligoSoft Bot - Final Architecture Deployed\n   AI Model: {PRIMARY_PROVIDER.upper()} ({MODEL_NAME})\n   Embeddings: {EMBEDDING_MODEL}\n{'='*60}\n")

# ==========================================#
# 🧠 MEMORY & MESSAGE HANDLING
# ==========================================#
async def update_history(uid: int, role: str, content: str) -> None:
    history = await state_manager.async_get_history(uid)
    history.append({"role": role, "content": content})
    await state_manager.async_save_history(uid, history)

# ==========================================#
# 🤖 THE FINAL, CORRECT, STREAMLINED CORE LOGIC
# ==========================================#
async def handle_user_message(
    user_id: int, 
    text: str, 
    image: Optional[Image.Image] = None, 
    file_content: Optional[str] = None,
    show_references: bool = True,
    intent: Any = None,
    career_context: str = ""
) -> Tuple[str, Optional[str], Dict[str, Any]]:
    # 1. Manage Conversation History    
    # 🔔 CHECK FOR NOTIFICATIONS (New Feature)
    notifications = user_manager.get_and_clear_notifications(user_id)
    if notifications:
        for note in notifications:
            # We return the notification as part of the answer or prepend it?
            # Better to prepend it to the final answer or handle it in handlers.py. 
            # But since we return text here, let's prepend.
            # Actually, let's just prepend to the text returned.
            pass # Logic moved to return statement or handled separately? 
            # Let's prepend to the final answer for simplicity in this architecture.
            
    current_history = await state_manager.async_get_history(user_id)
    managed_history = await convo_manager.manage(current_history)
    await state_manager.async_save_history(user_id, managed_history)

    # 1.5 Check Redis Cache (Only for text queries without files/images)
    if not image and not file_content:
        intent_name = intent.name if intent else "UNKNOWN"
        cached_result = rag_cache.get(text, user_id, intent_name)
        if cached_result:
            smart_log(user_id=user_id, intent="cache_hit", mode="text", time_meta=get_time_metadata(), has_image=False, strategy={"use_rag": False})
            ans = cached_result.get("answer")
            if intent_name in ["EDUCATIONAL", "CASUAL"] and ans:
                ans = f"💡 *اتفاقا این سوال پرکاربردی هست و خیلی‌ها می‌پرسن!*\n\n{ans}"
            return ans, cached_result.get("sources"), cached_result.get("eadl_meta", {})

    # 2. Determine Mode and Strategy
    mode = "image" if image else "document" if file_content else "text"
    effective_text = f"{file_content}\n\n{text}" if file_content else text
    
    # ✅ Determine if RAG is needed based on Intent
    # CASUAL intent should NOT trigger RAG search, just pure LLM response.
    use_rag = True
    if intent == Intent.CASUAL:
        use_rag = False

    strategy = {
        "use_rag": use_rag,
        "mode": mode,
        "intent": intent.name if intent else "UNKNOWN",
        "language": detect_language(text),
        "show_references": show_references,
        "career_context": career_context
    }
    
    time_meta: Dict[str, Any] = get_time_metadata()
    metadata: Dict[str, Any] = {"time_meta": time_meta}

    smart_log(
        user_id=user_id, 
        intent=strategy["intent"], 
        mode=mode, time_meta=time_meta, 
        has_image=bool(image),
        strategy=strategy # ✅ FIX: Added missing argument
    )

    # 3. Call the RAG System (Protected by Semaphore)
    async with processing_semaphore:
        result = await rag_system.process_query(
            user_id=user_id,
            user_query=effective_text,
            chat_history=managed_history,
            strategy=strategy,
            image_obj=image,
            metadata=metadata,
            case_store=case_store  # ✅ Pass the memory store
        )
    
    # Handle tuple unpacking & Update Usage
    await state_manager.async_increment_usage(user_id)
    subscription_manager.increment_usage(user_id)
    
    eadl_meta = {}
    if isinstance(result, tuple):
        if len(result) == 3:
            final_answer, sources_text, eadl_meta = result
        elif len(result) == 2:
            final_answer, sources_text = result
    else:
        final_answer = result
        sources_text = None
        
    # 4. Cache the result (if text-only)
    if not image and not file_content and final_answer:
        # Cache now includes eadl_meta and is intent-aware (Shared vs Private)
        intent_name = intent.name if intent else "UNKNOWN"
        rag_cache.set(text, user_id, {"answer": final_answer, "sources": sources_text, "eadl_meta": eadl_meta}, intent_name)
    
    # 🔔 Append Notifications to Answer
    if notifications:
        note_text = "\n\n".join([f"🔔 {n}" for n in notifications])
        final_answer = f"{note_text}\n\n━━━━━━━━━━━━\n{final_answer}"
        
    return final_answer, sources_text, eadl_meta

async def handle_user_message_stream(
    user_id: int, 
    text: str, 
    image: Optional[Image.Image] = None, 
    file_content: Optional[str] = None,
    show_references: bool = True,
    intent: Any = None,
    career_context: str = ""
) -> Tuple[AsyncGenerator[str, None], List[Any], Dict[str, Any]]:
    """
    Streaming version of the core logic.
    Returns a generator for the LLM response and metadata for post-processing.
    """
    # 1. Manage Conversation History
    current_history = await state_manager.async_get_history(user_id)
    managed_history = await convo_manager.manage(current_history)
    await state_manager.async_save_history(user_id, managed_history)

    # 2. Determine Mode and Strategy
    mode = "image" if image else "document" if file_content else "text"
    effective_text = f"{file_content}\n\n{text}" if file_content else text
    
    use_rag = intent not in [Intent.CASUAL, Intent.IRRELEVANT]

    strategy = {
        "use_rag": use_rag,
        "mode": mode,
        "intent": intent.name if intent else "UNKNOWN",
        "language": detect_language(text),
        "show_references": show_references,
        "career_context": career_context
    }
    
    time_meta: Dict[str, Any] = get_time_metadata()
    metadata: Dict[str, Any] = {"time_meta": time_meta}

    # 3. Call the streaming RAG System (Protected by Semaphore)
    async with processing_semaphore:
        llm_stream, retrieved_docs, eadl_meta = await rag_system.process_query_stream(
            user_id=user_id, user_query=effective_text, chat_history=managed_history,
            strategy=strategy, image_obj=image, metadata=metadata
        )
    
    await state_manager.async_increment_usage(user_id)
    subscription_manager.increment_usage(user_id)
    return llm_stream, retrieved_docs, eadl_meta

# ==========================================#
# 🚀 BOT LAUNCHER
# ==========================================#
if __name__ == '__main__':
    # 🔧 FIX: Windows Event Loop Policy (Prevents "Event loop is closed" errors on Windows)
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logger.info("🚀 OligoSoft Bot Server Starting...")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # --- FINAL: Inject Dependencies into Bot Data ---
    app.bot_data["user_manager"] = user_manager
    app.bot_data["rag_system"] = rag_system
    app.bot_data["case_store"] = case_store
    app.bot_data["eadl_manager"] = eadl_manager # ✅ Inject EADL Manager
    # ⚠️ Deprecated direct dict access, injecting manager instead
    app.bot_data["state_manager"] = state_manager 
    # app.bot_data["user_chat_history"] = ... (Removed to force usage of manager)
    
    app.bot_data["handle_user_message"] = handle_user_message
    app.bot_data["handle_user_message_stream"] = handle_user_message_stream
    app.bot_data["update_history"] = update_history
    app.bot_data["rag_cache"] = rag_cache
    app.bot_data["ADMIN_ID"] = ADMIN_ID
    
    # Register all handlers
    app.add_handler(CommandHandler('start', handlers.start))
    app.add_handler(CommandHandler('new', handlers.handle_new_command))
    app.add_handler(CommandHandler('setname', handlers.handle_setname_command))
    app.add_handler(CommandHandler('feedback', handlers.handle_feedback_command))
    app.add_handler(CommandHandler('subscription', handlers.handle_subscription_command))
    app.add_handler(CommandHandler('memory', handlers.handle_memory_command))
    app.add_handler(CommandHandler('memory_clear', handlers.handle_memory_clear_command))
    # ✅ Register Feedback Callback Handler
    app.add_handler(CallbackQueryHandler(handle_eadl_callback, pattern="^eadl:")) # ✅ Updated pattern
    app.add_handler(CallbackQueryHandler(handlers.handle_callback)) # Keep original for other buttons
    app.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.handle_document))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.handle_message))
    
    # --- MODULAR EXECUTION: Webhook vs Polling ---
    if WEBHOOK_URL:
        logger.info(f"🚀 Starting in WEBHOOK mode on port {PORT}...")
        logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}/{TELEGRAM_TOKEN}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        )
    else:
        logger.info("✅ Starting in POLLING mode (Dev/Beta)...")
        app.run_polling(drop_pending_updates=True)
