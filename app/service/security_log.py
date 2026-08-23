"""Structured security logging. Never log tokens, JWTs, or secrets."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger("prem3.security")

_FORBIDDEN = frozenset(
    {
        "authorization",
        "token",
        "jwt",
        "session_token",
        "secret",
        "stripe_secret",
        "stripe_secret_key",
        "webhook_secret",
        "signing_secret",
        "raw_body",
        "payload",
        "stripe-signature",
        "stripe_signature",
        "refresh_token",
        "access_token",
        "google_refresh_token",
        "google_access_token",
        "client_secret",
        "ciphertext",
        "wrapped_dek",
        "nonce",
        "dek",
    }
)


def security_log(event: str, **fields: Any) -> None:
    safe = {
        key: value
        for key, value in fields.items()
        if key.lower() not in _FORBIDDEN and value is not None
    }
    _LOGGER.info("%s %s", event, safe)
