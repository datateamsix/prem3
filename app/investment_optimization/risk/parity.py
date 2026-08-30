"""Risk-neutral parity against the accepted native Meridian allocation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.errors import RiskNeutralParityFailedError
from app.investment_optimization.ids import new_parity_receipt_id
from app.investment_optimization.risk.models import (
    CandidatePortfolio,
    RiskEvaluationPolicy,
    RiskNeutralParityReceipt,
)
from app.investment_planning.fingerprint import metadata_fingerprint


def build_parity_receipt(
    *,
    tenant_id: str,
    project_id: str,
    policy: RiskEvaluationPolicy,
    native_candidate: CandidatePortfolio,
    selected_candidate: CandidatePortfolio,
    now: datetime | None = None,
) -> RiskNeutralParityReceipt:
    matched = (
        not policy.risk_penalties_enabled
        and selected_candidate.allocation_fingerprint == native_candidate.allocation_fingerprint
        and selected_candidate.optimization_run_id == native_candidate.optimization_run_id
        and selected_candidate.model_version_ref == native_candidate.model_version_ref
        and selected_candidate.base_approved_plan_ref == native_candidate.base_approved_plan_ref
    )
    created = now or datetime.now(UTC)
    receipt_id = new_parity_receipt_id()
    payload = {
        "native_optimization_run_id": native_candidate.optimization_run_id,
        "native_allocation_fingerprint": native_candidate.allocation_fingerprint,
        "selected_allocation_fingerprint": selected_candidate.allocation_fingerprint,
        "approved_plan_ref": native_candidate.base_approved_plan_ref,
        "objective": policy.objective,
        "model_version_ref": policy.model_version_ref,
        "assumption_set_ref": policy.future_assumption_set_ref or "",
        "constraint_set_ref": policy.constraint_set_ref or "",
        "optimization_readiness_ref": policy.optimization_readiness_ref,
        "matched": matched,
    }
    receipt = RiskNeutralParityReceipt(
        parity_receipt_id=receipt_id,
        project_id=project_id,
        tenant_id=tenant_id,
        native_optimization_run_id=native_candidate.optimization_run_id,
        native_allocation_fingerprint=native_candidate.allocation_fingerprint,
        selected_allocation_fingerprint=selected_candidate.allocation_fingerprint,
        approved_plan_ref=native_candidate.base_approved_plan_ref,
        objective=policy.objective,
        model_version_ref=policy.model_version_ref,
        assumption_set_ref=policy.future_assumption_set_ref,
        constraint_set_ref=policy.constraint_set_ref,
        optimization_readiness_ref=policy.optimization_readiness_ref,
        matched=matched,
        limitations=() if matched else ("RISK_NEUTRAL_PARITY_FAILED",),
        fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )
    if not matched:
        raise RiskNeutralParityFailedError(
            "Risk-neutral selection does not match the accepted native Meridian allocation."
        )
    return receipt
