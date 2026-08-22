"""Canonical logical names. Original filenames are preserved."""

from __future__ import annotations

import re

_SAFE = re.compile(r"[^a-z0-9_]+")


def provider_slug(value: str) -> str:
    slug = _SAFE.sub("_", value.lower()).strip("_")
    if slug in {"", "other", "meta"}:
        raise ValueError("Provider slug must be explicit; 'other' and bare 'meta' are forbidden.")
    return slug


def canonical_logical_name(
    *,
    source_slug: str,
    data_role: str,
    grain: str,
    start_date: str,
    end_date: str,
    version: int,
    ext: str,
) -> str:
    return (
        f"{provider_slug(source_slug)}__{data_role}__{grain}__"
        f"{start_date}__{end_date}__v{version}.{ext.lstrip('.')}"
    )
