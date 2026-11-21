# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from subscription_manager import subscription_manager, SubscriptionTier, TIER_CONFIG


def test_new_user_subscription():
    sub = subscription_manager.get_user_subscription(123456789)
    assert "tier" in sub


def test_can_query():
    result = subscription_manager.can_query(123456789)
    assert isinstance(result, bool)


def test_tier_config_complete():
    assert SubscriptionTier.FREE in TIER_CONFIG
    assert SubscriptionTier.PRO in TIER_CONFIG
    assert TIER_CONFIG[SubscriptionTier.FREE]["daily_queries"] > 0


def test_increment_usage():
    uid = 9999991
    subscription_manager.increment_usage(uid)


def test_check_access():
    result = subscription_manager.check_access(9999992)
    assert isinstance(result, dict)
    assert "allowed" in result
