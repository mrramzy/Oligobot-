# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from config import ROUTER, AVAILABLE_MODELS, LLM_PROFILES, ACTIVE_LLM_PROFILE, LLM_PROFILE


def test_router_values_valid():
    for task, provider in ROUTER.items():
        assert provider in AVAILABLE_MODELS, f"ROUTER['{task}']='{provider}' not in AVAILABLE_MODELS"


def test_llm_profiles_loaded():
    assert "backend" in ACTIVE_LLM_PROFILE
    assert "text_model" in ACTIVE_LLM_PROFILE
    assert LLM_PROFILE in LLM_PROFILES or LLM_PROFILE == 1


def test_env_keys_loadable():
    from config import TELEGRAM_TOKEN, GOOGLE_API_KEY, ADMIN_ID
    _ = TELEGRAM_TOKEN
    _ = GOOGLE_API_KEY
    _ = ADMIN_ID
