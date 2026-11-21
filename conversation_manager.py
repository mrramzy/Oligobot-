# -*- coding: utf-8 -*-
"""
Conversation Manager with Summarization Strategy

This module provides a manager to keep the chat history concise and prevent it from
exceeding the LLM's context window limit.
v1.0 - Initial implementation of the summarization strategy.
"""

from typing import List, Dict
from ai_models import generate_response # This can cause circular dependency, but acceptable for now.
from config import ADMIN_ID, AVAILABLE_MODELS # Import necessary configs

class ConversationManager:
    """
    Manages chat history by summarizing older parts of the conversation
    once it reaches a certain length.
    
    How to use in your application (e.g., app.py):
    1. `from conversation_manager import ConversationManager`
    2. `convo_manager = ConversationManager()`
    3. Before calling the RAG engine:
       `managed_history = await convo_manager.manage(st.session_state.chat_history)`
    4. Pass the `managed_history` to the RAG engine.
       `response, sources = await rag_system.process_query(..., chat_history=managed_history, ...)`
    5. Update your session state with the new, managed history.
       `st.session_state.chat_history = managed_history`
    """
    def __init__(self, max_history_messages: int = 10, messages_to_keep: int = 4):
        """
        Initializes the conversation manager.

        Args:
            max_history_messages: The threshold of total messages at which to trigger summarization.
            messages_to_keep: The number of most recent messages to keep as-is after summarization.
        """
        if max_history_messages <= messages_to_keep:
            raise ValueError("max_history_messages must be greater than messages_to_keep")
        
        self.max_history_messages = max_history_messages
        self.messages_to_keep = messages_to_keep
        self.SUMMARIZATION_PROMPT = """
        این مکالمه را در یک پاراگراف کوتاه به زبان فارسی و به صورت سوم شخص خلاصه کن.
        این خلاصه به عنوان حافظه برای یک ربات هوش مصنوعی استفاده خواهد شد.
        فقط نکات کلیدی، سوالات اصلی کاربر و اطلاعات مهم ارائه شده را ذکر کن. از پرداختن به جزئیات غیرضروری خودداری کن.
        مثال: 'کاربر در مورد آنمی فقر آهن و علائم آن سوال کرد و ربات توضیحاتی در مورد خستگی، رنگ‌پریدگی و رنج نرمال هموگلوبین ارائه داد.'
        
        حالا این مکالمه را خلاصه کن:
        """

    async def manage(self, chat_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Manages the chat history. If it's too long, it summarizes the older parts.
        It intelligently handles an existing summary and appends to it.
        """
        if len(chat_history) < self.max_history_messages:
            return chat_history

        print(f"Conversation history length ({len(chat_history)}) exceeds threshold. Triggering summarization...")

        # Determine which part of the history to summarize
        parts_to_summarize = chat_history[:-self.messages_to_keep]
        recent_messages = chat_history[-self.messages_to_keep:]

        # Check if the part to be summarized already contains a summary from a previous run
        previous_summary = ""
        if parts_to_summarize and parts_to_summarize[0].get("role") == "system":
            # Extract previous summary and the messages that came after it
            previous_summary = parts_to_summarize[0]['content']
            # The rest of the messages are the ones to be summarized now
            new_messages_to_summarize = parts_to_summarize[1:]
        else:
            new_messages_to_summarize = parts_to_summarize

        # Format the messages that need to be summarized into a single block of text
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in new_messages_to_summarize])
        
        # Combine the previous summary with the new conversation text
        full_text_to_summarize = f"{previous_summary}\n{conversation_text}"
        
        # Prepare the final prompt for the LLM
        final_prompt = f"{self.SUMMARIZATION_PROMPT}\n\n{full_text_to_summarize}"
        
        # ✅ FIX: Call the LLM correctly to get the new, combined summary.
        # Use the lightweight model for this cost-effective task.
        light_model_name = AVAILABLE_MODELS["gemini"]["light_model"]
        
        summary_text = await generate_response(
            user_id=0, # System task, no specific user
            api_payload=[final_prompt],
            admin_id=ADMIN_ID,
            model=light_model_name
        )

        # Create the new system message containing the updated summary
        new_summary_message = {
            "role": "system",
            "content": f"خلاصه مکالمات قبلی: {summary_text}"
        }

        # Construct the final, managed chat history
        new_chat_history = [new_summary_message] + recent_messages
        
        print(f"Summarization complete. New history length: {len(new_chat_history)}")
        return new_chat_history
