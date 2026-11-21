# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from key_manager import KeyManager


def test_singleton():
    km1 = KeyManager.get_instance()
    km2 = KeyManager.get_instance()
    assert km1 is km2


def test_has_keys():
    km = KeyManager.get_instance()
    assert len(km.keys) > 0


def test_configure_no_crash():
    km = KeyManager.get_instance()
    km.configure()
