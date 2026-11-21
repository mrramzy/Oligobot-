# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from citation_manager import CitationManager


def test_init():
    cm = CitationManager()
    assert cm is not None


def test_normalize_visual_terms():
    result = CitationManager._normalize_visual_terms("See Figure 3 and Table 1.2")
    assert "تصویر" in result
    assert "جدول" in result


def test_get_display_name():
    cm = CitationManager()
    result = cm.get_display_name("henry", "fa")
    assert isinstance(result, str)
    assert len(result) > 0
