# -*- coding: utf-8 -*-
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from intent_manager import intent_manager, Intent


def test_singleton_exists():
    assert intent_manager is not None


def test_fast_casual_check():
    assert intent_manager._fast_casual_check("سلام") is True
    assert intent_manager._fast_casual_check("hello") is True
    assert intent_manager._fast_casual_check("normal range of hemoglobin in adults is 12-16 g/dL") is False


@pytest.mark.asyncio
async def test_detect_casual():
    result = await intent_manager.detect_intent("سلام خوبی", [])
    assert result == Intent.CASUAL


@pytest.mark.asyncio
async def test_detect_diagnostic():
    result = await intent_manager.detect_intent("Hb=9 میلی‌گرم در دسی‌لیتر", [])
    assert result in (Intent.DIAGNOSTIC, Intent.EDUCATIONAL)
