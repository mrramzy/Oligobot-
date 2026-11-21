# -*- coding: utf-8 -*-
"""
Prompt Builder Module
Extracted from rag_engine.py - handles prompt selection and system prompt assembly.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# VIP SOURCES (Authority Boost List)
def _load_vip_config():
    try:
        from config import BOOK_ALIASES_PATH
        alias_path = BOOK_ALIASES_PATH
        with open(alias_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            aliases = data.get("aliases", {})
            
            vips = []
            guidelines = ["guideline", "clsi", "protocol", "standard", "treatment", "algorithm"]
            
            for key, val in aliases.items():
                if val.get("type") == "book":
                    vips.append(key)
                    en_name = val.get("display", {}).get("en", "").lower()
                    vips.append(en_name)
                    # Add parts for better matching (e.g. "bailey" from "Bailey & Scott")
                    vips.extend([p for p in en_name.replace("&", "").replace("'", "").split() if len(p) > 3])
                
                elif val.get("type") == "guideline":
                    guidelines.append(key)
                    guidelines.append(val.get("display", {}).get("en", "").lower())
            
            return list(set(vips)), list(set(guidelines))
            
    except Exception as e:
        logger.error(f"⚠️ Could not load book_aliases.json: {e}. Using fallback defaults.")
        return (
            ["henry", "rodak", "hoffbrand", "tietz", "bailey", "scott", "koneman", "harper", "abbas", "harrison", "murray"],
            ["who", "cdc", "moh", "ministry", "guideline", "clsi", "protocol", "standard"]
        )

VIP_SOURCES, GUIDELINE_SOURCES = _load_vip_config()


def build_system_prompt(intent: str, prompt_cache, career_context: str = "", mode: str = "text", domain: str = "", load_specialized_prompt=None) -> list:
    """
    Build system prompt messages based on intent, mode, and domain.
    
    Args:
        intent: One of "DIAGNOSTIC", "EDUCATIONAL", "CASUAL"
        prompt_cache: PromptCache instance for retrieving cached prompts
        career_context: Optional career context string (reserved for future use)
        mode: Query mode - "text", "image", or "document"
        domain: Detected clinical domain (e.g., "hematology", "cytopathology")
        load_specialized_prompt: Callable that loads a specialized prompt for a domain
    
    Returns:
        List of system message dicts to append to llm_chat_history
    """
    messages = []
    
    active_prompts = []
    
    # 1. System Core & Identity (Always Required)
    active_prompts.append(prompt_cache.get("system_core"))
    
    # 2. Security Shield (Always Required)
    active_prompts.append(prompt_cache.get("prompt_injection_shield"))
    
    # 3. Intent-Specific Logic
    if intent in ["DIAGNOSTIC", "EDUCATIONAL"]:
        if intent == "DIAGNOSTIC":
            logger.info("🏥 Diagnostic Intent: Activating Diagnostic Protocol.")
            active_prompts.append(prompt_cache.get("diagnostic_protocol"))
        
        # 4. Human Interaction & Formatting Rules
        active_prompts.append(prompt_cache.get("human_interaction"))
        
        # 5. Career Context (if enabled)
        if career_context:
            active_prompts.append(career_context)
        # ---------------------------------------------
        
        combined_prompt = "\n\n---\n\n".join(filter(None, active_prompts))
        messages.append({"role": "system", "content": combined_prompt})
        
        # 🔬 SPECIALIZED DOMAIN PROTOCOL INJECTION
        # Inject the domain-specific protocol (hematology, cytopathology, pathology,
        # parasitology, urinalysis) when:
        #   - mode is image (visual analysis needs the specialized atlas protocol), OR
        #   - intent is DIAGNOSTIC (clinical text cases need the specialized protocol too).
        # Skip when the detected domain falls back to 'diagnostic_protocol', because that
        # core prompt is already injected above for DIAGNOSTIC — avoids double injection.
        should_load_specialized = (mode == "image") or (intent == "DIAGNOSTIC")
        if should_load_specialized and domain and domain != "diagnostic_protocol":
            logger.info(f"🔬 Loading specialized prompt for domain: {domain} (mode={mode}, intent={intent})")
            if load_specialized_prompt:
                specialized_prompt = load_specialized_prompt(domain)
                if specialized_prompt:
                    messages.append({"role": "system", "content": specialized_prompt})
        
        # 🧬 IMAGE FUSION PROTOCOL (لایه‌ی ۳: تقاطعِ مشاهده‌ی بصری با رفرنس‌های متنی)
        # فقط برای حالت تصویر: به مدل می‌گوییم تشخیص نهایی را از تقاطع «آنچه در عکس دید»
        # با «توصیفات/رفرنس‌های بازیابی‌شده» بسازد تا توهم به حداقل برسد.
        if mode == "image":
            fusion_rule = (
                "**IMAGE FUSION PROTOCOL (ضدِ توهم):**\n"
                "1. ابتدا فقط آنچه را در تصویر می‌بینی توصیف کن (مورفولوژی، نه تشخیص).\n"
                "2. سپس آن را با 'VERIFIED REFERENCES' بالا تقاطع بده: کدام رفرنس با مشاهده‌ی تو هم‌خوان است؟\n"
                "3. تشخیص افتراقی را فقط بر پایه‌ی هم‌پوشانیِ مشاهده + رفرنس بساز. "
                "اگر مشاهده با هیچ رفرنسی هم‌خوان نبود، صراحتاً بگو «شواهد بصری با منابع موجود قطعی نیست» "
                "و تست‌های تکمیلی پیشنهاد بده — هرگز تشخیص قطعیِ بدون پشتوانه نده.\n"
                "4. در پایان درجه‌ی اطمینان (🟢/🟡/🔴) را طبق پروتکل بده."
            )
            messages.append({"role": "system", "content": fusion_rule})
    
    elif intent == "CASUAL":
        casual_rule = "Rule for Casual Talk: Directly answer the user's latest question. Do not refer to previous turns or thank them for past feedback unless they are giving feedback in the *current* message. When career mode is ON, adapt your tone and depth to the user's professional level — do NOT assume they are in a laboratory or mention lab-specific scenarios unless they bring it up first."
        
        active_prompts.append(prompt_cache.get("human_interaction"))
        active_prompts.append(casual_rule)
        if career_context:
            active_prompts.append(career_context)
        combined_prompt = "\n\n---\n\n".join(filter(None, active_prompts))
        messages.append({"role": "system", "content": combined_prompt})
    
    else:
        # Defensive fallback only — intent is normalized above, so this is unreachable
        # in normal flow. Build a minimal valid prompt and fall through to the normal
        # 3-tuple return so we never emit a malformed payload.
        logger.error(f"RAG engine received an unhandled intent: {intent}")
        active_prompts.append(prompt_cache.get("human_interaction"))
        combined_prompt = "\n\n---\n\n".join(filter(None, active_prompts))
        messages.append({"role": "system", "content": combined_prompt})
    
    return messages
