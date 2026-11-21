# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

import pandas as pd
import pytz
from docx import Document as DocxDocument
import fitz  # PyMuPDF


def extract_text_from_file(file_path: str) -> str | None:
    ext = os.path.splitext(file_path)[1].lower()
    text_content = ""

    try:
        if ext == ".pdf":
            with fitz.open(file_path) as doc:
                for page in doc:
                    text_content += page.get_text() + "\n"

        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
            text_content = df.to_markdown(index=False)

        elif ext == ".docx":
            doc = DocxDocument(file_path)
            text_content = "\n".join(p.text for p in doc.paragraphs if p.text)

        elif ext == ".csv":
            df = pd.read_csv(file_path)
            text_content = df.to_markdown(index=False)

        elif ext == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="cp1256") as f:
                    text_content = f.read()
        else:
            return None

        return text_content.strip() if text_content else None

    except Exception as e:
        print(f"⚠️ File read error ({file_path}): {e}")
        return None

def sanitize_for_llm(text: str, max_len: int = 20000) -> str:
    """Clean text to prevent prompt injection attacks"""
    if not text:
        return ""
    # ✅ FIX BUG-010: Remove actual null bytes (\x00), not the escaped string literal
    text = text.replace("\x00", "")
    # Limit length
    return text[:max_len]

def escape_markdown_special_chars(text: str) -> str:
    """
    Escape markdown special characters for safe Telegram display.
    Keep intentional markdown formatting intact.
    """
    if not text:
        return ""
    
    markdown_escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in markdown_escape_chars:
        text = text.replace(char, '\\' + char)
    
    return text


def get_time_metadata(now: Optional[datetime] = None, tz_name: str = 'Asia/Tehran') -> dict[str, Union[int, str, bool]]:
    if now is None:
        try:
            # ✅ FIX: Always start from UTC to prevent server local time offsets
            utc_now = datetime.now(timezone.utc)
            tz = pytz.timezone(tz_name)
            now = utc_now.astimezone(tz)
            print(f"🕒 Time Calc: UTC={utc_now.strftime('%H:%M')} -> Tehran={now.strftime('%H:%M')}")
        except Exception:
            # Fallback: Manual UTC+3:30 (Iran Standard Time)
            utc_now = datetime.now(timezone.utc)
            tehran_offset = timezone(timedelta(hours=3, minutes=30))
            now = utc_now.astimezone(tehran_offset)

    return {
        "hour": now.hour,
        "time_24": now.strftime('%H:%M'),
        "date": now.strftime('%Y-%m-%d'),
        "weekday": now.strftime('%A'),
        "is_night_shift": 1 <= now.hour < 6
    }

def get_time_prompt_hint(time_meta: dict[str, Union[int, str, bool]], force_now: bool = False) -> str:
    hour = time_meta["hour"]
    prefix = "الان" if force_now else ("امروز" if 6 <= hour < 18 else "امشب")

    if time_meta["is_night_shift"]:
        mode_note = "Night Shift Mode: Be concise, supportive, troubleshooting-oriented."
    else:
        mode_note = "Standard Mode: Be educational, structured, and explanatory."

    return f"{prefix} (ساعت {time_meta['time_24']})\n({mode_note})"


def detect_name_from_text(text: str) -> Optional[str]:
    # ✅ FIX BUG-009: Use correct single-backslash regex escape sequences
    patterns = [r"منو\s+(.+?)\s+صدا کن", r"اسمم\s+(.+?)\s+است", r"من\s+(.+?)\s+هستم"]
    
    for pattern in patterns:
        match = re.search(pattern, text.strip())
        if match and 2 <= len(match.group(1).strip()) <= 50:
            return match.group(1).strip()
    
    return None

def smart_log(user_id: int, intent: str, mode: str, time_meta: dict, has_image: bool, strategy: dict = None):
    log_entry = {
        "user_id": user_id, "intent": intent, "mode": mode,
        "hour": time_meta.get("hour"), "weekday": time_meta.get("weekday"),
        "has_image": has_image, "tone": (strategy or {}).get("tone"),
        "log_time_utc": datetime.now(timezone.utc).isoformat()
    }
    print(f"🧠 SMART LOG: {log_entry}")

