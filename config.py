# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

# ==========================================
# 🔐 CONFIGURATION
# ==========================================
load_dotenv()

# ==========================================
# 🚦 AI TASK ROUTER Configuration
# ==========================================
ROUTER = {
    "intent": os.getenv("ROUTER_INTENT", "gemini").lower(),
    "keyword": os.getenv("ROUTER_KEYWORD", "gemini").lower(),
    "vision": os.getenv("ROUTER_VISION", "gemini").lower(),
    "text_gen": os.getenv("ROUTER_TEXT_GEN", "deepseek").lower(),
}

# --- Auto Fallback System ---
if ROUTER["text_gen"] == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
    print("⚠️ WARNING: DEEPSEEK_API_KEY not found in .env. Falling back text_gen to 'gemini'.")
    ROUTER["text_gen"] = "gemini"

GEMINI_HEAVY_MODEL = os.getenv("GEMINI_HEAVY_MODEL", "gemini-3.5-flash")
GEMINI_LIGHT_MODEL = os.getenv("GEMINI_LIGHT_MODEL", "gemini-3.1-flash-lite")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# ==========================================
# 🎛️ LLM PROFILE REGISTRY (سوییچ عددی مثل رجیستری ویندوز)
# ==========================================
# با تغییر فقط عددِ LLM_PROFILE در .env بین بک‌اندهای مختلف LLM سوییچ کن.
# هر پروفایل خودکفاست: backend (نحوه‌ی صدا زدن API) + مدل متن + مدل ویژن + کلید/آدرس.
# ماژولار: برای افزودن شرکت/مدل جدید فقط یک ردیف به LLM_PROFILES اضافه کن.
#
#   backend = "gemini_sdk"  → SDK رسمی گوگل (رایگان، چرخش کلید). از GOOGLE_API_KEY می‌خواند.
#   backend = "openai_compat" → هر endpoint سازگار با OpenAI (آروان/پولی، DeepSeek و...).
#                               از base_url + api_key همان پروفایل می‌خواند.
#
# مقادیر حساس (کلید/آدرس) از .env خوانده می‌شوند تا در کد هاردکد نشوند.
LLM_PROFILE = int(os.getenv("LLM_PROFILE", "1"))

LLM_PROFILES = {
    # 1 = رایگان: SDK رسمی گوگل (وضعیت فعلی، دست‌نخورده)
    1: {
        "label": "Gemini Free (Google SDK)",
        "backend": "gemini_sdk",
        "text_model": GEMINI_HEAVY_MODEL,
        "light_model": GEMINI_LIGHT_MODEL,
        "vision_model": GEMINI_LIGHT_MODEL,
        "base_url": None,
        "api_key_env": "GOOGLE_API_KEY",
    },
    # 2 = پولی: Gemini-2.5-Flash-lite روی ابرآروان (OpenAI-compatible)
    2: {
        "label": "Gemini-2.5-Flash-lite (ArvanCloud paid)",
        "backend": "openai_compat",
        "text_model": os.getenv("ARVAN_LLM_MODEL", "Gemini-2.5-Flash-lite"),
        "light_model": os.getenv("ARVAN_LLM_MODEL", "Gemini-2.5-Flash-lite"),
        "vision_model": os.getenv("ARVAN_VISION_MODEL", "Gemini-2.5-Flash-lite"),
        "base_url": os.getenv("ARVAN_LLM_BASE_URL", ""),
        "api_key_env": "ARVAN_API_KEY",
    },
    # 3 = ارزان (آزمایشی): Gemma-4-31B روی ابرآروان — برای متن، ۵× ارزان‌تر
    3: {
        "label": "Gemma-4-31B-IT (ArvanCloud cheap)",
        "backend": "openai_compat",
        "text_model": os.getenv("ARVAN_GEMMA_MODEL", "Gemma-4-31B-IT"),
        "light_model": os.getenv("ARVAN_GEMMA_MODEL", "Gemma-4-31B-IT"),
        # ویژن جدا: Gemma ممکن است عکس نبیند؛ پیش‌فرض به مدل امن Gemini روی آروان برمی‌گردد.
        "vision_model": os.getenv("ARVAN_VISION_MODEL", "Gemini-2.5-Flash-lite"),
        "base_url": os.getenv("ARVAN_GEMMA_BASE_URL", os.getenv("ARVAN_LLM_BASE_URL", "")),
        "api_key_env": "ARVAN_API_KEY",
    },
}

