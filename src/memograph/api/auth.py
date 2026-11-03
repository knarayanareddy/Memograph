"""Constant-time API-key authentication helpers."""

from __future__ import annotations

import hashlib
import secrets


class APIKeyAuth:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        """A non-secret, stable identifier used as a rate-limit key."""
        return self._fingerprint

    @staticmethod
    def extract(x_api_key: str | None, authorization: str | None) -> str | None:
        if x_api_key:
            return x_api_key.strip()
        if authorization and authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return None

    def verify(self, x_api_key: str | None, authorization: str | None) -> str | None:
        candidate = self.extract(x_api_key, authorization)
        if candidate is None:
            return None
        if not secrets.compare_digest(candidate, self._api_key):
            return None
        return self._fingerprint
