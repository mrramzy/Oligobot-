# -*- coding: utf-8 -*-
"""
Shared fixtures and configuration for pytest.
"""
import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    from unittest.mock import MagicMock, AsyncMock
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    redis_mock.exists = AsyncMock(return_value=False)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.ttl = AsyncMock(return_value=-1)
    return redis_mock


@pytest.fixture
def sample_api_payload():
    """Sample API payload for generation tests."""
    return [
        {"role": "system", "content": "You are a medical assistant."},
        {"role": "user", "content": "What is hemoglobin?"}
    ]


@pytest.fixture
def temp_subscription_data(tmp_path):
    """Create temporary subscription data file."""
    import json
    data = {
        "users": {
            "12345": {
                "tier": "FREE",
                "daily_queries": 0,
                "daily_limit": 10,
                "monthly_queries": 0,
                "monthly_limit": 3000,
                "active": True,
                "created_at": "2026-01-01T00:00:00"
            }
        }
    }
    file_path = tmp_path / "subscription_data.json"
    file_path.write_text(json.dumps(data))
    return str(file_path)


@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    return {
        "user_id": 12345,
        "display_name": "Test User",
        "created_at": "2026-01-01T00:00:00",
        "onboarding_step": "complete",
        "career": "hematologist"
    }
