# -*- coding: utf-8 -*-
# FINAL HANDLERS - MERGED FROM V9 & V10

import os
import time
import uuid
import io
import tempfile
import random
import asyncio
import structlog
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

# Local Imports
from config import (
    BTN_NEW, BTN_QUOTA, BTN_PROFILE_HELP, BTN_SETTINGS, BTN_SUPPORT,
    BTN_SET_NAME, BTN_FEEDBACK, BTN_WITH_REF, BTN_WITHOUT_REF, BTN_BACK,
    REQUIRED_CHANNELS, MAX_REQUESTS_PER_USER, BTN_EXPERT_PANEL, ADMIN_USER_IDS,
    BTN_SUBSCRIPTION, BTN_CAREER, BTN_CAREER_ON, BTN_CAREER_OFF, BTN_CAREER_SELECT
)
from user_manager import UserManager
from subscription_manager import subscription_manager
from protocol_enforcer import protocol_enforcer
from input_validator import InputValidator
from utils import (
    extract_text_from_file,
    sanitize_for_llm,
    get_time_metadata,
    safe_markdown_partial,
)
from intent_manager import intent_manager, Intent
from feedback_handlers import show_expert_dashboard, handle_eadl_callback

from ui_handlers import (
    get_quota_info, can_user_use, send_smart_message, check_membership, send_join_request,
    handle_new_chat, handle_profile_help, handle_quota, handle_settings, handle_set_name,
    handle_feedback, handle_with_references, handle_without_references, handle_back, handle_support,
    handle_new_command, handle_setname_command, handle_feedback_command,
    handle_subscription_command, handle_expert_panel_btn, handle_subscription,
    handle_career, handle_career_on, handle_career_off, handle_career_select, handle_career_choice,
    CAREER_BTN_MAP, MAIN_KEYBOARD, SETTINGS_KEYBOARD, CAREER_KEYBOARD
)
from streaming import stream_response

# Initialize the logger for this module
logger = structlog.get_logger(__name__)

