# -*- coding: utf-8 -*-
"""
Module: Citation & Content Manager (v1.0)

Handles plagiarism checks during ingestion and provides standardized, 
bilingual citation formatting for the final RAG response, respecting user preferences.
"""

import re
import json
import sys
from typing import List, Dict, Any, Literal

# Fix encoding for Windows console
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class CitationManager:
    """A manager for content integrity and citation formatting."""

    # نرمال‌سازیِ ارجاعِ دیداری به فارسی (شبکهٔ ایمنی اگر LLM انگلیسی نوشت).
    # فقط وقتی یک شناسه (عدد/رومی) بلافاصله بعدش بیاید جایگزین می‌شود تا متنِ عادی دست‌نخورده بماند.
    _VISUAL_ID = r"([0-9IVXLivxl][\w.\-]*)"
    _VISUAL_NORMALIZERS = [
        (re.compile(r"\bTables?\.?\s*" + _VISUAL_ID, re.IGNORECASE), r"جدول \1"),
        (re.compile(r"\b(?:Figures?|Figs?)\.?\s*" + _VISUAL_ID, re.IGNORECASE), r"تصویر \1"),
        (re.compile(r"\b(?:Images?|Photos?|Photographs?)\.?\s*" + _VISUAL_ID, re.IGNORECASE), r"تصویر \1"),
    ]

    @classmethod
    def _normalize_visual_terms(cls, text: str) -> str:
        for pattern, repl in cls._VISUAL_NORMALIZERS:
            text = pattern.sub(repl, text)
        return text

    def __init__(self, alias_path=None):
        """Loads the book alias mapping upon initialization."""
        if alias_path is None:
            from config import BOOK_ALIASES_PATH
            alias_path = BOOK_ALIASES_PATH
        # Default safe format for citations (if file is missing/corrupted)
        self._default_format = {
            "with_page": "({name}، صفحه {page})",
            "with_page_table": "({name}، صفحه {page}، {table})",
            "without_page": "({name})",
            "rule_fa": "همیشه فقط «اسم کوتاه فارسیِ مرجع» را به‌کار ببر؛ هرگز عنوان کامل انگلیسی کتاب را ننویس.",
            "rule_table_fa": "اگر و فقط اگر پاسخ خود را بر داده‌ی یک جدول/شکل/تصویر بنا کردی و آن رفرنس فیلد «Visual» دارد، شماره‌اش را داخل پرانتز بیاور و حتماً فارسی بنویس: «Table» → «جدول»، و «Figure/Image» → «تصویر». هرگز کلمات انگلیسیِ table/figure/image را در متن ننویس. در غیر این صورت ذکرش نکن.",
            "example_fa": "(هنری، صفحه 91)",
            "example_table_fa": "(هافبراند، صفحه 176، جدول 11.3)",
        }
        try:
            with open(alias_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.aliases = data["aliases"]
            # 🎯 منبع واحد حقیقت برای فرمت رفرنس‌دهی (از همان book_aliases.json)
            self.citation_format = {**self._default_format, **data.get("citation_format", {})}
            print("[OK] CitationManager initialized: Book aliases loaded successfully.")
        except FileNotFoundError:
            print(f"[ERROR] Alias file not found at '{alias_path}'. Citations will be basic.")
            self.aliases = {}
            self.citation_format = dict(self._default_format)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[ERROR] Error parsing alias file '{alias_path}': {e}. Citations will be basic.")
            self.aliases = {}
            self.citation_format = dict(self._default_format)

    def get_citation_instruction(self, lang: Literal['fa', 'en'] = 'fa') -> str:
        """
        دستورِ رفرنس‌دهی را از روی citation_format در book_aliases.json می‌سازد.
        منبع واحد حقیقت: برای تغییر شکل ارجاع، فقط book_aliases.json را عوض کن.
        """
        fmt = self.citation_format
        return (
            "**CRITICAL CITATION RULE:**\n"
            "1. **PRIORITY:** Ground your answer in the 'Verified References' provided below.\n"
            f"2. **CITATION FORMAT:** Cite exactly as `{fmt['with_page']}` "
            f"(example: {fmt['example_fa']}). If the page is missing, use `{fmt['without_page']}`.\n"
            f"3. {fmt['rule_fa']}\n"
            f"4. **TABLE/FIGURE:** When you rely on a table or figure, cite as "
            f"`{fmt['with_page_table']}` (example: {fmt['example_table_fa']}), "
            f"where {{table}} is the exact value of that reference's `Visual:` field. "
            f"{fmt['rule_table_fa']}"
        )

    def get_display_name(self, source_key: str, lang: Literal['fa', 'en'] = 'fa') -> str:
        """Gets the display name for a source key from aliases."""
        source_key = str(source_key).lower()
        
        # 1. Exact Match
        if source_key in self.aliases:
            alias_info = self.aliases[source_key]
            return alias_info["display"].get(lang, alias_info["display"].get('fa', source_key.capitalize()))
            
        # 2. Fuzzy Match (Check if alias key or full title is inside the source string)
        for key, info in self.aliases.items():
            # Check if key (e.g. "henry") is in source (e.g. "henry_24th_ed.pdf")
            # Also check full title if available
            if key in source_key or (info.get("full_title") and info["full_title"].lower() in source_key):
                return info["display"].get(lang, info["display"].get('fa', key.capitalize()))

        return source_key.capitalize()

    def is_plagiarism_risk(self, text: str) -> bool:
        """
        Performs a basic, fast check to flag text that resembles direct copying.
        This is a heuristic filter, not a replacement for professional tools.
        """
        # 1. Ignore very short texts
        if len(text.split()) < 10:
            return False

        # 2. Check for common bookish phrases that indicate direct quotes
        bookish_phrases = [r"طبق تعریف", r"همانطور که در کتاب", r"در ویرایش جدید", r"this book describes"]
        for pattern in bookish_phrases:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # 3. A low unique word ratio can be a sign of poor paraphrasing
        words = re.findall(r'\w+', text.lower())
        if not words:
            return False
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.55:
            return True

        return False

    def format_answer_with_citations(
        self, 
        retrieved_docs: List[Dict[str, Any]], 
        llm_response: str,
        show_references: bool = True, # Respects user's choice from the panel
        lang: Literal['fa', 'en'] = 'fa'
    ) -> str:
        """
        Pass-through function. The LLM is now responsible for generating citations
        based on the context provided in the prompt. This function is kept for
        architectural consistency.
        """
        if not show_references:
            return llm_response

        # 🛡️ SAFETY NET: Post-process to replace long English titles with Persian aliases
        # This catches cases where LLM ignores the instruction and uses the "Original" source name.
        for key, info in self.aliases.items():
            persian_name = info["display"].get('fa')
            full_title = info.get("full_title")
            
            if persian_name and full_title:
                # Replace full title (case insensitive) with Persian alias
                pattern = re.compile(re.escape(full_title), re.IGNORECASE)
                llm_response = pattern.sub(persian_name, llm_response)

        # 🛡️ ارجاعِ دیداری را فارسی کن: Table→جدول، Figure/Image→تصویر (هیچ واژهٔ انگلیسی نماند)
        llm_response = self._normalize_visual_terms(llm_response)

        return llm_response
