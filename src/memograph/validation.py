"""Input validation and path-containment helpers.

All file paths derived from user, transcript, or LLM input must pass through
these helpers.  This is the single boundary that prevents path traversal.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import ValidationError

TOPIC_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


def validate_topic_id(topic_id: str) -> str:
    """Return a validated topic ID or raise :class:`ValidationError`.

    Rules: lowercase, starts with a letter, 1-50 chars, ``[a-z0-9_]`` only.
    This deliberately forbids separators and parent traversal components.
    """
    if not isinstance(topic_id, str) or not topic_id:
        raise ValidationError("topic_id must be a non-empty string")
    if len(topic_id) > 50:
        raise ValidationError(f"topic_id too long: {len(topic_id)} > 50")
    if not TOPIC_ID_RE.fullmatch(topic_id):
        raise ValidationError(
            f"Invalid topic_id {topic_id!r}: use lowercase letters, digits, "
            "and underscores; must start with a letter"
        )
    return topic_id


def validate_agent_id(agent_id: str) -> str:
    """Agent IDs use the same conservative grammar as topic IDs."""
    return validate_topic_id(agent_id)


def validate_fact_content(content: str, max_length: int = 1000) -> str:
    """Validate atomic fact content."""
    if not isinstance(content, str) or not content.strip():
        raise ValidationError("Fact content must be a non-empty string")
    if len(content) > max_length:
        raise ValidationError(f"Fact content too long: {len(content)} > {max_length}")
    # Newlines are allowed in facts, but NUL is never useful in text storage.
    if "\x00" in content:
        raise ValidationError("Fact content cannot contain NUL bytes")
    return content


def validate_summary(summary: str, max_length: int = 80) -> str:
    """Validate an index pointer summary."""
    if not isinstance(summary, str) or not summary.strip():
        raise ValidationError("Summary must be a non-empty string")
    cleaned = " ".join(summary.split())
    if len(cleaned) > max_length:
        raise ValidationError(f"Summary too long: {len(cleaned)} > {max_length}")
    return cleaned


def normalize_topic_id(name: str) -> str:
    """Convert a human-readable name into a valid, deterministic topic ID."""
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Cannot normalize an empty name")
    text = name.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValidationError(f"Cannot normalize {name!r} to a topic_id")
    if not text[0].isalpha():
        text = f"topic_{text}"
    text = text[:50].rstrip("_")
    return validate_topic_id(text)


def stable_id(text: str, prefix: str = "id", length: int = 12) -> str:
    """Return a process-independent ID.

    Python's built-in ``hash()`` is salted per process and must never be used
    for persistent memory identifiers.  SHA-256 is stable across restarts.
    """
    if not isinstance(text, str):
        raise ValidationError("stable_id expects a string")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
    candidate = f"{prefix}_{digest}" if prefix else digest
    return validate_topic_id(candidate)


def safe_relative_path(base: Path, relative: str | Path) -> Path:
    """Resolve ``relative`` under ``base`` and reject escapes.

    ``Path.is_relative_to`` is used rather than string prefix checks because
    it handles symlinks, ``..``, and absolute paths correctly after resolution.
    """
    base = Path(base).resolve()
    rel = Path(relative)
    if rel.is_absolute():
        raise ValidationError(f"Absolute paths are not allowed: {relative}")
    candidate = (base / rel).resolve()
    if not candidate.is_relative_to(base):
        raise ValidationError(f"Path escapes its base directory: {relative}")
    return candidate


def safe_topic_path(base: Path, topic_id: str, suffix: str) -> Path:
    """Build a validated ``topics/<topic_id><suffix>`` path."""
    validate_topic_id(topic_id)
    if suffix not in {".json", ".md", ".jsonl"}:
        raise ValidationError(f"Unsupported topic file suffix: {suffix}")
    return safe_relative_path(base / "topics", f"{topic_id}{suffix}")
