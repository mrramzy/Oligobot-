
# -*- coding: utf-8 -*-
"""
Centralised, domain-specific exceptions for the OLIGOBOT system.
Hierarchical taxonomy: BotError (base) → provider/layer-specific subclasses.
"""


class BotError(Exception):
    """Base exception for all custom errors in the OLIGOBOT application."""
    def __init__(self, message="A general bot error occurred.", cause=None):
        self.message = message
        self.cause = cause
        super().__init__(self.message)
        if cause:
            self.__cause__ = cause


class ConfigError(BotError):
    """Missing or misconfigured environment variables, settings, or keys."""
    def __init__(self, message="Configuration error.", key=None):
        self.key = key
        super().__init__(message)


class APIError(BotError):
    """External API call failed (network, auth, rate limit, server error)."""
    def __init__(self, message="API call failed.", provider=None, status_code=None, cause=None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message, cause=cause)


class GeminiAPIError(APIError):
    """Google Gemini API failure."""
    def __init__(self, message="Gemini API error.", status_code=None, cause=None):
        super().__init__(message, provider="gemini", status_code=status_code, cause=cause)


class DeepSeekAPIError(APIError):
    """DeepSeek API failure."""
    def __init__(self, message="DeepSeek API error.", status_code=None, cause=None):
        super().__init__(message, provider="deepseek", status_code=status_code, cause=cause)


class OpenAIAPIError(APIError):
    """OpenAI API failure."""
    def __init__(self, message="OpenAI API error.", status_code=None, cause=None):
        super().__init__(message, provider="openai", status_code=status_code, cause=cause)


class ArvanAPIError(APIError):
    """ArvanCloud API failure."""
    def __init__(self, message="ArvanCloud API error.", status_code=None, cause=None):
        super().__init__(message, provider="arvan", status_code=status_code, cause=cause)


class SearchError(BotError):
    """Vector search failure (FAISS, ChromaDB)."""
    def __init__(self, message="Vector search failed.", engine=None, cause=None):
        self.engine = engine
        super().__init__(message, cause=cause)


class EmbeddingError(BotError):
    """Embedding generation failure."""
    def __init__(self, message="Embedding generation failed.", provider=None, cause=None):
        self.provider = provider
        super().__init__(message, cause=cause)


class StreamingError(BotError):
    """Streaming response failure (connection dropped, chunk error)."""
    def __init__(self, message="Streaming response failed.", cause=None):
        super().__init__(message, cause=cause)


class SubscriptionError(BotError):
    """Subscription/quota limit exceeded or billing error."""
    def __init__(self, message="Subscription error.", user_id=None, tier=None):
        self.user_id = user_id
        self.tier = tier
        super().__init__(message)


class ValidationError(BotError):
    """Input validation failure (security, format, injection)."""
    def __init__(self, reason: str):
        self.reason = reason
        message = f"Validation failed: {reason}"
        super().__init__(message)


# --- Backward-compatible aliases ---
RAGError = BotError

class NoKnowledgeFoundError(ValidationError):
    """Raised when RAG returns no relevant documents."""
    def __init__(self, message="No relevant knowledge was found for the query."):
        super().__init__(message)


class InsufficientDataError(ValidationError):
    """Raised when input is insufficient for analysis (blurry image, etc.)."""
    def __init__(self, message="The provided data is insufficient for analysis."):
        super().__init__(message)


InvalidInputError = ValidationError