# پروفایل فعال (با fallback امن به پروفایل ۱ اگر عدد نامعتبر بود)
ACTIVE_LLM_PROFILE = LLM_PROFILES.get(LLM_PROFILE, LLM_PROFILES[1])
if LLM_PROFILE not in LLM_PROFILES:
    print(f"⚠️ LLM_PROFILE={LLM_PROFILE} تعریف نشده؛ بازگشت به پروفایل ۱ (رایگان).")

# آدرس و کلید پولی آروان برای backend=openai_compat
ARVAN_LLM_BASE_URL = os.getenv("ARVAN_LLM_BASE_URL", "")
ARVAN_GEMMA_BASE_URL = os.getenv("ARVAN_GEMMA_BASE_URL", "")

# ==========================================
# 🧬 RAG EMBEDDING ENGINE (single source of truth)
# ==========================================
# هم ساخت ایندکس و هم کوئری ربات از این تنظیمات می‌خوانند تا همیشه هماهنگ بمانند.
# تعویض مدل امبدینگ در آینده = فقط تغییر همین چند خط (یا .env) + بازسازی از روی chunks.jsonl.
# گزینه‌های provider: "arvan" (پیش‌فرض، bge-m3 روی ابرآروان) | "gemini" | "openai" | "local"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "arvan").lower()

# ابعاد بردار خروجی — باید با مدل سازگار باشد (bge-m3 = 1024)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# اندازه‌ی batch برای embed دسته‌ای اسناد (سرعت ساخت ایندکس)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

# --- ArvanCloud AIaaS (OpenAI-compatible /v1/embeddings) ---
# BASE_URL شامل توکن مسیر است و تا انتهای /v1 می‌رسد (نمونه: https://arvancloudai.ir/gateway/models/Bge-m3/<token>/v1)
ARVAN_EMBEDDING_BASE_URL = os.getenv("ARVAN_EMBEDDING_BASE_URL", "")
ARVAN_API_KEY = os.getenv("ARVAN_API_KEY", "")
ARVAN_EMBEDDING_MODEL = os.getenv("ARVAN_EMBEDDING_MODEL", "bge-m3")