# --- FUNCTION ADDED TO RESTORE AND ENHANCE ---
def detect_language(text: str) -> str:
    """
    Detects if the text is predominantly Persian or another language (defaults to English).
    This is a zero-cost, offline, and instantaneous function.
    """
    if not text or not isinstance(text, str):
        return 'en'
    # Check for any character in the Persian Unicode range
    if re.search(r'[\u0600-\u06FF]', text):
        return 'fa'
    return 'en'


# Tie-break priority: when two domains score equally, the more distinctive/narrow
# domain wins. Pathology is broadest (generic cancer terms), so it ranks lowest.
_DOMAIN_PRIORITY = ['parasitology', 'urinalysis', 'cytopathology', 'hematology', 'pathology']

# Domain keyword maps. Each return value MUST correspond to a real PSL/<domain>.md file.
# Keywords are curated to be distinctive — bare generic biochem terms (glucose, protein,
# قند ...) are intentionally excluded so that biochemistry questions fall back to the
# generic 'diagnostic_protocol' instead of being misrouted (e.g. blood glucose → urinalysis).
_DOMAIN_KEYWORDS = {
    'hematology': [
        'خون', 'blood', 'cbc', 'هموگلوبین', 'hemoglobin', 'hgb', 'hct', 'hematocrit', 'هماتوکریت',
        'گلبول قرمز', 'گلبول سفید', 'rbc', 'wbc', 'پلاکت', 'platelet', 'plt',
        'mcv', 'mch', 'mchc', 'rdw', 'لنفوسیت', 'lymphocyte', 'نوتروفیل', 'neutrophil',
        'مونوسیت', 'monocyte', 'ائوزینوفیل', 'eosinophil', 'بازوفیل', 'basophil',
        'بلاست', 'blast', 'آنمی', 'anemia', 'کم خونی', 'لوسمی', 'لوکمی', 'leukemia',
        'تالاسمی', 'thalassemia', 'فریتین', 'ferritin', 'رتیکولوسیت', 'reticulocyte',
        'اسمیر خون', 'blood smear', 'لام خون', 'انعقاد', 'coagulation', 'pt', 'ptt', 'inr',
        'فقر آهن', 'iron deficiency',
    ],
    'cytopathology': [
        'سیتولوژی', 'سایتولوژی', 'cytology', 'cytopathology', 'پاپ اسمیر', 'pap smear', 'pap',
        'بتزدا', 'bethesda', 'fna', 'آسپیراسیون', 'aspiration', 'هسته سلول',
        'nuclear', 'cytoplasm', 'سیتوپلاسم', 'سایتوپلاسم', 'پلیومورفیسم', 'pleomorphism',
        'آتیپی', 'atypia',
    ],
    'pathology': [
        'بافت شناسی', 'بافت‌شناسی', 'histology', 'histopathology', 'بیوپسی', 'biopsy',
        'نکروز', 'necrosis', 'فیبروز', 'fibrosis', 'کارسینوما', 'carcinoma',
        'آدنوکارسینوما', 'adenocarcinoma', 'آدنوما', 'adenoma', 'سرطان', 'cancer',
        'تومور', 'tumor', 'متاستاز', 'metastasis', 'ihc', 'ایمونوهیستوشیمی',
        'immunohistochemistry', 'h&e', 'هماتوکسیلین', 'تهاجمی', 'invasive',
    ],
    'parasitology': [
        'انگل', 'parasite', 'تروفوزوئیت', 'trophozoite', 'کیست انگل', 'cyst',
        'ژیاردیا', 'giardia', 'آمیب', 'amoeba', 'entamoeba', 'انتامبا',
        'پلاسمودیوم', 'plasmodium', 'مالاریا', 'malaria', 'لیشمانیا', 'leishmania',
        'تخم انگل', 'o&p', 'انگل شناسی', 'انگل‌شناسی', 'مدفوع', 'stool', 'لارو', 'larva',
        'اواسیست', 'oocyst', 'هلمینت', 'helminth',
    ],
    'urinalysis': [
        'ادرار', 'urine', 'urinalysis', 'یورینالیز', 'u/a', 'رسوب ادرار', 'sediment',
        'کست ادراری', 'cast', 'سیلندر', 'استوانه', 'کریستال', 'crystal',
        'پروتئینوری', 'proteinuria', 'گلوکزوری', 'glucosuria', 'هماچوری', 'hematuria',
        'پیوری', 'pyuria', 'leukocyte esterase', 'nitrite', 'نیتریت',
        'specific gravity', 'وزن مخصوص', 'نوار ادرار', 'dipstick',
    ],
}


