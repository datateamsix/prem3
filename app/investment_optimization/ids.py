"""Server-owned optimization identifiers."""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier


def _opaque(prefix: str) -> str:
    return validate_resource_identifier(f"{prefix}_{uuid4().hex[:20]}", field="resource_id")


def new_proposal_id() -> str:
    return _opaque("oprop")


def new_execution_plan_id() -> str:
    return _opaque("oexec")


def new_constraint_set_id() -> str:
    return _opaque("ocst")


def new_assumption_set_id() -> str:
    return _opaque("oasm")


def new_portfolio_model_mapping_id() -> str:
    return _opaque("pmap")


def new_mapping_entry_id() -> str:
    return _opaque("ment")


def new_consumption_contract_id() -> str:
    return _opaque("omcc")


def new_optimization_input_id() -> str:
    return _opaque("oinc")


def new_readiness_receipt_id() -> str:
    return _opaque("oready")


def new_evidence_coverage_id() -> str:
    return _opaque("oecov")
