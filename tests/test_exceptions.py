# -*- coding: utf-8 -*-
"""
Tests for exception hierarchy.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from exceptions import (
    BotError, ConfigError, APIError,
    GeminiAPIError, DeepSeekAPIError, OpenAIAPIError, ArvanAPIError,
    SearchError, EmbeddingError, StreamingError, SubscriptionError, ValidationError,
    RAGError, NoKnowledgeFoundError, InsufficientDataError, InvalidInputError,
)


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    def test_bot_error_is_base(self):
        assert issubclass(BotError, Exception)
        assert issubclass(ConfigError, BotError)
        assert issubclass(APIError, BotError)
        assert issubclass(SearchError, BotError)
        assert issubclass(EmbeddingError, BotError)
        assert issubclass(StreamingError, BotError)
        assert issubclass(SubscriptionError, BotError)
        assert issubclass(ValidationError, BotError)

    def test_api_error_subclasses(self):
        assert issubclass(GeminiAPIError, APIError)
        assert issubclass(DeepSeekAPIError, APIError)
        assert issubclass(OpenAIAPIError, APIError)
        assert issubclass(ArvanAPIError, APIError)

    def test_backward_compat_aliases(self):
        assert RAGError is BotError
        assert InvalidInputError is ValidationError
        assert issubclass(NoKnowledgeFoundError, ValidationError)
        assert issubclass(InsufficientDataError, ValidationError)


class TestExceptionAttributes:
    """Test exception attributes and messages."""

    def test_bot_error_message(self):
        e = BotError("test error")
        assert str(e) == "test error"
        assert e.message == "test error"

    def test_bot_error_cause(self):
        cause = ValueError("original")
        e = BotError("wrapped", cause=cause)
        assert e.cause is cause
        assert e.__cause__ is cause

    def test_config_error_key(self):
        e = ConfigError("missing key", key="API_KEY")
        assert e.key == "API_KEY"

    def test_api_error_provider_status(self):
        e = APIError("failed", provider="gemini", status_code=429)
        assert e.provider == "gemini"
        assert e.status_code == 429

    def test_gemini_api_error(self):
        e = GeminiAPIError("rate limited", status_code=429)
        assert e.provider == "gemini"
        assert e.status_code == 429

    def test_deepseek_api_error(self):
        e = DeepSeekAPIError("timeout")
        assert e.provider == "deepseek"

    def test_search_error_engine(self):
        e = SearchError("no results", engine="faiss")
        assert e.engine == "faiss"

    def test_subscription_error_user(self):
        e = SubscriptionError("limit exceeded", user_id=12345, tier="FREE")
        assert e.user_id == 12345
        assert e.tier == "FREE"

    def test_validation_error_reason(self):
        e = ValidationError("injection detected")
        assert e.reason == "injection detected"
        assert "injection detected" in str(e)

    def test_no_knowledge_found_default_message(self):
        e = NoKnowledgeFoundError()
        assert "No relevant knowledge" in str(e)

    def test_insufficient_data_default_message(self):
        e = InsufficientDataError()
        assert "insufficient" in str(e).lower()


class TestExceptionUsage:
    """Test that exceptions can be raised and caught correctly."""

    def test_catch_bot_error_for_config(self):
        with pytest.raises(BotError):
            raise ConfigError("test")

    def test_catch_api_error_for_gemini(self):
        with pytest.raises(APIError):
            raise GeminiAPIError("test")

    def test_catch_validation_for_no_knowledge(self):
        with pytest.raises(ValidationError):
            raise NoKnowledgeFoundError()

    def test_catch_validation_for_insufficient(self):
        with pytest.raises(ValidationError):
            raise InsufficientDataError()