def _keyword_matches(keyword: str, text: str) -> bool:
    """
    Matches a keyword against text.
    - Short ASCII tokens (e.g. 'pt', 'wbc', 'u/a') use word-boundary matching so they
      don't false-trigger as substrings of larger words (e.g. 'pt' inside 'aptt').
    - Persian / mixed keywords use plain substring matching (Persian word boundaries are
      unreliable without an NLP tokenizer).
    """
    if re.fullmatch(r'[a-z0-9][a-z0-9/&.\-]*', keyword):
        return re.search(r'(?<![a-z0-9])' + re.escape(keyword) + r'(?![a-z0-9])', text) is not None
    return keyword in text


def detect_clinical_domain(text: str) -> str:
    """
    Detects the clinical laboratory domain of a query via curated keyword matching.
    The return value maps directly to a PSL prompt file:
      - hematology     → PSL/hematology.md      (CBC, blood smear, anemia, leukemia ...)
      - cytopathology  → PSL/cytopathology.md   (Pap smear, FNA, Bethesda ...)
      - pathology      → PSL/pathology.md        (biopsy, histology, carcinoma, IHC ...)
      - parasitology   → PSL/parasitology.md     (parasites, cysts, malaria, stool O&P ...)
      - urinalysis     → PSL/urinalysis.md       (urine sediment, casts, crystals ...)
      - diagnostic_protocol → default fallback (biochemistry & general clinical cases)

    Offline, zero-cost. On ties the more distinctive domain wins (see _DOMAIN_PRIORITY).
    """
    if not text or not isinstance(text, str):
        return 'diagnostic_protocol'

    text_lower = text.lower()

    domain_scores = {
        domain: sum(1 for kw in keywords if _keyword_matches(kw, text_lower))
        for domain, keywords in _DOMAIN_KEYWORDS.items()
    }

    best_score = max(domain_scores.values())
    if best_score == 0:
        return 'diagnostic_protocol'

    # Resolve ties deterministically using the priority order.
    for domain in _DOMAIN_PRIORITY:
        if domain_scores[domain] == best_score:
            return domain

    return 'diagnostic_protocol'


# ==========================================================
# ✨ STREAMING UX HELPER
# ==========================================================
def safe_markdown_partial(text: str) -> str:
    """
    یک قطعه‌ی نیمه‌کاره‌ی استریم را به متنی تبدیل می‌کند که Telegram Markdown آن را رد نکند.

    حین استریم، نشانه‌گذاری‌ها (مثل **bold یا `code) اغلب باز می‌مانند و تلگرام
    کل ادیت را با BadRequest رد می‌کند → کاربر چند ثانیه هیچ آپدیتی نمی‌بیند (پرش).
    این تابع نشانه‌گذاری‌های بازِ ساده را موقتاً می‌بندد تا استریم روان بماند.
    فرمتِ نهایی همان متنِ کاملِ معتبر است؛ این فقط برای فریم‌های میانی است.
    """
    if not text:
        return text

    # اگر تعداد بک‌تیک فرد است، یک بک‌تیک موقت اضافه کن (code span باز)
    if text.count("`") % 2 == 1:
        text += "`"

    # ستاره‌ها: تلگرام legacy Markdown از * برای bold استفاده می‌کند.
    # اگر تعداد * فرد بماند، رد می‌شود → یک * موقت اضافه کن.
    if text.count("*") % 2 == 1:
        text += "*"

    # آندرلاین _ (italic در legacy markdown)
    if text.count("_") % 2 == 1:
        text += "_"

    return text


def md_to_html(text: str) -> str:
    """
    Converts LLM markdown-style output to Telegram-safe HTML.
    Handles: *bold*, _italic_, `code`, ```code blocks```, and escapes < > &.
    This replaces ParseMode.MARKDOWN with ParseMode.HTML for better RTL/Farsi support.
    """
    if not text:
        return text

    # Escape HTML special chars FIRST (but preserve existing tags if any)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Convert ```code blocks``` to <pre><code>...</code></pre>
    text = re.sub(r'```(\w*)\n(.*?)```', r'<pre>\2</pre>', text, flags=re.DOTALL)
    text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)

    # Convert `inline code` to <code>...</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Convert **bold** or *bold* to <b>...</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<b>\1</b>', text)

    # Convert _italic_ to <i>...</i>
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)

    return text
