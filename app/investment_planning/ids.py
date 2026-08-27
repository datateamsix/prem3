"""Server-owned Investment Planning identifiers."""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier


def _opaque(prefix: str) -> str:
    return validate_resource_identifier(f"{prefix}_{uuid4().hex[:20]}", field="resource_id")


def new_plan_id() -> str:
    return _opaque("ipln")


def new_source_version_id() -> str:
    return _opaque("bsrc")


def new_mapping_id() -> str:
    return _opaque("imap")


def new_snapshot_ref_id() -> str:
    return _opaque("psnap")


def new_validation_receipt_id() -> str:
    return _opaque("iprc")


def new_dimension_mapping_id() -> str:
    return _opaque("pdmap")
