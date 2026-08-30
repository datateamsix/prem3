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


def new_advanced_readiness_id() -> str:
    return _opaque("oaready")


def new_constraint_validation_id() -> str:
    return _opaque("ocval")


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


def new_optimization_run_id() -> str:
    return _opaque("orun")


def new_optimization_result_id() -> str:
    return _opaque("ores")


def new_scenario_id() -> str:
    return _opaque("oscn")


def new_proposal_decision_receipt_id() -> str:
    return _opaque("odrc")


def new_proposal_readiness_receipt_id() -> str:
    return _opaque("opready")


def new_planning_decision_id() -> str:
    return _opaque("odec")


def new_risk_policy_id() -> str:
    return _opaque("orpol")


def new_candidate_id() -> str:
    return _opaque("ocand")


def new_risk_evaluation_id() -> str:
    return _opaque("oreval")


def new_frontier_id() -> str:
    return _opaque("ofrn")


def new_frontier_selection_id() -> str:
    return _opaque("osel")


def new_parity_receipt_id() -> str:
    return _opaque("opary")


def new_feasibility_receipt_id() -> str:
    return _opaque("ofeas")
