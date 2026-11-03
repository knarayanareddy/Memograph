"""Structured security audit logging for the REST API."""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER = logging.getLogger("memograph.audit")


def audit(event: str, **fields: Any) -> None:
    """Emit one structured audit record without secrets or request bodies."""
    LOGGER.info(
        json.dumps(
            {"event": event, **fields},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
