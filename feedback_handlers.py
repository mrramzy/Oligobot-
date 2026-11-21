# -*- coding: utf-8 -*-
"""
EADL Dashboard Handlers.
Manages the Expert Panel for reviewing clinical cases and access requests.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_USER_IDS
from utils import escape_markdown_special_chars
import datetime

# ✅ FIX BUG-005: Do NOT instantiate a separate EADLManager here.
# The singleton instance is rag_system.eadl, injected into bot_data["eadl_manager"] by app.py.
# We access it from context.bot_data or update.effective_user context in each handler.
# A module-level fallback is kept ONLY for the show_expert_dashboard initial auth check.
from eadl_manager import EADLManager as _EADLManagerClass

def _get_eadl(context=None):
    """Get the shared EADL instance from bot_data, falling back to a local one if unavailable."""
    if context and context.bot_data.get("eadl_manager"):
        return context.bot_data["eadl_manager"]
    # Fallback (should only happen during early startup or tests)
    return _EADLManagerClass()

async def show_expert_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the list of pending cases to authorized experts or access request for others."""
    user_id = update.effective_user.id
    eadl = _get_eadl(context)
    
    # 1. Check Authorization
    if not eadl.is_authorized(user_id):
        # Show Request Access Button
        keyboard = [[InlineKeyboardButton("📝 درخواست عضویت در پنل EADL", callback_data="eadl:req_access")]]
        text = "⛔ **دسترسی محدود**\n\nاین پنل (EADL) مخصوص متخصصین تایید شده جهت بازبینی کیس‌های پزشکی است.\nاگر متخصص علوم آزمایشگاهی یا پزشک هستید، می‌توانید درخواست دهید."
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    pending_cases = await eadl.get_pending_cases()
    
    text = f"👨‍⚕️ **پنل EADL (سیستم تشخیص تجربی)**\n\n📊 تعداد کیس‌های در انتظار: {len(pending_cases)}\n\nلطفاً برای بررسی انتخاب کنید:"
    if not pending_cases:
        text = "✅ هیچ کیس جدیدی برای بررسی وجود ندارد. همه چیز عالیست! 🎉"

    keyboard = []
    if pending_cases:
        for case in pending_cases[:10]: # Show max 10 newest
            # Format: [Hematology] Anemia... (10:30)
            time_str = datetime.datetime.fromtimestamp(case['timestamp']).strftime('%H:%M')
            btn_text = f"[{case['domain'][:4]}] {case['query'][:20]}... ({time_str})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"eadl:view:{case['id']}")])
    
    # Admin Only: Manage Requests
    if eadl.is_admin(user_id) or user_id in ADMIN_USER_IDS:
        keyboard.append([InlineKeyboardButton("👥 مدیریت درخواست‌های عضویت", callback_data="eadl:admin_reqs")])

    keyboard.append([InlineKeyboardButton("🔄 بروزرسانی لیست", callback_data="eadl:refresh")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def handle_eadl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles interactions within the EADL dashboard."""
    query = update.callback_query
    await query.answer()
    eadl = _get_eadl(context)  # ✅ FIX BUG-005: Use shared instance from bot_data
    
    data = query.data
    if not data.startswith("eadl:"):
        return

    parts = data.split(":")
    action = parts[1]

    if action == "refresh":
        await show_expert_dashboard(update, context)
        return

    # --- ACCESS REQUEST FLOW ---
    if action == "req_access":
        user = update.effective_user
        user_info = f"@{user.username}" if user.username else f"{user.first_name} (ID: {user.id})"
        
        success = await eadl.request_access(user.id, user_info)
        if success:
            await query.edit_message_text("✅ **درخواست شما ثبت شد.**\n\nتیم فنی درخواست شما را بررسی کرده و نتیجه را از طریق همین ربات به اطلاع شما می‌رساند.", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("شما قبلاً عضو هستید یا درخواست داده‌اید.", show_alert=True)
        return

    # --- ADMIN REQUEST MANAGEMENT ---
    if action == "admin_reqs":
        if not (eadl.is_admin(query.from_user.id) or query.from_user.id in ADMIN_USER_IDS):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        requests = await eadl.get_access_requests()
        if not requests:
            await query.answer("لیست درخواست‌ها خالی است.", show_alert=True)
            return

        text = "👥 **درخواست‌های عضویت در EADL**\n\nلطفاً تایید یا رد کنید:"
        keyboard = []
        for uid, info in requests.items():
            keyboard.append([
                InlineKeyboardButton(f"✅ تایید {info['user_info']}", callback_data=f"eadl:approve_user:{uid}"),
                InlineKeyboardButton(f"❌ رد", callback_data=f"eadl:reject_user:{uid}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="eadl:refresh")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    if action in ["approve_user", "reject_user"]:
        target_uid = int(parts[2])
        is_approve = action == "approve_user"
        
        await eadl.process_access_request(target_uid, approved=is_approve)
        
        # Send Notification to User
        user_manager = context.bot_data["user_manager"]
        msg = "🎉 **تبریک!** درخواست شما برای عضویت در پنل EADL تایید شد." if is_approve else "❌ درخواست عضویت شما در پنل EADL رد شد."
        user_manager.add_notification(target_uid, msg)
        
        await query.answer("انجام شد.")
        # Refresh list
        await handle_eadl_callback(update, context) # Re-call to refresh
        return

    if action == "view":
        case_id = parts[2]
        case = await eadl.get_case(case_id)
        
        if not case:
            await query.edit_message_text("❌ کیس یافت نشد یا منقضی شده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="eadl:refresh")]]))
            return

        # Escape special chars to prevent Markdown parsing errors
        safe_query = escape_markdown_special_chars(case['query'])
        # Truncate response and escape it (raw text preview) to avoid broken markdown tags
        safe_response = escape_markdown_special_chars(case['response'][:800])
        safe_keywords = escape_markdown_special_chars(', '.join(case['keywords']))
        safe_domain = escape_markdown_special_chars(case['domain'])

        # Show Case Details
        details = (
            f"🆔 *Case ID:* `{case['id']}`\n"
            f"📂 *Domain:* {safe_domain}\n"
            f"🔑 *Keywords:* {safe_keywords}\n\n"
            f"👤 *User Query:*\n{safe_query}\n\n"
            f"🤖 *Bot Response:*\n{safe_response}...\n\n"
            f"📊 *System Confidence:* {int(case['meta'].get('confidence_score', 0)*100)}%"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید (Approve)", callback_data=f"eadl:act:{case_id}:APPROVE"),
                InlineKeyboardButton("❌ رد (Reject)", callback_data=f"eadl:act:{case_id}:REJECT"),
            ],
            [InlineKeyboardButton("📝 رد و اصلاح (Correct)", callback_data=f"eadl:comment:{case_id}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="eadl:refresh")]
        ]
        await query.edit_message_text(details, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    elif action == "comment":
        case_id = parts[2]
        # Set state in user_data so handle_message knows the next text is a comment
        context.user_data["eadl_comment_case_id"] = case_id
        context.user_data["eadl_comment_msg_id"] = query.message.message_id # Save msg_id to close it later
        
        await query.edit_message_text(f"📝 **ثبت اصلاحیه برای کیس {case_id}**\n\nلطفاً تشخیص صحیح یا نکته آموزشی خود را تایپ کنید:", parse_mode=ParseMode.MARKDOWN)

    elif action == "act":
        case_id = parts[2]
        verdict = parts[3]
        user_id = query.from_user.id
        
        # ✅ FIX ARCH-003: Verify that the user is authorized to resolve cases
        if not (eadl.is_admin(user_id) or user_id in ADMIN_USER_IDS):
            await query.answer("⛔ دسترسی غیرمجاز - فقط ادمین‌ها می‌توانند کیس را بررسی کنند.", show_alert=True)
            return
        
        await eadl.resolve_case(case_id, user_id, verdict)
        
        msg = "✅ کیس تایید شد و در حافظه سیستم ثبت گردید." if verdict == "APPROVE" else "❌ کیس رد شد. سیستم از این خطا یاد خواهد گرفت."
        
        # Go back to list
        await query.answer(msg, show_alert=True)
        await show_expert_dashboard(update, context)