# ==================== COMMAND & MESSAGE HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with onboarding for new users."""
    user_id = update.effective_user.id
    log = logger.bind(user_id=user_id, command="/start")

    if not await check_membership(user_id, context):
        await send_join_request(update)
        return

    user_manager = context.bot_data["user_manager"]
    is_new = not user_manager.exists(user_id)
    if is_new:
        user_manager.create_user(user_id, username=update.effective_user.username, first_name=update.effective_user.first_name)
        log.info("start.new_user_created")

    name = user_manager.get_display_name(user_id)
    log.info("start.user_greeted", display_name=name)

    # Onboarding for new users: force career, name, reference setup
    if is_new:
        context.user_data["onboarding_step"] = "name"
        await update.message.reply_text(
            f"👋 **خوش آمدید به OligoSoft Bot!**\n\n"
            f"من دستیار هوشمند آزمایشگاهی شما هستم.\n"
            f"برای شروع، لطفاً **نام نمایشی** خود را وارد کنید:",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text(f"👋 درود **{name}** عزیز!", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory command to view user memory."""
    user_id = update.effective_user.id
    
    from user_memory import get_user_memory
    memory = get_user_memory()
    topics = memory.get_all_topics(user_id)
    stats = memory.get_stats(user_id)
    
    if not topics:
        text_msg = (
            "🧠 **حافظه مکالمات شما**\n\n"
            "هنوز موضوعی ثبت نشده است.\n"
            "با پرسیدن سوالات آزمایشگاهی، موضوعات مهم در حافظه من ذخیره می‌شوند.\n\n"
            "💡 برای پاک کردن حافظه: `/memory_clear`"
        )
    else:
        topic_lines = []
        for i, t in enumerate(topics[:10], 1):
            kw = ", ".join(t.get("keywords", [])[:3])
            rel = t.get("relevance", 0)
            bar = "█" * int(rel * 5) + "░" * (5 - int(rel * 5))
            topic_lines.append(f"{i}. **{t['name']}** [{bar}] ({kw})")
        
        topics_text = "\n".join(topic_lines)
        text_msg = (
            f"🧠 **حافظه مکالمات شما**\n\n"
            f"📊 تعداد موضوعات: {stats['topic_count']}\n"
            f"🔢 تعداد سوالات: {stats['total_queries']}\n\n"
            f"**موضوعات ذخیره شده:**\n{topics_text}\n\n"
            f"💡 برای پاک کردن حافظه: `/memory_clear`"
        )
    
    await update.message.reply_text(text_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_memory_clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory_clear command to clear user memory."""
    user_id = update.effective_user.id
    from user_memory import get_user_memory
    get_user_memory().clear(user_id)
    await update.message.reply_text("🗑️ **حافظه مکالمات پاک شد.**\nاز این پس موضوعات جدید را یاد خواهم گرفت.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

BUTTON_HANDLERS = {
    BTN_NEW: handle_new_chat,
    BTN_PROFILE_HELP: handle_profile_help,
    BTN_QUOTA: handle_quota,
    BTN_SETTINGS: handle_settings,
    BTN_SUPPORT: handle_support,
    BTN_SET_NAME: handle_set_name,
    BTN_FEEDBACK: handle_feedback,
    BTN_WITH_REF: handle_with_references,
    BTN_WITHOUT_REF: handle_without_references,
    BTN_BACK: handle_back,
    BTN_EXPERT_PANEL: handle_expert_panel_btn,
    BTN_SUBSCRIPTION: handle_subscription,
    BTN_CAREER: handle_career,
    BTN_CAREER_ON: handle_career_on,
    BTN_CAREER_OFF: handle_career_off,
    BTN_CAREER_SELECT: handle_career_select,
}

# Register career choice buttons so they route to handle_career_choice
# instead of falling through to the RAG pipeline
for _career_btn_text in CAREER_BTN_MAP:
    BUTTON_HANDLERS[_career_btn_text] = handle_career_choice
RATE_LIMIT_SECONDS = 3.0

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages with input validation and structured logging."""
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""
    log = logger.bind(user_id=user_id, text=text, update_id=update.update_id)
    log.info("handle_message.received")

    # --- EADL COMMENT HANDLING (Priority Check) ---
    # اگر کاربر در حال ثبت نظر اصلاحی برای یک کیس EADL است، این پیام به‌عنوان نظر ثبت شود.
    if context.user_data.get("eadl_comment_case_id"):
        case_id = context.user_data["eadl_comment_case_id"]
        msg_id = context.user_data.get("eadl_comment_msg_id")
        comment = text
        eadl_manager = context.bot_data.get("eadl_manager")

        # پاک‌سازی state مهم: حتی اگر خطا رخ داد، state نباید گیر کند
        del context.user_data["eadl_comment_case_id"]
        if "eadl_comment_msg_id" in context.user_data:
            del context.user_data["eadl_comment_msg_id"]

        if not eadl_manager:
            await update.message.reply_text("❌ خطا: سیستم EADL در دسترس نیست.", reply_markup=MAIN_KEYBOARD)
            return

        if not (eadl_manager.is_admin(user_id) or user_id in ADMIN_USER_IDS):
            await update.message.reply_text("⛔ دسترسی غیرمجاز - فقط ادمین‌ها می‌توانند کیس را بررسی کنند.", reply_markup=MAIN_KEYBOARD)
            return

        try:
            await eadl_manager.resolve_case(case_id, user_id, "REJECT", comment)

            try:
                case = await eadl_manager.get_case(case_id)
                user_manager = context.bot_data.get("user_manager")
                if case and user_manager and comment.strip():
                    target_uid = case.get("user_id")
                    topic = (case.get("query") or "")[:40]
                    if target_uid and int(target_uid) != user_id:
                        user_manager.add_notification(
                            int(target_uid),
                            f"🔬 یک متخصص پاسخ قبلی شما درباره‌ی «{topic}…» را بازبینی و تکمیل کرد:\n\n{comment}"
                        )
            except Exception as e:
                logger.warning(f"EADL user notification skipped: {e}")

            if msg_id:
                try:
                    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg_id, text="✅ اصلاحیه دریافت شد.", parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

            await update.message.reply_text(
                "✅ **نظر اصلاحی شما با موفقیت ثبت شد.**\n\nسیستم از این داده برای بهبود استفاده خواهد کرد.\nاکنون می‌توانید به گفتگوی عادی ادامه دهید.",
                reply_markup=MAIN_KEYBOARD,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"EADL resolve error: {e}")
            await update.message.reply_text("❌ خطا در ثبت نظر.", reply_markup=MAIN_KEYBOARD)
        return  # ← مهم: EADL comment هیچوقت نباید به مسیر RAG بره

    # --- ONBOARDING STATE MACHINE ---
    onboarding_step = context.user_data.get("onboarding_step")
    if onboarding_step:
        user_manager = context.bot_data["user_manager"]
        if onboarding_step == "name":
            if 2 <= len(text) <= 50:
                user_manager.set_display_name(user_id, text)
                context.user_data["onboarding_step"] = "career"
                career_text = "شغل خود را انتخاب کنید:"
                from ui_handlers import CAREER_KEYBOARD
                await update.message.reply_text(
                    f"✅ نام **{text}** ثبت شد!\n\n{career_text}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=CAREER_KEYBOARD
                )
            else:
                await update.message.reply_text("❌ نام باید بین ۲ تا ۵۰ کاراکتر باشد. دوباره وارد کنید:")
            return

        if onboarding_step == "career":
            from ui_handlers import CAREER_BTN_MAP, CAREER_KEYBOARD
            career = CAREER_BTN_MAP.get(text)
            if career:
                user_manager.set_career(user_id, career)
                user_manager.set_career_enabled(user_id, True)
                info = user_manager.CAREER_OPTIONS[career]
                context.user_data["onboarding_step"] = "references"
                await update.message.reply_text(
                    f"{info['emoji']} **{info['label']}** ({info['label_fa']}) انتخاب شد!\n\n"
                    f"آیا می‌خواهید **رفرنس‌ها** (منابع و صفحات) در پاسخ‌ها نمایش داده شوند؟",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("✅ بله، نمایش رفرنس"), KeyboardButton("❌ خیر، بدون رفرنس")],
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text("❌ لطفاً یکی از گزینه‌های بالا را انتخاب کنید:", reply_markup=CAREER_KEYBOARD)
            return

        if onboarding_step == "references":
            if "بله" in text or "نمایش" in text:
                user_manager.set_show_references(user_id, True)
                ref_text = "رفرنس‌ها فعال شدند"
            else:
                user_manager.set_show_references(user_id, False)
                ref_text = "رفرنس‌ها غیرفعال شدند"
            context.user_data.pop("onboarding_step", None)
            name = user_manager.get_display_name(user_id)
            await update.message.reply_text(
                f"✅ {ref_text}!\n\n"
                f"🎉 **تنظیمات تکمیل شد!**\n\n"
                f"درود **{name}** عزیز! اکنون آماده‌ام سوالات آزمایشگاهی شما را پاسخ دهم.\n"
                f"هر سوالی دارید بپرسید!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_KEYBOARD
            )
            return
        return

    # Dependency Injection Retrieval
    user_manager = context.bot_data["user_manager"]
    handle_user_message = context.bot_data["handle_user_message"]
    handle_user_message_stream = context.bot_data.get("handle_user_message_stream")
    update_history = context.bot_data["update_history"]
    state_manager = context.bot_data["state_manager"]
    case_store = context.bot_data["case_store"]
    eadl = context.bot_data.get("eadl_manager")

    if not await state_manager.async_is_verified(user_id) and not await check_membership(user_id, context):
        await send_join_request(update)
        return
    await state_manager.async_add_verified_user(user_id)

    if not await can_user_use(user_id, context):
        access = subscription_manager.check_access(user_id)
        if access["reason"] == "subscription_expired":
            msg = "⛔ اشتراک شما منقضی شده است. لطفاً اشتراک خود را تمدید کنید."
        elif access["reason"] == "daily_limit_reached":
            msg = "⛔ سهمیه امروز شما به پایان رسیده است. فردا مجدداً تلاش کنید."
        else:
            msg = "⛔ دسترسی شما محدود شده است. لطفاً با پشتیبانی تماس بگیرید."
        await update.message.reply_text(msg, reply_markup=MAIN_KEYBOARD)
        return

    # --- RATE LIMITER ---
    last_time = context.user_data.get("last_message_time", 0)
    current_time = time.time()
    if current_time - last_time < RATE_LIMIT_SECONDS and user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⏳ لطفاً کمی صبر کنید...", reply_markup=MAIN_KEYBOARD)
        return
    context.user_data["last_message_time"] = current_time

    if context.user_data.get("waiting_for_name"):
        name = text
        if 2 <= len(name) <= 50:
            user_manager.set_display_name(user_id, name)
            context.user_data["waiting_for_name"] = False
            await update.message.reply_text(f"✅ نام شما به **{name}** تغییر کرد.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text("❌ نام باید بین ۲ تا ۵۰ کاراکتر باشد.", reply_markup=SETTINGS_KEYBOARD)
        return

    if context.user_data.get("waiting_for_feedback"):
        log.warning("user_feedback_report", feedback_content=text, status="needs_review")
        context.user_data["waiting_for_feedback"] = False
        await update.message.reply_text("✅ بازخورد شما ثبت شد. تیم فنی آن را بررسی خواهد کرد.", reply_markup=SETTINGS_KEYBOARD)
        return

    if text in BUTTON_HANDLERS:
        log.info("handle_message.button_handler_triggered", button=text)
        await BUTTON_HANDLERS[text](update, context)
        return

    # Input validation
    try:
        InputValidator().validate_query(text)
    except ValueError as e:
        log.warning("handle_message.invalid_input", error=str(e))
        await update.message.reply_text(f"❌ ورودی نامعتبر است: {e}")
        return

    # --- Intent-Based Routing ---
    user_history = await state_manager.async_get_history(user_id)
    detected_intent = await intent_manager.detect_intent(text, user_history)
    log.info("handle_message.intent_detected", intent=detected_intent.name)

    # --- Critique Detection (for protocol enforcement bypass) ---
    # کلمات انتقادی که نشان می‌ده کاربر در حال نقد پاسخ قبلی است، نه پرسش جدید.
    # نکته: کلماتی مثل "چرا" یا "کدام" در سوالات عادی هم استفاده می‌شوند،
    # پس باید با کلمات مرجعِ پاسخِ قبلی (گفتی، اشتباه، قبلی) ترکیب شوند.
    strong_critique_keywords = ["گفتی", "اشتباه", "قبلی", "غلط", "درست نبود"]
    general_critique_keywords = ["چرا", "چطور", "مگه", "تفاوت", "فرق", "توضیح", "نظر", "کدام", "کدوم"]
    has_strong_critique = any(k in text for k in strong_critique_keywords)
    has_general_critique = any(k in text for k in general_critique_keywords)
    # فقط زمانی protocol enforcement غیرفعال شود که نشانه قوی انتقاد وجود داشته باشد
    # یا حداقل دو نشانه عمومی (برای کاهش false positive)
    is_critique = has_strong_critique or (has_general_critique and len(user_history) >= 2 and any(m.get("role") == "assistant" for m in user_history[-4:]))
    should_enforce_protocol = not is_critique

    if detected_intent == Intent.CASUAL:
        # Check if this is a repeated greeting (user already greeted recently)
        greeting_keywords = ["درود", "سلام", "خسته نباشید", "وقت بخیر", "شب بخیر", "صبح بخیر", "عصر بخیر"]
        is_greeting = any(k in text for k in greeting_keywords)

        if is_greeting and len(user_history) >= 2:
            # Check if bot already greeted in last 2 messages
            recent_bot_msgs = [m for m in user_history[-4:] if m.get("role") == "assistant"]
            if recent_bot_msgs:
                # Brief response for repeated greetings
                brief_responses = [
                    "درود دوباره 🙂",
                    "سلام، چطور می‌تونم کمک کنم؟",
                    "سلام دوباره 👋",
                    "خوشحالم که برگشتی. سوالی داری؟",
                ]
                brief_response = random.choice(brief_responses)
                await update.message.reply_text(brief_response, reply_markup=MAIN_KEYBOARD)
                await update_history(user_id, "user", text)
                await update_history(user_id, "assistant", brief_response)
                return

    if detected_intent == Intent.IRRELEVANT:
        responses = [
            "من تمرکزم رو گذاشتم روی مباحث علوم آزمایشگاهی. اگر سوالی تو این حوزه داری، در خدمتم! 🔬",
            "راستش من برای پاسخ به سوالات پزشکی و آزمایشگاهی آموزش دیدم. خوشحال می‌شم اگر تو این زمینه کمکی ازم برمیاد بگی.",
            "حیطه تخصصی من علوم آزمایشگاهی هست. سوال دیگه‌ای داری که بتونم کمکت کنم؟",
            "من یه دستیار هوشمند آزمایشگاهی‌ام و اطلاعاتم تو حوزه‌های دیگه محدوده. بیا برگردیم سر بحث شیرین آزمایشگاه! 😉",
            "متاسفانه تو این زمینه نمی‌تونم نظر بدم، اما هر سوالی راجع به آزمایش، تشخیص یا تفسیر نتایج داشته باشی، پایه‌ام."
        ]
        await update.message.reply_text(random.choice(responses), reply_markup=MAIN_KEYBOARD)
        return

    # --- For DIAGNOSTIC and EDUCATIONAL, proceed to RAG ---

    if detected_intent == Intent.DIAGNOSTIC and should_enforce_protocol:
        log.info("handle_message.diagnostic_path_activated")
        
        extracted_data = protocol_enforcer.extract_entities(text)
        if extracted_data:
            case_store.update_case(user_id, extracted_data)
        
        current_case_data = case_store.get_raw_case(user_id)
        is_allowed, rejection_msg = protocol_enforcer.validate_diagnostic_request(current_case_data)
        
        if not is_allowed:
            log.info("handle_message.protocol_warning_bypassed", reason=rejection_msg)

    # 🚀 GUI UPDATE: No initial indicator — let the stream speak for itself
    processing_msg = None
    
    try:
        # Inject Memory Context for all relevant intents
        case_summary = case_store.get_case_summary(user_id)
        augmented_text = f"{case_summary}\n\nUser Query: {text}" if case_summary else text
        
        show_references = user_manager.get_show_references(user_id)
        
        case_id = str(uuid.uuid4())[:8]
        log.info("handle_message.sending_response", case_id=case_id, intent=detected_intent.name)
        
        if handle_user_message_stream:
            # --- Streaming Path ---
            career_ctx = user_manager.get_career_context(user_id)
            response_stream, retrieved_docs, eadl_meta = await handle_user_message_stream(
                user_id=user_id, text=augmented_text, show_references=show_references,
                intent=detected_intent, career_context=career_ctx
            )
            
            final_answer, processing_msg = await stream_response(
                update, context, response_stream,
                InputValidator(),
                context.bot_data["rag_system"].citation_manager,
                retrieved_docs, show_references,
                detected_intent, eadl, user_id, text, augmented_text
            )

            if detected_intent == Intent.DIAGNOSTIC:
                if processing_msg:
                    try:
                        await processing_msg.delete()
                    except Exception:
                        pass
                await update.message.reply_text(final_answer, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

                if eadl:
                    await eadl.submit_case(
                        user_id, text, final_answer,
                        eadl_meta.get("domain", "general"),
                        eadl_meta.get("keywords", []),
                        eadl_meta,
                    )
            elif processing_msg:
                try:
                    await processing_msg.edit_text(final_answer, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    await update.message.reply_text(final_answer, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)
            else:
                await update.message.reply_text(final_answer, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

            await update_history(user_id, "user", augmented_text)
            await update_history(user_id, "assistant", final_answer)

            # Extract and store topics (fire-and-forget, non-blocking)
            async def _extract_and_store():
                try:
                    from user_memory import extract_topics_from_conversation, get_user_memory
                    topics = await extract_topics_from_conversation(text, final_answer)
                    if topics:
                        get_user_memory().add_topics(user_id, topics)
                except Exception as e:
                    logger.warning(f"Topic extraction failed: {e}")
            asyncio.create_task(_extract_and_store())

        else:
            # --- Non-Streaming Path (for CASUAL, IRRELEVANT) ---
            career_ctx = user_manager.get_career_context(user_id)
            response_text, sources, eadl_meta = await handle_user_message(user_id=user_id, text=augmented_text, show_references=show_references, intent=detected_intent, career_context=career_ctx)
            cleaned = InputValidator().sanitize_output(response_text)
            await update_history(user_id, "user", augmented_text)
            await update_history(user_id, "assistant", cleaned)
            
            # Extract and store topics (fire-and-forget, non-blocking)
            async def _extract_and_store():
                try:
                    from user_memory import extract_topics_from_conversation, get_user_memory
                    topics = await extract_topics_from_conversation(text, cleaned)
                    if topics:
                        get_user_memory().add_topics(user_id, topics)
                except Exception as e:
                    logger.warning(f"Topic extraction failed: {e}")
            asyncio.create_task(_extract_and_store())
            
            if detected_intent == Intent.DIAGNOSTIC and eadl:
                 await eadl.submit_case(
                     user_id, text, cleaned,
                     eadl_meta.get("domain", "general"),
                     eadl_meta.get("keywords", []),
                     eadl_meta,
                 )

            if processing_msg:
                await processing_msg.edit_text(cleaned, parse_mode=ParseMode.MARKDOWN)
            else:
                await send_smart_message(update, cleaned, reply_markup=MAIN_KEYBOARD, case_id=case_id, user_id=user_id)
            
    except Exception as e:
        log.error("handle_message.error", error=str(e), exc_info=True)
        error_text = "❌ خطایی در پردازش درخواست رخ داد. لطفاً دوباره تلاش کنید."
        if processing_msg:
            await processing_msg.edit_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles photos with caption validation and structured logging."""
    user_id = update.effective_user.id
    caption = update.message.caption or "تحلیل تصویر"
    log = logger.bind(user_id=user_id, caption=caption, update_id=update.update_id)
    log.info("handle_photo.received")

    user_manager = context.bot_data["user_manager"]
    handle_user_message = context.bot_data["handle_user_message"]
    state_manager = context.bot_data["state_manager"]
    eadl = context.bot_data.get("eadl_manager")

    if not await state_manager.async_is_verified(user_id) and not await check_membership(user_id, context):
        await send_join_request(update)
        return
    await state_manager.async_add_verified_user(user_id)

    if not await can_user_use(user_id, context):
        access = subscription_manager.check_access(user_id)
        if access["reason"] == "subscription_expired":
            msg = "⛔ اشتراک شما منقضی شده است."
        elif access["reason"] == "daily_limit_reached":
            msg = "⛔ سهمیه امروز شما به پایان رسیده است."
        else:
            msg = "⛔ دسترسی شما محدود شده است."
        await update.message.reply_text(msg, reply_markup=MAIN_KEYBOARD)
        return

    if update.message.caption:
        try:
            InputValidator().validate_query(caption)
        except ValueError as e:
            log.warning("handle_photo.invalid_caption", error=str(e))
            await update.message.reply_text(f"❌ کپشن تصویر نامعتبر است: {e}")
            return

    msg = await update.message.reply_text("🔬 در حال پردازش تصویر و جستجو...", reply_markup=MAIN_KEYBOARD)
    
    try:
        from PIL import Image
        photo = update.message.photo[-1]
        file = await photo.get_file()
        byte_stream = io.BytesIO()
        await file.download_to_memory(out=byte_stream)
        byte_stream.seek(0)
        image = Image.open(byte_stream).convert("RGB")
        
        show_references = user_manager.get_show_references(user_id)
        response_text, sources, eadl_meta = await handle_user_message(user_id=user_id, text=caption, image=image, show_references=show_references, intent=Intent.DIAGNOSTIC)

        cleaned = InputValidator().sanitize_output(response_text)
        
        case_id = str(uuid.uuid4())[:8]
        log.info("handle_photo.sending_response", case_id=case_id)
        await msg.delete()
        
        await update.message.reply_text(cleaned, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)
        if eadl:
             eadl_meta["case_type"] = "IMAGE"
             await eadl.submit_case(
                 user_id, caption, cleaned,
                 eadl_meta.get("domain", "general"),
                 eadl_meta.get("keywords", []),
                 eadl_meta,
             )
             
    except Exception as e:
        log.error("handle_photo.error", error=str(e), exc_info=True)
        await update.message.reply_text("❌ خطا در تحلیل تصویر.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles documents with caption validation and structured logging."""
    user_id = update.effective_user.id
    caption = update.message.caption or "تحلیل سند"
    log = logger.bind(user_id=user_id, caption=caption, update_id=update.update_id)
    log.info("handle_document.received")

    user_manager = context.bot_data["user_manager"]
    handle_user_message = context.bot_data["handle_user_message"]
    state_manager = context.bot_data["state_manager"]
    eadl = context.bot_data.get("eadl_manager")

    if not await state_manager.async_is_verified(user_id) and not await check_membership(user_id, context):
        await send_join_request(update)
        return
    await state_manager.async_add_verified_user(user_id)

    if not await can_user_use(user_id, context):
        access = subscription_manager.check_access(user_id)
        if access["reason"] == "subscription_expired":
            msg = "⛔ اشتراک شما منقضی شده است."
        elif access["reason"] == "daily_limit_reached":
            msg = "⛔ سهمیه امروز شما به پایان رسیده است."
        else:
            msg = "⛔ دسترسی شما محدود شده است."
        await update.message.reply_text(msg, reply_markup=MAIN_KEYBOARD)
        return

    if update.message.caption:
        try:
            InputValidator().validate_query(caption)
        except ValueError as e:
            log.warning("handle_document.invalid_caption", error=str(e))
            await update.message.reply_text(f"❌ کپشن سند نامعتبر است: {e}")
            return

    msg = await update.message.reply_text("📥 در حال مطالعه سند...", reply_markup=MAIN_KEYBOARD)
    
    file_path = None
    try:
        doc = update.message.document
        tg_file = await doc.get_file()

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.file_name or 'doc'}") as tmp_file:
            file_path = tmp_file.name
            await tg_file.download_to_drive(file_path)

        raw_text = extract_text_from_file(file_path)
        safe_text = sanitize_for_llm(raw_text, max_len=20000)

        show_references = user_manager.get_show_references(user_id)
        response_text, sources, eadl_meta = await handle_user_message(user_id=user_id, text=caption, file_content=safe_text, show_references=show_references, intent=Intent.DIAGNOSTIC)

        cleaned = InputValidator().sanitize_output(response_text)

        case_id = str(uuid.uuid4())[:8]
        log.info("handle_document.sending_response", case_id=case_id)
        await msg.delete()

        await update.message.reply_text(cleaned, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)
        if eadl:
             eadl_meta["case_type"] = "DOC"
             await eadl.submit_case(
                 user_id, caption, cleaned,
                 eadl_meta.get("domain", "general"),
                 eadl_meta.get("keywords", []),
                 eadl_meta,
             )
    except Exception as e:
        log.error("handle_document.error", error=str(e), exc_info=True)
        await update.message.reply_text("❌ خطا در پردازش سند.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button callbacks."""
    query = update.callback_query
    if not query: return
    await query.answer()
    
    user_id = query.from_user.id
    log = logger.bind(user_id=user_id, callback_data=query.data)

    if query.data == "check_join":
        log.info("handle_callback.check_join")
        if await check_membership(user_id, context):
            await query.edit_message_text("✅ عضویت شما تایید شد. خوش آمدید!")
            await start(update, context)
        else:
            await query.answer("❌ هنوز عضو کانال‌های مورد نظر نیستید.", show_alert=True)
