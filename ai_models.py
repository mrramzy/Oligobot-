# -*- coding: utf-8 -*-
"""
AI Models - Profile/helper functions and re-exports for backward compatibility.
"""
import os
import io
import base64
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
from google import genai as google_genai

from config import (
    MODEL_NAME, OPENAI_API_KEY, SPECIALIZED_PROMPTS,
    DEEPSEEK_API_KEY, EMBEDDING_MODEL, GOOGLE_API_KEY, ROUTER,
    ACTIVE_LLM_PROFILE
)
from key_manager import KeyManager


# ==========================================================
# LLM PROFILE BACKEND HELPERS
# ==========================================================
def _active_profile() -> dict:
    """Active LLM profile from .env: LLM_PROFILE."""
    return ACTIVE_LLM_PROFILE


def _profile_uses_openai_compat() -> bool:
    """Does the active profile use an OpenAI-compatible endpoint?"""
    return _active_profile().get("backend") == "openai_compat"


def _openai_compat_client():
    """Create an OpenAI client for the active profile's endpoint."""
    from openai import OpenAI
    prof = _active_profile()
    base_url = (prof.get("base_url") or "").rstrip("/")
    api_key = os.getenv(prof.get("api_key_env", "ARVAN_API_KEY"), "")
    if not base_url or not api_key:
        raise ValueError(
            f"Profile '{prof.get('label')}' requires base_url and api_key "
            f"(env: {prof.get('api_key_env')}). Set in .env."
        )
    return OpenAI(api_key=api_key, base_url=base_url)


def _image_to_data_url(image_data) -> str:
    """PIL Image → data URL (base64 PNG) for OpenAI-compatible multimodal input."""
    buffered = io.BytesIO()
    image_data.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()


def _normalize_roles_openai(messages: list) -> list:
    """
    Normalize roles for OpenAI-compatible endpoints: only user/assistant/system.
    Legacy 'bot'/'model' roles → 'assistant'.
    """
    if not (messages and isinstance(messages[0], dict)):
        return messages
    out = []
    for m in messages:
        role = m.get("role", "user")
        if role in ("bot", "model", "assistant"):
            role = "assistant"
        elif role != "system":
            role = "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


def _gemini_client(api_key: str = None):
    """Create a google.genai Client instance with the given or first available API key."""
    if not api_key:
        from config import GOOGLE_API_KEY as gk
        api_key = gk.split(',')[0].strip() if gk else ""
    return google_genai.Client(api_key=api_key)


def _gemini_generate(client, model_name: str, content, stream: bool = False, system_instruction: str = None):
    """Wrapper for google.genai client.models.generate_content with optional streaming."""
    config = {}
    if system_instruction:
        config["system_instruction"] = system_instruction
    if stream:
        return client.models.generate_content_stream(
            model=model_name,
            contents=content,
            config=config if config else None,
        )

    return client.models.generate_content(
        model=model_name,
        contents=content,
        config=config if config else None,
    )


def build_medical_dict() -> dict[str, str]:
    """Comprehensive Persian→English medical terms dictionary (OFFLINE - no API)."""
    return {
        # Range/Normal
        "رنج": "range", "نرمال": "normal", "طبیعی": "normal",
        "حد": "range", "حدود": "range", "محدودیت": "range",

        # Blood Sugar
        "قند": "glucose", "گلوکز": "glucose", "شکر": "glucose",
        "ناشتا": "fasting", "خالی": "fasting",

        # Bilirubin
        "بیلی": "bilirubin", "بیلیروبین": "bilirubin",
        "کل": "total", "مستقیم": "direct", "غیر مستقیم": "indirect",

        # Liver
        "کبد": "liver", "الت": "ALT", "اسپات": "AST", "آلت": "ALT", "اسپ": "AST",
        "آنزیم": "enzyme", "کبدی": "hepatic",

        # Kidney
        "کلیه": "kidney", "کلیه‌ها": "kidneys", "کریاتین": "creatinine",
        "کریاتینین": "creatinine", "یوریا": "urea", "بیوریا": "urea",
        "نیتروژن": "nitrogen", "یان": "BUN",

        # Blood/RBC/WBC
        "خون": "blood", "سرخ": "red", "سفید": "white", "پلاکت": "platelet",
        "هموگلوبین": "hemoglobin", "هب": "hemoglobin", "هموگلوبین": "hemoglobin",
        "رگ": "vein", "شریان": "artery",

        # Proteins
        "پروتئین": "protein", "آلبومین": "albumin", "گلوبولین": "globulin",
        "پروتیین": "protein", "توتال": "total",
        "الکتریولیت": "electrolyte",

        # Lipids
        "چربی": "lipid", "لیپید": "lipid", "کلسترول": "cholesterol",
        "تری": "triglyceride", "تریگلیسرید": "triglyceride", "کلس": "cholesterol",
        "اچ دی ال": "HDL", "ال دی ال": "LDL",

        # Ions
        "سدیم": "sodium", "پتاسیم": "potassium", "کلسیم": "calcium",
        "فسفر": "phosphorus", "منیزیم": "magnesium", "کلر": "chloride",
        "زینک": "zinc", "روی": "zinc", "مس": "copper", "آهن": "iron", "اهن": "iron",
        "سرب": "lead", "امونیوم": "ammonium", "آمونیوم": "ammonium",
        "فریتین": "ferritin", "فریتبن": "ferritin", "فرتین": "ferritin",

        # HbA1c
        "قند سه ماهه": "HbA1c", "هموگلوبین گلیکوزیله": "HbA1c", "اچ بی ای وان سی": "HbA1c",

        # Thyroid
        "تیروئید": "thyroid", "تی اس اچ": "TSH", "تی ۴": "T4", "تی ۳": "T3",

        # Immune
        "ایمنی": "immune", "آنتی بادی": "antibody", "آنتیژن": "antigen", "انتی بادی": "antibody",

        #Vitamins
        "ویتامین": "vitamin", "ویتامین دی": "vitamin D", "ویتامین سی": "vitamin C",
        "ویتامین ای": "vitamin E", "ویتامین کا": "vitamin K", "ویتامین ب": "vitamin B",
        "ویتا دی": "vitamin D", "ویتا سی": "vitamin C", "ویتا ای": "vitamin E", "ویتا کا": "vitamin K", "ویتا ب": "vitamin B",

        # Others
        "مقدار": "level", "درجه": "level", "پاسخ": "", "چطور": "", "چیه": "",
        "پیدا": "", "معمولی": "normal", "معیاری": "standard",
    }


# ==========================================================
# Backward-compatibility re-exports
# ==========================================================
from query_refinement import refine_search_query_offline, refine_search_query
from vision import analyze_image_for_rag, caption_atlas_image
from generation import generate_response, generate_response_stream
