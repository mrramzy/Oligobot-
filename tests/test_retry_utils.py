# -*- coding: utf-8 -*-
"""
Tests for retry_utils module.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from retry_utils import gemini_retry, deepseek_retry, openai_retry, arvan_retry, generic_retry


class TestRetryDecorators:
    """Test retry decorator behavior."""

    @pytest.mark.asyncio
    async def test_generic_retry_succeeds_first_try(self):
        """Function succeeds on first attempt."""
        @generic_retry(max_attempts=3)
        async def success():
            return "ok"

        result = await success()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_generic_retry_succeeds_after_failure(self):
        """Function succeeds after initial failure."""
        call_count = 0

        @generic_retry(max_attempts=3, min_wait=0.01, max_wait=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generic_retry_exhausted(self):
        """Function fails after max retries."""
        @generic_retry(max_attempts=2, min_wait=0.01, max_wait=0.01)
        async def always_fails():
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            await always_fails()

    @pytest.mark.asyncio
    async def test_gemini_retry_retries_on_quota(self):
        """Gemini retry retries on quota error."""
        call_count = 0

        @gemini_retry
        async def gemini_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("429 quota exceeded")
            return "ok"

        result = await gemini_call()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_deepseek_retry_on_connection_error(self):
        """DeepSeek retry triggers on connection errors."""
        call_count = 0

        @deepseek_retry
        async def deepseek_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "ok"

        result = await deepseek_call()
        assert result == "ok"
        assert call_count == 2

    def test_arvan_retry_sync(self):
        """Arvan retry works with sync functions."""
        call_count = 0

        @arvan_retry
        def arvan_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Timeout")
            return "ok"

        result = arvan_call()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_preserves_function_name(self):
        """Retry decorator preserves original function name."""
        @generic_retry(max_attempts=1)
        async def my_function():
            return "ok"

        assert my_function.__name__ == "my_function"
