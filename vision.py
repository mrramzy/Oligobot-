# -*- coding: utf-8 -*-
"""
Vision - Medical image analysis for RAG.
Lean prompts to minimize token cost and latency.
"""
import asyncio
import json
import io
import base64

from config import (
    MODEL_NAME, OPENAI_API_KEY, SPECIALIZED_PROMPTS, AVAILABLE_MODELS, ROUTER
)
from ai_models import (
    _active_profile, _profile_uses_openai_compat, _openai_compat_client,
    _image_to_data_url, _gemini_client, _gemini_generate
)
from retry_utils import openai_retry, gemini_retry

# Compact domain prompts — keep under 150 tokens each
_DOMAIN_PROMPTS = {
    "HEMATOLOGY": (
        "Analyze this blood/bone marrow smear. IMPORTANT: ONLY report what is CLEARLY VISIBLE. "
        "Do NOT invent or hallucinate findings. Return JSON only:\n"
        '{"category":"HEMATOLOGY","keywords":"5-8 morphology terms","findings":"2-4 CLEARLY VISIBLE abnormalities","confidence":"HIGH/MEDIUM/LOW per finding"}\n'
        "CRITICAL RULES:\n"
        "- Neutrophil segmentation: 3-5 lobes = NORMAL (do NOT call hypersegmented)\n"
        "- 6+ lobes = hypersegmented (pathological)\n"
        "- If uncertain about a finding, use MAYBE not DEFINITE\n"
        "Keywords: cell type, nucleus, cytoplasm, granules, inclusions (Döhle, Auer rods, Howell-Jolly), "
        "RBC shape (sickle, target, schistocyte, spherocyte), "
        "parasites (Plasmodium ring/trophozoite/schizont, Babesia, Leishmania amastigotes), "
        "viral (atypical lymphocyte, lantern cell B19, smudge cell)."
    ),
    "URINALYSIS": (
        "Analyze this urine sediment. Return JSON only:\n"
        '{"category":"URINALYSIS","keywords":"5-8 terms","findings":"2-4 abnormalities"}\n'
        "Keywords: WBC, RBC, casts (hyaline/granular/WBC/waxy), crystals (oxalate/uric/struvite), "
        "bacteria, Trichomonas, Candida, epithelial cells, mucus."
    ),
    "PARASITOLOGY": (
        "Identify parasites in this image. Return JSON only:\n"
        '{"category":"PARASITOLOGY","keywords":"5-8 terms","findings":"2-4 observations","parasite_stage":"life stage"}\n'
        "Keywords: protozoa (trophozoite/cyst), helminth eggs (Ascaris/Trichuris/Enterobius/Schistosoma), "
        "larvae, Plasmodium stages (ring/trophozoite/schizont/gametocyte), Babesia."
    ),
    "PATHOLOGY": (
        "Analyze this tissue slide. Return JSON only:\n"
        '{"category":"PATHOLOGY","keywords":"5-8 terms","findings":"2-4 observations"}\n'
        "Keywords: architecture, cell morphology, inflammation type, staining pattern."
    ),
}

_GENERIC_PROMPT = (
    "Analyze this medical image. Return JSON only:\n"
    '{"category":"HEMATOLOGY|URINALYSIS|PARASITOLOGY|PATHOLOGY|OTHER","keywords":"5-8 morphology terms","findings":"2-4 observations"}'
)


def _build_vision_prompt(category: str = None) -> str:
    if category and category in _DOMAIN_PROMPTS:
        return _DOMAIN_PROMPTS[category]
    return _GENERIC_PROMPT


