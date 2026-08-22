"""Server-owned Data Foundation identifiers."""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier


def _opaque(prefix: str) -> str:
    return validate_resource_identifier(f"{prefix}_{uuid4().hex[:20]}", field="resource_id")


def new_requirement_id() -> str:
    return _opaque("dfreq")


def new_candidate_id() -> str:
    return _opaque("dfcand")


def new_source_id() -> str:
    return _opaque("dfsrc")


def new_plan_id() -> str:
    return _opaque("dfplan")


def new_finding_id() -> str:
    return _opaque("dffind")


def new_receipt_id() -> str:
    return _opaque("dfrcpt")


def new_preview_id() -> str:
    return _opaque("dfprev")


def new_approval_id() -> str:
    return _opaque("dfapr")


def new_run_id() -> str:
    return _opaque("dfrun")


def new_cycle_id() -> str:
    return _opaque("mcycle")


def new_gap_id() -> str:
    return _opaque("dfgap")


def new_intelligence_brief_id() -> str:
    return _opaque("dfbrief")
