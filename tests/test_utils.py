# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from utils import (
    sanitize_for_llm, detect_language, detect_clinical_domain,
    get_time_metadata, escape_markdown_special_chars, extract_text_from_file,
)


def test_sanitize_for_llm():
    assert sanitize_for_llm("") == ""
    assert sanitize_for_llm(None) == ""
    assert sanitize_for_llm("hello\x00world") == "helloworld"
    assert len(sanitize_for_llm("x" * 30000)) == 20000


def test_detect_language():
    assert detect_language("سلام دنیا") == "fa"
    assert detect_language("hello world") == "en"


def test_detect_clinical_domain():
    assert detect_clinical_domain("هموگلوبین چیست") in ("hematology", "other")
    assert detect_clinical_domain("ادرار کریستال") in ("urinalysis", "other")


def test_get_time_metadata():
    meta = get_time_metadata()
    assert "date" in meta
    assert "hour" in meta


def test_escape_markdown():
    result = escape_markdown_special_chars("test *bold* _underline_")
    assert isinstance(result, str)


def test_extract_text_missing_file():
    assert extract_text_from_file("nonexistent_12345.txt") is None