async def analyze_image_for_rag(image_data, expected_category: str = None) -> dict:
    """Analyze medical image and return category + keywords + findings."""
    try:
        prompt = _build_vision_prompt(expected_category)
        active_model = ROUTER["vision"]

        if active_model == "openai":
            @openai_retry
            async def _call_openai():
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                buffered = io.BytesIO()
                image_data.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                return await asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]}],
                        temperature=0.0, max_tokens=200
                    )
                )
            response = await _call_openai()
            text = response.choices[0].message.content.strip()

        elif active_model == "deepseek":
            return {"category": "OTHER", "keywords": "", "findings": ""}

        elif active_model == "gemini" and _profile_uses_openai_compat():
            prof = _active_profile()
            client = _openai_compat_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=prof["vision_model"],
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_data)}}
                    ]}],
                    temperature=0.0, max_tokens=200
                )
            )
            text = response.choices[0].message.content.strip()

        else:
            light_model = AVAILABLE_MODELS["gemini"]["light_model"]
            client = _gemini_client()
            response = await asyncio.to_thread(_gemini_generate, client, light_model, [prompt, image_data])
            text = response.text.strip()

        if not text:
            return {"category": "OTHER", "keywords": "", "findings": ""}

        text = text.replace("```json", "").replace("```", "").strip()
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            text = text[json_start:json_end]
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"category": "OTHER", "keywords": "", "findings": ""}

        category = data.get("category", "OTHER")
        if category not in SPECIALIZED_PROMPTS:
            category = "OTHER"

        return {
            "category": category,
            "keywords": str(data.get("keywords", "")),
            "findings": str(data.get("findings", "")),
            "parasite_stage": str(data.get("parasite_stage", "")),
            "count_estimate": str(data.get("count_estimate", "")),
        }

    except Exception as e:
        print(f"⚠️ Vision analysis failed: {type(e).__name__}: {e}")
        return {"category": "OTHER", "keywords": "", "findings": ""}


async def count_cells_from_image(image_data, cell_type: str = "auto") -> dict:
    """Count WBC/RBC/PLT from a microscope field image."""
    count_prompt = (
        "Count cells in this microscope field. Return JSON only:\n"
        '{"wbc":0,"rbc":0,"plt":0,"abnormal_cells":"...","field_description":"..."}'
    )
    try:
        active_model = ROUTER["vision"]
        if active_model == "openai":
            @openai_retry
            async def _call_openai():
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                buffered = io.BytesIO()
                image_data.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                return await asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": count_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]}],
                        temperature=0.0, max_tokens=150
                    )
                )
            response = await _call_openai()
            text = response.choices[0].message.content.strip()
        elif active_model == "deepseek":
            return {"wbc": 0, "rbc": 0, "plt": 0, "abnormal_cells": "", "field_description": "Not supported"}
        elif active_model == "gemini" and _profile_uses_openai_compat():
            prof = _active_profile()
            client = _openai_compat_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=prof["vision_model"],
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": count_prompt},
                        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_data)}}
                    ]}],
                    temperature=0.0, max_tokens=150
                )
            )
            text = response.choices[0].message.content.strip()
        else:
            light_model = AVAILABLE_MODELS["gemini"]["light_model"]
            client = _gemini_client()
            response = await asyncio.to_thread(_gemini_generate, client, light_model, [count_prompt, image_data])
            text = response.text.strip()

        text = text.replace("```json", "").replace("```", "").strip()
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            text = text[json_start:json_end]
        data = json.loads(text)
        return {
            "wbc": int(data.get("wbc", 0)),
            "rbc": int(data.get("rbc", 0)),
            "plt": int(data.get("plt", 0)),
            "abnormal_cells": str(data.get("abnormal_cells", "")),
            "field_description": str(data.get("field_description", "")),
        }
    except Exception as e:
        print(f"⚠️ Cell counting failed: {type(e).__name__}: {e}")
        return {"wbc": 0, "rbc": 0, "plt": 0, "abnormal_cells": "", "field_description": "Failed"}


async def caption_atlas_image(image_data, page_text: str = "") -> str:
    """Atlas captioner — compact prompt."""
    hint = (page_text or "").strip()[:2000]

    instruction = (
        "Write a search-optimized English caption for this atlas figure. "
        "Use the provided text as ground truth. Describe: cell type, size, shape, nucleus, "
        "cytoplasm, granules, inclusions, staining, clinical associations. "
        "Output ONLY the paragraph.\n\n"
        f"--- ATLAS TEXT ---\n{hint}\n--- END ---"
    )

    try:
        active_model = ROUTER["vision"]
        if active_model == "gemini" and _profile_uses_openai_compat():
            prof = _active_profile()
            client = _openai_compat_client()
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=prof["vision_model"],
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_data)}}
                    ]}],
                    temperature=0.1, max_tokens=300
                )
            )
            text = response.choices[0].message.content.strip()
        elif active_model == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_data)}}
                    ]}],
                    temperature=0.1, max_tokens=300
                )
            )
            text = response.choices[0].message.content.strip()
        else:
            light_model = AVAILABLE_MODELS["gemini"]["light_model"]
            client = _gemini_client()
            response = await asyncio.to_thread(_gemini_generate, client, light_model, [instruction, image_data])
            text = response.text.strip()

        return text.replace("```", "").strip()
    except Exception as e:
        print(f"⚠️ Atlas captioning failed: {type(e).__name__}: {e}")
        return ""
