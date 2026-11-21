# -*- coding: utf-8 -*-
"""
Generation - Response generation (sync and streaming) for multiple LLM backends.
"""
import asyncio
import io
import base64
from typing import AsyncGenerator

from PIL import Image

from config import (
    MODEL_NAME, OPENAI_API_KEY, GOOGLE_API_KEY, AVAILABLE_MODELS, ROUTER
)
from deepseek_client import DeepSeekClient
from key_manager import KeyManager
from ai_models import (
    _active_profile, _profile_uses_openai_compat, _openai_compat_client,
    _image_to_data_url, _normalize_roles_openai, _gemini_client, _gemini_generate
)


async def generate_response(user_id: int, api_payload: list, admin_id: int, model: str = None) -> str:
    """
    Safe model caller with retry and error handling.
    Supports 3 models: OpenAI, Gemini, DeepSeek
    """
    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            is_vision = isinstance(api_payload, list) and any(isinstance(part, Image.Image) for part in api_payload)

            if model and model in ["openai", "gemini", "deepseek", "gemini_sdk"]:
                active_model = model
            else:
                active_model = ROUTER["vision"] if is_vision else ROUTER["text_gen"]

            if active_model == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)

                if any(isinstance(part, Image.Image) for part in api_payload):
                    text_prompt = api_payload[0]
                    image_obj = api_payload[1]

                    buffered = io.BytesIO()
                    image_obj.save(buffered, format="PNG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode()

                    response = await asyncio.to_thread(
                        lambda: client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": text_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                                ]
                            }],
                            temperature=0.7,
                            max_tokens=2000
                        )
                    )
                else:
                    messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]
                    response = await asyncio.to_thread(
                        lambda: client.chat.completions.create(
                            model="gpt-4o",
                            messages=messages_payload,
                            temperature=0.7,
                            max_tokens=2000
                        )
                    )

                return response.choices[0].message.content

            elif active_model == "deepseek":
                if not isinstance(api_payload[0], dict) and len(api_payload) > 1:
                    print("⚠️ DeepSeek: Image input not fully supported, using text fallback...")

                messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]
                deepseek_client = DeepSeekClient()
                response_text = await deepseek_client.chat_completion(messages_payload)
                return response_text

            elif active_model == "gemini_sdk":
                target_model_name = AVAILABLE_MODELS["gemini"]["heavy_model"]
                if is_vision:
                    target_model_name = AVAILABLE_MODELS["gemini"]["light_model"]
                client = _gemini_client(GOOGLE_API_KEY)

                if isinstance(api_payload[0], dict):
                    system_parts = []
                    gemini_payload = []
                    for msg in api_payload:
                        role = msg.get("role", "user")
                        content = msg.get('content', '')
                        if role == "system":
                            system_parts.append(content)
                        else:
                            gemini_role = "model" if role in ("assistant", "bot", "model") else "user"
                            gemini_payload.append({'role': gemini_role, 'parts': [content]})
                    if system_parts:
                        system_text = "\n\n---\n\n".join(system_parts)
                        res = await asyncio.to_thread(
                            _gemini_generate, client, target_model_name, gemini_payload,
                            system_instruction=system_text
                        )
                    else:
                        res = await asyncio.to_thread(_gemini_generate, client, target_model_name, gemini_payload)
                else:
                    res = await asyncio.to_thread(_gemini_generate, client, target_model_name, api_payload)
                return res.text

            elif active_model == "gemini" and _profile_uses_openai_compat():
                prof = _active_profile()
                client = _openai_compat_client()
                target = prof["vision_model"] if is_vision else prof["text_model"]
                if model and model.lower() not in ("gemini", "openai", "deepseek"):
                    target = model

                if is_vision:
                    text_prompt = api_payload[0]
                    image_obj = next(p for p in api_payload if isinstance(p, Image.Image))
                    messages_payload = [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_prompt},
                            {"type": "image_url", "image_url": {"url": _image_to_data_url(image_obj)}},
                        ],
                    }]
                else:
                    messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]
                    messages_payload = _normalize_roles_openai(messages_payload)

                response = await asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model=target,
                        messages=messages_payload,
                        temperature=0.7,
                        max_tokens=2000,
                    )
                )
                return response.choices[0].message.content

            else:  # gemini (free - official Google SDK)
                target_model_name = AVAILABLE_MODELS["gemini"]["heavy_model"]
                if model and model.lower() != "gemini":
                    target_model_name = model
                client = _gemini_client(GOOGLE_API_KEY)

                if isinstance(api_payload[0], dict):
                    system_parts = []
                    gemini_payload = []
                    for msg in api_payload:
                        role = msg.get("role", "user")
                        content = msg.get('content', '')
                        if role == "system":
                            system_parts.append(content)
                        else:
                            gemini_role = "model" if role in ("assistant", "bot", "model") else "user"
                            gemini_payload.append({'role': gemini_role, 'parts': [content]})

                    if system_parts:
                        system_text = "\n\n---\n\n".join(system_parts)
                        res = await asyncio.to_thread(
                            _gemini_generate, client, target_model_name, gemini_payload,
                            system_instruction=system_text
                        )
                    else:
                        res = await asyncio.to_thread(_gemini_generate, client, target_model_name, gemini_payload)
                else:
                    res = await asyncio.to_thread(_gemini_generate, client, target_model_name, api_payload)

                return res.text

        except Exception as e:
            err = str(e)
            print(f"⚠️ API error {attempt+1} ({active_model}): {err}")

            if "rate_limit" in err.lower() or "429" in err or "quota" in err.lower():
                if active_model == "gemini":
                     print(f"⚠️ Quota exceeded in Generate Response. Rotating key...")
                     KeyManager.get_instance().rotate()

                await asyncio.sleep(delay)
                delay *= 2
                if attempt == max_retries - 1:
                    return f"ADMIN ERROR (RATE_LIMIT):\n{err}" if user_id == admin_id else "⏳ ترافیک بالا، لطفاً بعداً تلاش کنید."
                continue

            if "Safety" in err or "400" in err:
                return "⛔ درخواست قابل پردازش نیست."
            if "500" in err or "Connection" in err:
                pass  # Continue to retries

            if attempt == max_retries - 1:
                if active_model == "gemini" and _profile_uses_openai_compat():
                    print(f"🔄 ArvanCloud failed completely. Auto-switching to Google SDK (free) for this request...")
                    return await generate_response(user_id, api_payload, admin_id, model="gemini_sdk")
                elif active_model != "gemini":
                    print(f"🔄 {active_model} failed completely. Auto-switching to Gemini for this request...")
                    return await generate_response(user_id, api_payload, admin_id, model="gemini")

                return "⏳ ترافیک بالا، لطفاً بعداً تلاش کنید."

    return "⛔ خطای نامشخص سیستم."


