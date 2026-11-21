# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from keyword_extractor import KeywordExtractor


def test_enrich_query_farsi():
    ke = KeywordExtractor()
    result = ke.enrich_query("رنج نرمال هموگلوبین چقدر است")
    assert isinstance(result, list)


def test_enrich_query_english():
    ke = KeywordExtractor()
    result = ke.enrich_query("normal range of hemoglobin")
    assert isinstance(result, list)
