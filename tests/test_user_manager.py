# -*- coding: utf-8 -*-
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from user_manager import UserManager


def test_create_and_get():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        um = UserManager(filename=tmp)
        um.create_user(999999, username="test_user", first_name="Test")
        user = um.get_user(999999)
        assert user is not None
        assert user["username"] == "test_user"
    finally:
        os.unlink(tmp)


def test_save_reload():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        um = UserManager(filename=tmp)
        um.create_user(888888, username="save_test")
        um.save()
        um2 = UserManager(filename=tmp)
        user = um2.get_user(888888)
        assert user is not None
        assert user["username"] == "save_test"
    finally:
        os.unlink(tmp)


def test_set_display_name():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        um = UserManager(filename=tmp)
        um.create_user(777777)
        um.set_display_name(777777, "Dr. Smith")
        assert um.get_display_name(777777) == "Dr. Smith"
    finally:
        os.unlink(tmp)
