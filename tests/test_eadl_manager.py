# -*- coding: utf-8 -*-
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from eadl_manager import EADLManager


def test_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = os.path.join(tmpdir, "eadl.json")
        config = os.path.join(tmpdir, "config.json")
        mgr = EADLManager(storage_file=storage, config_file=config)
        assert mgr is not None


def test_ensure_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = os.path.join(tmpdir, "eadl.json")
        config = os.path.join(tmpdir, "config.json")
        EADLManager(storage_file=storage, config_file=config)
        assert os.path.exists(storage)
        assert os.path.exists(config)
