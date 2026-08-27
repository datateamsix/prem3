"""Deterministic analytical keys. BQ-only; never person IDs, never Firestore fields."""

from __future__ import annotations

import hashlib


def _sha256_hex(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def session_id(*, ga4_property_id: str, subject_key: str, ga_session_id: str) -> str:
    """Property-scoped session key. ga_session_id is not globally unique."""
    return _sha256_hex(ga4_property_id, subject_key, ga_session_id)


def journey_id(*, project_id: str, identity_strategy: str, subject_key: str) -> str:
    """Project-scoped journey identity key. Not a PreM3 person ID."""
    return _sha256_hex(project_id, identity_strategy, subject_key)