# ==========================================
# 🧠 EADL — Semantic Learning Layer
# ==========================================
# لایه‌ی یادگیری معنایی: اصلاحیه‌های متخصص در یک ChromaDB جدا (eadl_index) با همان
# امبدینگ bge-m3 آروان ذخیره می‌شوند و موقع هر سوال فقط مرتبط‌ترین‌ها (بالای آستانه)
# به پرامپت تزریق می‌شوند تا توکن صرف‌نظر از حجم اصلاحیه‌ها ثابت بماند.
EADL_ENABLED = os.getenv("EADL_ENABLED", "1") == "1"
EADL_INDEX_PATH = os.getenv("EADL_INDEX_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "eadl_index"))
# حداکثر تعداد اصلاحیه‌ی تزریقی به ازای هر سوال
EADL_TOP_K = int(os.getenv("EADL_TOP_K", "3"))
# حداقل شباهت معنایی (relevance score در بازه‌ی 0..1) برای واجد شرایط بودن یک اصلاحیه.
# کالیبراسیون: bge-m3 برای جفت‌های واقعاً مرتبطِ فارسی (paraphrase) cosine ~0.70–0.85 می‌دهد؛
# 0.70 تعادل خوبی است (مرتبط‌ها می‌آیند، بی‌ربط‌ها ~0.0–0.3 رد می‌شوند). با تست تأیید شد.
EADL_SIM_THRESHOLD = float(os.getenv("EADL_SIM_THRESHOLD", "0.70"))
# کیس‌های REVIEWED قدیمی‌تر از این تعداد روز از صف JSON هرس می‌شوند (دانش در eadl_index می‌ماند)
EADL_CASE_RETENTION_DAYS = int(os.getenv("EADL_CASE_RETENTION_DAYS", "30"))
# 🗳️ وزن‌دهی اجماع: اصلاحیه‌ای که حداقل این تعداد متخصصِ مستقل تأییدش کرده‌اند «معتبر» شمرده
# می‌شود و با لحن قوی تزریق می‌شود؛ کمتر از آن = «نظر مقدماتی، با احتیاط» (ایمنی پزشکی).
EADL_MIN_CONSENSUS = int(os.getenv("EADL_MIN_CONSENSUS", "2"))
# دو اصلاحیه با شباهت معناییِ بالاتر از این آستانه، «هم‌موضوع» تلقی می‌شوند و به‌جای رکورد
# تکراری، شمارنده‌ی تأیید (confirmations) همان رکورد بالا می‌رود (اجماع واقعی، نه تکرار).
EADL_CONSENSUS_MATCH_THRESHOLD = float(os.getenv("EADL_CONSENSUS_MATCH_THRESHOLD", "0.85"))

# ==========================================
# 🖼️ ATLAS — Vision-to-Text Image Indexing
# ==========================================
# تصاویر استخراج‌شده‌ی اطلس اینجا ذخیره می‌شوند؛ image_path در متادیتای ایندکس می‌رود.
ATLAS_IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base", "atlas_images")
# ماژولار: ارسالِ خودِ تصویرِ مرجعِ اطلس به کاربر هنگام پاسخ (فعلاً خاموش؛ برای فاز بعد).
ATLAS_SEND_IMAGE_TO_USER = os.getenv("ATLAS_SEND_IMAGE_TO_USER", "0") == "1"

# Supported models and their configurations
AVAILABLE_MODELS = {
    "openai": {
        "name": "gpt-4o",
        "embedding": "text-embedding-3-small",
        "provider": "OpenAI"
    },
    "gemini": {
        "name": GEMINI_HEAVY_MODEL,
        "heavy_model": GEMINI_HEAVY_MODEL,
        "light_model": GEMINI_LIGHT_MODEL,
        "embedding": GEMINI_EMBEDDING_MODEL,
        "provider": "Google Gemini"
    },
    "deepseek": {
        "name": "deepseek-chat",
        "embedding": "deepseek-embedding",
        "provider": "DeepSeek"
    }
}

# --- Validate ROUTER against AVAILABLE_MODELS ---
for task, provider in ROUTER.items():
    if provider not in AVAILABLE_MODELS:
        raise ValueError(f"Invalid provider '{provider}' for task '{task}'. Options are {list(AVAILABLE_MODELS.keys())}")

PRIMARY_PROVIDER = ROUTER["text_gen"]
MODEL_CONFIG = AVAILABLE_MODELS[PRIMARY_PROVIDER]
MODEL_NAME = MODEL_CONFIG["name"]
EMBEDDING_MODEL = AVAILABLE_MODELS["gemini"]["embedding"]
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base") # 🚀 Switched to 'base' for 5x speedup


# --- API Keys ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
_admin_list = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = [ADMIN_ID] if ADMIN_ID != 0 else []
if _admin_list:
    ADMIN_USER_IDS.extend([int(x.strip()) for x in _admin_list.split(",") if x.strip().isdigit()])
ADMIN_USER_IDS = list(set(ADMIN_USER_IDS))

# ==========================================
# 🧠 RAG & KNOWLEDGE BASE
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(BASE_DIR, "chroma_clinical_v2"))
CHROMA_VISION_PATH = os.getenv("CHROMA_VISION_PATH", os.path.join(BASE_DIR, "chroma_vision"))
FAISS_BRAIN_PATH = os.getenv("FAISS_BRAIN_PATH", os.path.join(BASE_DIR, "brain_index"))
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", os.path.join(BASE_DIR, "knowledge_base"))
ATLAS_IMAGES_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "atlases")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
PSL_PATH = os.getenv("PSL_PATH", os.path.join(BASE_DIR, "PSL"))
EADL_INDEX_PATH = os.getenv("EADL_INDEX_PATH", os.path.join(BASE_DIR, "eadl_index"))

