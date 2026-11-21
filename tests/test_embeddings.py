# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from embeddings import get_rag_embeddings, ArvanEmbeddings


def test_get_rag_embeddings():
    emb = get_rag_embeddings()
    assert emb is not None


def test_arvan_embeddings_init():
    try:
        ae = ArvanEmbeddings()
        assert ae is not None
    except ValueError:
        pass  # Expected if env not set
