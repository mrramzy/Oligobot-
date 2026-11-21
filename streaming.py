# -*- coding: utf-8 -*-
# Streaming response handler - extracted from handlers.py

import time
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from utils import safe_markdown_partial

# Telegram limits sendChatAction to ~1/5s. Throttle to avoid wasted HTTP calls.
CHAT_ACTION_THROTTLE = 5.0


async def stream_response(update, context, response_stream, validator, citation_manager,
                          retrieved_docs, show_references, detected_intent, eadl,
                          user_id, text, augmented_text):
    """Stream the response from the RAG system with live editing."""
    full_text = ""
    last_update_time = 0.0
    last_sent_text = ""
    last_sent_len = 0
    first_frame_sent = False
    processing_msg = None
    last_chat_action_time = 0.0

    MIN_CHARS_TO_EDIT = 15

    def _natural_delay(text_so_far: str, new_chunk: str) -> float:
        """Calculate a human-like delay based on content context."""
        base = 0.15
        if new_chunk and new_chunk[-1] in ".?!?\n۔":
            return base + 0.35
        if new_chunk and new_chunk[-1] in ",;،؛":
            return base + 0.12
        if new_chunk and new_chunk[-1] in "([":
            return base + 0.08
        if len(full_text) > 200 and len(full_text) < 600:
            return base * 0.7
        return base

    async for chunk in response_stream:
        full_text += chunk
        now = time.time()
        delay = _natural_delay(full_text, chunk)

        enough_new = (len(full_text) - last_sent_len) >= MIN_CHARS_TO_EDIT
        if (now - last_update_time) > delay and enough_new:
            text_to_send = safe_markdown_partial(full_text) + " ▌"
            if text_to_send != last_sent_text:
                try:
                    if not first_frame_sent:
                        processing_msg = await update.message.reply_text(text_to_send, parse_mode=ParseMode.MARKDOWN)
                        first_frame_sent = True
                    else:
                        await processing_msg.edit_text(text_to_send, parse_mode=ParseMode.MARKDOWN)
                    last_sent_text = text_to_send
                    last_sent_len = len(full_text)
                    last_update_time = now
                except BadRequest as e:
                    if "not modified" not in str(e).lower():
                        try:
                            if processing_msg:
                                await processing_msg.edit_text(full_text + " ▌")
                            else:
                                processing_msg = await update.message.reply_text(full_text + " ▌")
                            last_sent_text = text_to_send
                            last_sent_len = len(full_text)
                            last_update_time = now
                            first_frame_sent = True
                        except BadRequest:
                            pass
                # Throttled typing indicator — max once per CHAT_ACTION_THROTTLE seconds
                if (now - last_chat_action_time) >= CHAT_ACTION_THROTTLE:
                    last_chat_action_time = now
                    try:
                        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
                    except Exception:
                        pass

    # Final cleanup and formatting
    cleaned = validator.sanitize_output(full_text)
    final_answer = citation_manager.format_answer_with_citations(
        retrieved_docs=retrieved_docs, llm_response=cleaned, show_references=show_references
    )

    return final_answer, processing_msg
