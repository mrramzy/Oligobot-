# -*- coding: utf-8 -*-
# UI Handlers - extracted from handlers.py

import structlog
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from config import (
    BTN_NEW, BTN_QUOTA, BTN_PROFILE_HELP, BTN_SETTINGS, BTN_SUPPORT,
    BTN_SET_NAME, BTN_FEEDBACK, BTN_WITH_REF, BTN_WITHOUT_REF, BTN_BACK,
    REQUIRED_CHANNELS, ADMIN_USER_IDS, BTN_EXPERT_PANEL, BTN_SUBSCRIPTION,
    BTN_CAREER, BTN_CAREER_ON, BTN_CAREER_OFF, BTN_CAREER_SELECT, SUPPORT_ID
)
from user_manager import UserManager
from subscription_manager import subscription_manager
from feedback_handlers import show_expert_dashboard

logger = structlog.get_logger(__name__)

# ==================== KEYBOARDS ====================
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton(BTN_NEW)],
    [KeyboardButton(BTN_PROFILE_HELP), KeyboardButton(BTN_QUOTA)],
    [KeyboardButton(BTN_SUBSCRIPTION)],
    [KeyboardButton(BTN_SETTINGS), KeyboardButton(BTN_SUPPORT)],
    [KeyboardButton(BTN_EXPERT_PANEL)]
], resize_keyboard=True)

SETTINGS_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton(BTN_SET_NAME), KeyboardButton(BTN_CAREER)],
    [KeyboardButton(BTN_FEEDBACK)],
    [KeyboardButton(BTN_WITH_REF), KeyboardButton(BTN_WITHOUT_REF)],
    [KeyboardButton(BTN_BACK)]
], resize_keyboard=True)