async def generate_response_stream(user_id: int, api_payload: list, admin_id: int, model: str = None) -> AsyncGenerator[str, None]:
    """
    Streaming version of generate_response.
    Yields chunks of text as they are generated.
    """
    try:
        is_vision = isinstance(api_payload, list) and any(isinstance(part, Image.Image) for part in api_payload)

        if model and model in ["openai", "gemini", "deepseek", "gemini_sdk"]:
            active_model = model
        else:
            active_model = ROUTER["vision"] if is_vision else ROUTER["text_gen"]

        if active_model == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]

            stream = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages_payload,
                    temperature=0.7,
                    max_tokens=2000,
                    stream=True
                )
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        elif active_model == "deepseek":
            messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]
            deepseek_client = DeepSeekClient()
            async for chunk in deepseek_client.chat_completion_stream(messages_payload):
                yield chunk
            return

        elif active_model == "gemini_sdk":
            target_model_name = AVAILABLE_MODELS["gemini"]["heavy_model"]
            client = _gemini_client(GOOGLE_API_KEY)

            if isinstance(api_payload[0], dict):
                system_parts = []
                gemini_payload = []
                for msg in api_payload:
                    role = msg.get("role", "user")
                    content = msg.get('content', '')
                    if role == "system":
                        system_parts.append(content)
                    else:
                        gemini_role = "model" if role in ("assistant", "bot", "model") else "user"
                        gemini_payload.append({'role': gemini_role, 'parts': [content]})
                if system_parts:
                    system_text = "\n\n---\n\n".join(system_parts)
                    response = await asyncio.to_thread(
                        _gemini_generate, client, target_model_name, gemini_payload,
                        stream=True, system_instruction=system_text
                    )
                else:
                    response = await asyncio.to_thread(_gemini_generate, client, target_model_name, gemini_payload, stream=True)
            else:
                response = await asyncio.to_thread(_gemini_generate, client, target_model_name, api_payload, stream=True)

            for chunk in response:
                try:
                    if chunk.text:
                        yield chunk.text
                except (ValueError, AttributeError):
                    pass
            return

        elif active_model == "gemini" and _profile_uses_openai_compat():
            prof = _active_profile()
            client = _openai_compat_client()
            target = prof["text_model"]
            if model and model.lower() not in ("gemini", "openai", "deepseek"):
                target = model
            messages_payload = api_payload if isinstance(api_payload[0], dict) else [{"role": "user", "content": api_payload[0]}]
            messages_payload = _normalize_roles_openai(messages_payload)
            stream = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=target,
                    messages=messages_payload,
                    temperature=0.7,
                    max_tokens=2000,
                    stream=True,
                )
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return

        elif active_model == "gemini":
            target_model_name = AVAILABLE_MODELS["gemini"]["heavy_model"]
            if model and model.lower() != "gemini":
                target_model_name = model
            client = _gemini_client(GOOGLE_API_KEY)

            system_parts = []
            gemini_payload = []
            if isinstance(api_payload[0], dict):
                for msg in api_payload:
                    role = msg.get("role", "user")
                    content = msg.get('content', '')
                    if role == "system":
                        system_parts.append(content)
                    else:
                        gemini_role = "model" if role in ("assistant", "bot", "model") else "user"
                        gemini_payload.append({'role': gemini_role, 'parts': [content]})
            else:
                gemini_payload = api_payload

            if isinstance(api_payload[0], dict):
                if system_parts:
                    system_text = "\n\n---\n\n".join(system_parts)
                    response = await asyncio.to_thread(
                        _gemini_generate, client, target_model_name, gemini_payload,
                        stream=True, system_instruction=system_text
                    )
                else:
                    response = await asyncio.to_thread(_gemini_generate, client, target_model_name, gemini_payload, stream=True)
            else:
                response = await asyncio.to_thread(_gemini_generate, client, target_model_name, gemini_payload, stream=True)

            for chunk in response:
                try:
                    if chunk.text:
                        yield chunk.text
                except (ValueError, AttributeError):
                    print("⚠️ Streaming chunk has no 'text' attribute, likely a safety block.")
                    try:
                        if chunk.prompt_feedback.block_reason:
                            yield f"⛔️ پاسخ به دلیل خط مشی ایمنی مسدود شد."
                    except Exception:
                        pass

    except Exception as e:
        print(f"⚠️ Streaming Error ({active_model}): {e}")
        if active_model == "gemini" and _profile_uses_openai_compat():
            print(f"🔄 ArvanCloud streaming failed. Auto-switching to Google SDK (free) stream...")
            async for chunk in generate_response_stream(user_id, api_payload, admin_id, model="gemini_sdk"):
                yield chunk
            return
        elif active_model != "gemini":
            print(f"🔄 {active_model} streaming failed. Auto-switching to Gemini stream...")
            async for chunk in generate_response_stream(user_id, api_payload, admin_id, model="gemini"):
                yield chunk
            return

        yield f"⛔ خطا در تولید پاسخ: {str(e)}"
