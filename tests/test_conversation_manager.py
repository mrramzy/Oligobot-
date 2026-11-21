# -*- coding: utf-8 -*-
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from conversation_manager import ConversationManager


def test_init():
    cm = ConversationManager(max_history_messages=10, messages_to_keep=4)
    assert cm.max_history_messages == 10


def test_short_history_unchanged():
    cm = ConversationManager(max_history_messages=10, messages_to_keep=4)
    short = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    result = asyncio.run(cm.manage(short))
    assert len(result) == 2


def test_invalid_params():
    with pytest.raises(ValueError):
        ConversationManager(max_history_messages=2, messages_to_keep=5)
