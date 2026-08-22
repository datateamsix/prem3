"""Server-owned Business IQ identifiers."""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier


def _opaque(prefix: str) -> str:
    return validate_resource_identifier(f"{prefix}_{uuid4().hex[:20]}", field="resource_id")


def new_profile_id() -> str:
    return _opaque("bprof")


def new_snapshot_id() -> str:
    return _opaque("bps")


def new_fact_id() -> str:
    return _opaque("bfact")


def new_event_id() -> str:
    return _opaque("bevt")


def new_channel_id() -> str:
    return _opaque("bch")


def new_relationship_id() -> str:
    return _opaque("brel")


def new_hypothesis_id() -> str:
    return _opaque("bhyp")


def new_gap_id() -> str:
    return _opaque("bgap")


def new_prior_id() -> str:
    return _opaque("bpe")


def new_brief_id() -> str:
    return _opaque("bbrief")


def new_proposal_id() -> str:
    return _opaque("bprop")


def new_clarification_id() -> str:
    return _opaque("bclar")


def new_receipt_id() -> str:
    return _opaque("brcpt")
