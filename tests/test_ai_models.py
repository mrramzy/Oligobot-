# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from PIL import Image
from ai_models import (
    _active_profile as get_active_profile,
    _profile_uses_openai_compat, _gemini_client,
    _normalize_roles_openai, build_medical_dict, _image_to_data_url,
)


def test_active_profile():
    p = get_active_profile()
    assert "backend" in p
    assert "text_model" in p


def test_profile_routing():
    result = _profile_uses_openai_compat()
    assert isinstance(result, bool)


def test_gemini_client():
    c = _gemini_client(api_key="fake-key")
    assert c is not None


def test_normalize_roles():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "bot", "content": "hello"},
        {"role": "assistant", "content": "hey"},
        {"role": "model", "content": "yo"},
    ]
    result = _normalize_roles_openai(msgs)
    roles = [m["role"] for m in result]
    assert roles == ["user", "assistant", "assistant", "assistant"]


def test_medical_dict():
    d = build_medical_dict()
    assert "هموگلوبین" in d
    assert d["هموگلوبین"] == "hemoglobin"


def test_image_to_data_url():
    img = Image.new("RGB", (10, 10), color="red")
    url = _image_to_data_url(img)
    assert url.startswith("data:image/png;base64,")
