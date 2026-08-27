"""Deterministic Identity Graph fingerprints via canonical serialization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.modeling.common.fingerprints import canonical_fingerprint

_EXCLUDE = frozenset(
    {
        "fingerprint",
        "updated_at",
        "created_at",
        "created_by",
        "confirmed_at",
        "confirmed_by",
    }
)


def identity_fingerprint(value: BaseModel | dict[str, Any]) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude=_EXCLUDE)
    else:
        payload = {key: item for key, item in value.items() if key not in _EXCLUDE}
    return canonical_fingerprint(payload)
