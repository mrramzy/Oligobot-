# -*- coding: utf-8 -*-
"""
Centralized retry/backoff utilities for all external API calls.
Uses tenacity for consistent retry policies across the codebase.
"""
import logging
from functools import wraps
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def _is_retryable_error(error):
    """Check if an error is retryable (quota, rate limit, connection, server)."""
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    error_str = str(error).lower()
    retryable_codes = ["429", "quota", "resource_exhausted", "rate limit",
                       "500", "502", "503", "504", "timeout", "connection"]
    return any(code in error_str for code in retryable_codes)


def _is_quota_error(error):
    """Check if an error is a quota/rate limit error."""
    error_str = str(error).lower()
    return any(code in error_str for code in ["429", "quota", "resource_exhausted", "rate limit"])


def gemini_retry(func):
    """
    Retry decorator for Google Gemini API calls.
    - 3 attempts, exponential backoff (2^attempt seconds)
    - Retries on: 429/quota, connection errors, 500+ errors
    - Rotates API key on quota errors
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if _is_quota_error(e):
                logger.warning(f"Gemini rate limited, rotating key: {e}")
                try:
                    from key_manager import KeyManager
                    KeyManager.get_instance().rotate()
                except Exception:
                    pass
            raise
    return wrapper


def deepseek_retry(func):
    """
    Retry decorator for DeepSeek API calls.
    - 3 attempts, exponential backoff
    - Retries on: connection errors, 500+ errors, timeouts
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"DeepSeek API error, retrying: {e}")
            raise
    return wrapper


def openai_retry(func):
    """
    Retry decorator for OpenAI API calls.
    - 3 attempts, exponential backoff
    - Retries on: 429, 500+, connection errors
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"OpenAI API error, retrying: {e}")
            raise
    return wrapper


def arvan_retry(func):
    """
    Retry decorator for ArvanCloud API calls.
    - 4 attempts, exponential backoff
    - Retries on: 429, 5xx, connection errors
    """
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"ArvanCloud API error, retrying: {e}")
            raise
    return wrapper


def generic_retry(max_attempts=3, min_wait=2, max_wait=20):
    """
    Generic retry decorator factory for any external API call.
    
    Usage:
        @generic_retry(max_attempts=3)
        async def my_api_call():
            ...
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception(_is_retryable_error),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"API call failed, retrying: {e}")
                raise
        return wrapper
    return decorator
