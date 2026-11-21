# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from prompt_manager import PromptManager
from config import PSL_PATH


def test_import():
    assert PromptManager is not None


def test_load_prompts():
    pm = PromptManager(base_path=PSL_PATH)
    pm.load_prompts()
    prompts = pm.get_all_prompts()
    assert isinstance(prompts, dict)
    assert len(prompts) > 0


def test_get_prompt():
    pm = PromptManager(base_path=PSL_PATH)
    pm.load_prompts()
    first_key = list(pm.get_all_prompts().keys())[0]
    result = pm.get_prompt(first_key)
    assert result is not None
    assert len(result) > 0