# ==================== QUOTA & MEMBERSHIP ====================
async def get_quota_info(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Gets user's remaining quota for the day from the state manager."""
    if user_id in ADMIN_USER_IDS:
        return "♾️ نامحدود (مدیر)"

    access = subscription_manager.check_access(user_id)

    if access["has_override"] and access["override_type"] in ("test_mode", "free_access"):
        return f"♾️ نامحدود ({access['reason']})"

    tier_config = subscription_manager.get_tier_config(user_id)
    tier_label = tier_config["label"]
    daily_limit = tier_config["daily_queries"]

    if daily_limit == -1:
        return f"♾️ نامحدود ({tier_label})"

    state_manager = context.bot_data["state_manager"]
    used = await state_manager.async_get_usage(user_id)
    rem = max(0, daily_limit - used)
    return f"{rem} از {daily_limit} درخواست ({tier_label})"

async def can_user_use(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user has permission and quota to use the bot."""
    if user_id in ADMIN_USER_IDS:
        return True

    access = subscription_manager.check_access(user_id)
    if not access["allowed"]:
        return False

    state_manager = context.bot_data["state_manager"]
    used = await state_manager.async_get_usage(user_id)

    tier_config = subscription_manager.get_tier_config(user_id)
    daily_limit = tier_config["daily_queries"]

    if daily_limit == -1:
        return True

    return used < daily_limit

async def send_smart_message(update: Update, text: str, reply_markup=None, case_id=None, user_id=None):
    """Send message, splitting if too long."""
    MAX_LENGTH = 4096
    if len(text) > MAX_LENGTH:
        parts = []
        while text:
            if len(text) <= MAX_LENGTH:
                parts.append(text)
                break
            split_idx = text.rfind('\n', 0, MAX_LENGTH)
            if split_idx == -1: split_idx = MAX_LENGTH
            parts.append(text[:split_idx])
            text = text[split_idx:]
            
        for part in parts[:-1]:
            await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text(parts[-1], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if a user is a member of all required channels."""
    if user_id in ADMIN_USER_IDS:
        logger.info("check_membership.admin_bypass", user_id=user_id)
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                logger.warning("check_membership.not_member", user_id=user_id, channel=channel, status=member.status)
                return False
        except Exception as e:
            logger.error("check_membership.api_error", user_id=user_id, channel=channel, error=str(e))
            return False
    logger.info("check_membership.success", user_id=user_id)
    return True

async def send_join_request(update: Update):
    """Sends a message asking the user to join channels."""
    channels_str = ", ".join(REQUIRED_CHANNELS)
    join_msg = f"❌ **شما عضو کانال‌های مورد نیاز نیستید.**\n\nلطفاً ابتدا در کانال زیر عضو شوید:\n{channels_str}\n\nسپس دکمه زیر را بزنید:"
    join_button = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید عضویت", callback_data="check_join")]])
    await update.message.reply_text(join_msg, reply_markup=join_button, parse_mode=ParseMode.MARKDOWN)

# ==================== UI HANDLERS ====================
async def handle_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state_manager = context.bot_data["state_manager"]
    await state_manager.async_save_history(user_id, [])
    case_store = context.bot_data["case_store"]
    case_store.clear_case(user_id)
    await update.message.reply_text("🆕 بازنشانی", reply_markup=MAIN_KEYBOARD)

async def handle_profile_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_manager = context.bot_data["user_manager"]
    if not user_manager.exists(user_id):
        user_manager.create_user(user_id, username=update.effective_user.username, first_name=update.effective_user.first_name)
    
    text = user_manager.get_user_info_text(user_id)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quota_info = await get_quota_info(update.effective_user.id, context)
    await update.message.reply_text(f"💳 **سهمیه امروز:**\n{quota_info}", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ **تنظیمات:**", parse_mode=ParseMode.MARKDOWN, reply_markup=SETTINGS_KEYBOARD)

async def handle_set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_name"] = True
    await update.message.reply_text("✏️ **لطفاً نام دلخواه خود را وارد کنید:**", parse_mode=ParseMode.MARKDOWN, reply_markup=SETTINGS_KEYBOARD)

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "💬 **بازخورد و نظرات**\n\nراه‌های ارسال بازخورد:\n1. **تلگرام:** @Drxerou\n2. **ایمیل:** info@oligosoft.com"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=SETTINGS_KEYBOARD)

async def handle_with_references(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager = context.bot_data["user_manager"]
    user_manager.set_show_references(update.effective_user.id, True)
    await update.message.reply_text("✅ **نمایش رفرنس فعال شد.**\nپاسخ‌ها از این پس شامل نام کتاب و شماره صفحه خواهند بود.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_without_references(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager = context.bot_data["user_manager"]
    user_manager.set_show_references(update.effective_user.id, False)
    await update.message.reply_text("❌ **نمایش رفرنس غیرفعال شد.**\nپاسخ‌ها از این پس خلاصه‌تر و بدون ذکر منبع خواهند بود.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 بازگشت به منوی اصلی", reply_markup=MAIN_KEYBOARD)

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📞 **پشتیبانی الیگوسافت**\n\nراه‌های تماس:\n1. **تلگرام:** @Drxerou\n2. **کانال:** @Oligosoft"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)

# ==================== CAREER SYSTEM ====================
CAREER_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("📚 Student / دانشجو"), KeyboardButton("🔬 کارشناس آزمایشگاه")],
    [KeyboardButton("🎓 کارشناسی ارشد"), KeyboardButton("🩺 Physician / پزشک")],
    [KeyboardButton("🔎 Pathologist / پاتولوژیست"), KeyboardButton("🏥 DCLS / متخصص علوم آزمایشگاهی")],
    [KeyboardButton("🧬 PhD / دکتری"), KeyboardButton("🎓 FCLS Fellow")],
    [KeyboardButton(BTN_BACK)]
], resize_keyboard=True)

CAREER_BTN_MAP = {
    "📚 Student / دانشجو": "student",
    "🔬 کارشناس آزمایشگاه": "technician",
    "🎓 کارشناسی ارشد": "masters",
    "🩺 Physician / پزشک": "physician",
    "🔎 Pathologist / پاتولوژیست": "pathologist",
    "🏥 DCLS / متخصص علوم آزمایشگاهی": "dcls",
    "🧬 PhD / دکتری": "phd",
    "🎓 FCLS Fellow": "fcls",
}

async def handle_career(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show career menu."""
    user_id = update.effective_user.id
    user_manager = context.bot_data["user_manager"]
    current = user_manager.get_career(user_id)
    enabled = user_manager.get_career_enabled(user_id)
    career_opts = user_manager.CAREER_OPTIONS

    status = "ON" if enabled else "OFF"
    current_text = ""
    if current and current in career_opts:
        c = career_opts[current]
        current_text = f"\n\nCurrently: {c['emoji']} {c['label']} ({c['label_fa']})"

    text = (
        f"💼 **Career Mode** (Status: {status}){current_text}\n\n"
        "When ON, I adapt my responses to your professional level.\n"
        "When OFF, I talk like a general assistant — no lab assumptions.\n\n"
        "Choose your career, or toggle on/off:"
    )
    toggle_kb = ReplyKeyboardMarkup([
        [KeyboardButton(BTN_CAREER_ON), KeyboardButton(BTN_CAREER_OFF)],
        [KeyboardButton(BTN_CAREER_SELECT)],
        [KeyboardButton(BTN_BACK)]
    ], resize_keyboard=True)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=toggle_kb)

async def handle_career_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_manager = context.bot_data["user_manager"]
    if not user_manager.get_career(user_id):
        await update.message.reply_text("First select your career, then enable career mode.", reply_markup=CAREER_KEYBOARD)
        return
    user_manager.set_career_enabled(user_id, True)
    await update.message.reply_text("Career mode ON! I'll adapt to your professional level.", reply_markup=MAIN_KEYBOARD)

async def handle_career_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_manager = context.bot_data["user_manager"]
    user_manager.set_career_enabled(user_id, False)
    await update.message.reply_text("Career mode OFF. I'll respond like a general assistant.", reply_markup=MAIN_KEYBOARD)

async def handle_career_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose your career:", reply_markup=CAREER_KEYBOARD)

async def handle_career_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle career keyboard selection."""
    text = update.message.text
    user_id = update.effective_user.id
    user_manager = context.bot_data["user_manager"]
    career = CAREER_BTN_MAP.get(text)
    if career:
        user_manager.set_career(user_id, career)
        user_manager.set_career_enabled(user_id, True)
        info = user_manager.CAREER_OPTIONS[career]
        await update.message.reply_text(
            f"{info['emoji']} **{info['label']}** ({info['label_fa']}) selected and career mode activated!\n\n"
            f"I'll now adapt my responses to your professional level.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD
        )
        return True
    return False

# ==================== COMMAND HANDLERS ====================
async def handle_new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new command."""
    user_id = update.effective_user.id
    log = logger.bind(user_id=user_id, command="/new")
    log.info("new_command.triggered")
    state_manager = context.bot_data["state_manager"]
    await state_manager.async_save_history(user_id, [])
    case_store = context.bot_data["case_store"]
    case_store.clear_case(user_id)
    await update.message.reply_text("✅ گفتگو جدید شروع شد!")

async def handle_setname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setname command."""
    user_id = update.effective_user.id
    logger.info(f"setname_command", user_id=user_id)
    context.user_data["waiting_for_name"] = True
    await update.message.reply_text("لطفاً نام خود را وارد کنید:")

async def handle_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /feedback command."""
    user_id = update.effective_user.id
    logger.info(f"feedback_command", user_id=user_id)
    context.user_data["waiting_for_feedback"] = True
    await update.message.reply_text("لطفاً بازخوردتان را بنویسید:")

async def handle_subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscription command."""
    await handle_subscription(update, context)

async def handle_expert_panel_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the Expert Panel button click."""
    await show_expert_dashboard(update, context)

async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows user's subscription status."""
    user_id = update.effective_user.id
    access = subscription_manager.check_access(user_id)
    tier_config = subscription_manager.get_tier_config(user_id)
    sub = subscription_manager.get_user_subscription(user_id)
    remaining = subscription_manager.get_remaining_queries(user_id)
    
    if access["is_admin"]:
        tier_text = "♾️ نامحدود (مدیر)"
        remaining_text = "∞"
    elif access["has_override"]:
        tier_text = f"🧪 {access['override_type']}"
        remaining_text = "∞"
    else:
        tier_text = f"{tier_config['label']} ({tier_config['label_en']})"
        if tier_config["daily_queries"] == -1:
            remaining_text = "∞"
        else:
            remaining_text = f"{remaining} از {tier_config['daily_queries']}"
    
    expires_text = "ندارد"
    if sub.get("expires_at"):
        from datetime import datetime
        import pytz
        expires = datetime.fromisoformat(sub["expires_at"])
        expires_text = expires.strftime("%Y/%m/%d")
    
    price = tier_config["monthly_price"]
    price_text = f"{price:,} تومان" if price > 0 else "رایگان"
    
    text = f"""💳 **وضعیت اشتراک شما**

📦 **تی‌ر فعلی:** {tier_text}
📊 **سقف روزانه:** {remaining_text} سوال
💰 **هزینه ماهانه:** {price_text}
📅 **تاریخ انقضا:** {expires_text}

**ویژگی‌های تی‌ر {tier_config['label']}:**
{chr(10).join(f'  ✅ {f}' for f in tier_config['features'])}

💡 برای ارتقا اشتراک با پشتیبانی تماس بگیرید.
📞 @{SUPPORT_ID.replace('@', '')}"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_KEYBOARD)
