"""Shared exception types for Memograph."""

from __future__ import annotations


class MemoGraphError(Exception):
    """Base class for Memograph errors."""


class ValidationError(MemoGraphError, ValueError):
    """Raised when caller- or model-supplied data is unsafe or malformed."""


class IndexLimitError(MemoGraphError):
    """Raised when an index update would exceed a hard bandwidth limit."""


class LockUnavailable(MemoGraphError):
    """Raised when an exclusive consolidation lock cannot be acquired."""


class ConsolidationParseError(MemoGraphError, ValueError):
    """Raised when LLM consolidation output cannot be parsed or validated."""


class ProviderError(MemoGraphError):
    """Raised when a provider is misconfigured or returns an unusable response."""


class TokenBudgetError(MemoGraphError):
    """Raised when context cannot fit within the configured token budget."""
