# -*- coding: utf-8 -*-
"""
Query Refinement - Offline dictionary, spaCy NLP, and API-based query refinement.
"""
import asyncio

from config import (
    MODEL_NAME, OPENAI_API_KEY, AVAILABLE_MODELS, GOOGLE_API_KEY, ROUTER
)
from deepseek_client import DeepSeekClient
from key_manager import KeyManager
from ai_models import (
    _active_profile, _profile_uses_openai_compat, _openai_compat_client,
    _gemini_client, _gemini_generate, build_medical_dict
)

# Cache spaCy model once at module load (expensive to load per call)
_spacy_nlp = None

def _get_spacy_nlp():
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:
            pass
    return _spacy_nlp


async def refine_search_query_offline(user_text: str, history: list) -> str:
    """Offline translation (no API)."""
    medical_dict = build_medical_dict()
    text = user_text.lower().strip()

    # 1. Phrase Matching - longer phrases first
    translated_words = []
    sorted_keys = sorted(medical_dict.keys(), key=len, reverse=True)
    temp_text = text

    for key in sorted_keys:
        if key in temp_text:
            val = medical_dict[key]
            if val:
                translated_words.append(val)
                print(f"   📌 Phrase Match: '{key}' → '{val}'")
                temp_text = temp_text.replace(key, " ")

    # 2. No terms found
    if not translated_words:
        print(f"   ℹ️  No medical terms found → SKIP (conversational)")
        return "SKIP"

    # 3. Context awareness
    if history and len(history) >= 1:
        last_msg = history[-1].get('content', '').lower()

        if ("رنج" in last_msg or "range" in last_msg or "normal" in last_msg) and \
           ("رنج" not in text and "نرمال" not in text and "طبیعی" not in text):
            query = f"normal range of {' '.join(translated_words)}"
            print(f"✅ REFINED QUERY (with context): '{user_text}' → '{query}'")
            return query

    # 4. Default
    query = ' '.join(translated_words)
    print(f"✅ REFINED QUERY (offline): '{user_text}' → '{query}'")
    return query


async def refine_search_query(user_text: str, history: list) -> str:
    """
    HYBRID STRATEGY: API → spaCy NLP → Dictionary
    """
    print(f"🔄 Refining query: '{user_text}'")

    # ========================================
    # 1. TRY API FIRST
    # ========================================
    try:
        history_str = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in history[-2:] if msg
        ])

        prompt = f"""Given chat history and Persian query, extract and translate ONLY the core medical concepts into English search terms.

CHAT HISTORY:
{history_str}

QUERY: "{user_text}"

Rules:
1. Context aware (e.g., previous "range of bilirubin" + now "protein?" = "normal reference range of Total Protein")
2. Greeting/off-topic → return SKIP
3. If the query covers multiple distinct topics, return them separated by '||'.
   Example: "HbA1c normal range || HbA1c interferences"
4. CRITICAL: DO NOT include any Persian words (like "رو بهم بگو" or "چیست"). Output ONLY English medical terms or SKIP."""

        active_model = ROUTER["keyword"]
        if active_model == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=50
                )
            )
            api_result = response.choices[0].message.content.strip()
            print(f"✅ [OpenAI API SUCCESS]: '{user_text}' → '{api_result}'")
            return api_result
        elif active_model == "deepseek":
            deepseek_client = DeepSeekClient()
            response_text = await deepseek_client.chat_completion([
                {"role": "user", "content": prompt}
            ])
            api_result = response_text.strip()
            print(f"✅ [DeepSeek API SUCCESS]: '{user_text}' → '{api_result}'")
            return api_result
        elif active_model == "gemini" and _profile_uses_openai_compat():
            prof = _active_profile()
            client = _openai_compat_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=prof["light_model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=50,
                )
            )
            api_result = response.choices[0].message.content.strip()
            print(f"✅ [Arvan {prof['light_model']} SUCCESS]: '{user_text}' → '{api_result}'")
            return api_result
        else:  # gemini (free - official Google SDK)
            light_model = AVAILABLE_MODELS["gemini"]["light_model"]
            client = _gemini_client()

            try:
                response = await asyncio.to_thread(_gemini_generate, client, light_model, prompt)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "resource" in str(e).lower():
                    print(f"⚠️ Quota exceeded in Refine Query. Rotating key...")
                    KeyManager.get_instance().rotate()
                    client = _gemini_client()
                    response = await asyncio.to_thread(_gemini_generate, client, light_model, prompt)
                else:
                    raise e

            api_result = response.text.strip()
            print(f"✅ [Gemini Flash-Lite SUCCESS]: '{user_text}' → '{api_result}'")
            return api_result

    except Exception as e:
        print(f"⚠️  [API FAILED] {type(e).__name__}, falling back to spaCy NLP...")

    # ========================================
    # 2. TRY SPACY NLP
    # ========================================
    try:
        nlp = _get_spacy_nlp()
        if nlp is None:
            raise ImportError("spaCy model not available")

        doc = nlp(user_text.lower())
        medical_dict = build_medical_dict()

        keywords = []
        print(f"   🔬 spaCy Tokenization:")

        for token in doc:
            if token.pos_ in ['NOUN', 'ADJ', 'X']:
                word = token.text.strip()

                if word in medical_dict and medical_dict[word]:
                    eng = medical_dict[word]
                    keywords.append(eng)
                    print(f"      📌 '{word}' (POS={token.pos_}) → '{eng}'")

        if keywords:
            if history and len(history) >= 1:
                last_msg = history[-1].get('content', '').lower()
                if ("رنج" in last_msg or "normal" in last_msg) and \
                   ("رنج" not in user_text.lower() and "نرمال" not in user_text.lower()):
                    query = f"normal range of {' '.join(keywords)}"
                    print(f"✅ [spaCy + Context]: '{user_text}' → '{query}'")
                    return query

            query = ' '.join(keywords)
            print(f"✅ [spaCy SUCCESS]: '{user_text}' → '{query}'")
            return query

    except ImportError:
        print(f"⚠️  spaCy not installed, skipping...")
    except Exception as e:
        print(f"⚠️  spaCy error: {e}, trying fallback...")

    # ========================================
    # 3. TRY OFFLINE DICTIONARY
    # ========================================
    print(f"   📖 Dictionary Fallback:")
    offline_result = await refine_search_query_offline(user_text, history)

    if offline_result != "SKIP":
        print(f"✅ [Dictionary Fallback]: '{user_text}' → '{offline_result}'")
        return offline_result

    print(f"❌ [ALL METHODS FAILED] → SKIP")
    return "SKIP"