# ==========================================
# 💾 DATA FILE PATHS
# ==========================================
ENTITY_INDEX_PATH = os.getenv("ENTITY_INDEX_PATH", os.path.join(BASE_DIR, "entity_index.json"))
USER_PROFILES_PATH = os.getenv("USER_PROFILES_PATH", os.path.join(BASE_DIR, "user_profiles.json"))
SUBSCRIPTION_DATA_PATH = os.getenv("SUBSCRIPTION_DATA_PATH", os.path.join(BASE_DIR, "subscription_data.json"))
USER_MEMORY_PATH = os.getenv("USER_MEMORY_PATH", os.path.join(BASE_DIR, "user_memory.json"))
EADL_MEMORY_PATH = os.getenv("EADL_MEMORY_PATH", os.path.join(BASE_DIR, "eadl_memory.json"))
EADL_CASES_PATH = os.getenv("EADL_CASES_PATH", os.path.join(BASE_DIR, "eadl_cases.json"))
EADL_CONFIG_PATH = os.getenv("EADL_CONFIG_PATH", os.path.join(BASE_DIR, "eadl_config.json"))
BOOK_ALIASES_PATH = os.getenv("BOOK_ALIASES_PATH", os.path.join(BASE_DIR, "book_aliases.json"))
ADMIN_DASHBOARD_HTML_PATH = os.path.join(BASE_DIR, "admin_dashboard.html")

PROMPT_SYSTEM_PATH = "PSL"

# Prompts for specialized image analysis
SPECIALIZED_PROMPTS = {
    "HEMATOLOGY": "Analyze this hematology slide for cell morphology, inclusions, and parasites.",
    "URINALYSIS": "Analyze this urine sediment for cells, casts, crystals, and parasites.",
    "PARASITOLOGY": "Identify parasites, their life stages, and morphological features in this image.",
    "PATHOLOGY": "Analyze this pathology slide for tissue architecture and cellular abnormalities.",
    "OTHER": "Analyze this medical image."
}

# =========================================
# 💾 CACHE (Redis)
# =========================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", None)
PORT = int(os.getenv("PORT", 8443))


# ==========================================
# 👤 USER & TELEGRAM SETTINGS
# ==========================================
SUPPORT_ID = "@Drxerou"
REQUIRED_CHANNELS = ["@Oligosoft"]
MAX_REQUESTS_PER_USER = 30  # Fallback limit (subscription system takes priority)
HISTORY_LIMIT = 10

# ==========================================
# 💳 SUBSCRIPTION & ADMIN DASHBOARD
# ==========================================
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "oligobot_admin_2026")
ADMIN_DASHBOARD_PORT = int(os.getenv("ADMIN_DASHBOARD_PORT", "8080"))

# ==========================================
# 🎨 TELEGRAM UI CONSTANTS
# ==========================================
BTN_NEW = "🆕 بازنشانی"
BTN_PROFILE_HELP = "📋 پروفایل"
BTN_QUOTA = "💳 اعتبار من"
BTN_SETTINGS = "⚙️ تنظیمات"
BTN_SUPPORT = "📞 پشتیبانی"
BTN_SET_NAME = "✏️ تعیین نام"
BTN_FEEDBACK = "💬 بازخورد"
BTN_WITH_REF = "✅ با رفرنس و صفحه"
BTN_WITHOUT_REF = "❌ بدون رفرنس"
BTN_BACK = "🔙 بازگشت"
BTN_EXPERT_PANEL = "👨‍⚕️ پنل EADL"
BTN_SUBSCRIPTION = "💳 اشتراک من"
BTN_CAREER = "💼 شغل من"
BTN_CAREER_ON = "✅ فعال‌سازی حالت شغلی"
BTN_CAREER_OFF = "❌ غیرفعال‌سازی حالت شغلی"
BTN_CAREER_SELECT = "📝 انتخاب شغل"
