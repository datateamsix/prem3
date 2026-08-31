"""Recommendation outcome closure. Time passing does not close a receipt."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import OutcomeLifecycleStatus
from app.investment_optimization.ids import new_outcome_receipt_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import (
    DecisionOutcomeObservation,
    ExecutionAdherence,
    InvestmentDecisionRecord,
    PredictionErrorSummary,
    PredictionEvidenceSet,
    RecommendationAdherence,
    RecommendationOutcomeReceipt,
)


def close_outcome_receipt(
    *,
    tenant_id: str,
    project_id: str,
    decision: InvestmentDecisionRecord,
    prediction: PredictionEvidenceSet | None,
    observation: DecisionOutcomeObservation | None = None,
    recommendation_adherence: RecommendationAdherence | None = None,
    execution_adherence: ExecutionAdherence | None = None,
    prediction_error: PredictionErrorSummary | None = None,
    approved_plan_ref: str | None = None,
    outcome_not_observed: bool = False,
) -> RecommendationOutcomeReceipt:
    limitations: list[str] = []
    if prediction is None:
        limitations.append("PREDICTION_EVIDENCE_INCOMPLETE")
    if observation is None:
        limitations.append("OUTCOME_NOT_OBSERVED")
    if execution_adherence is None:
        limitations.append("EXECUTION_EVIDENCE_INCOMPLETE")
    status = OutcomeLifecycleStatus.PARTIAL
    closed_at = None
    can_close = prediction is not None and (observation is not None or outcome_not_observed)
    if can_close:
        status = OutcomeLifecycleStatus.CLOSED
        closed_at = datetime.now(UTC)
    elif prediction is not None and observation is None:
        status = OutcomeLifecycleStatus.AWAITING_OUTCOME
    created = datetime.now(UTC)
    payload = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "decision": decision.decision_fingerprint,
        "prediction": prediction.fingerprint if prediction else "",
        "observation": observation.observation_fingerprint if observation else "",
        "rec_adh": recommendation_adherence.fingerprint if recommendation_adherence else "",
        "exec_adh": execution_adherence.fingerprint if execution_adherence else "",
        "error": prediction_error.fingerprint if prediction_error else "",
        "status": status.value,
    }
    return RecommendationOutcomeReceipt(
        recommendation_outcome_receipt_id=new_outcome_receipt_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        recommendation_ref=decision.frontier_selection_ref,
        decision_ref=decision.investment_decision_id,
        approved_plan_ref=approved_plan_ref or decision.decided_portfolio_ref,
        recommendation_adherence_ref=(
            recommendation_adherence.recommendation_adherence_id
            if recommendation_adherence
            else None
        ),
        execution_adherence_ref=(
            execution_adherence.execution_adherence_id if execution_adherence else None
        ),
        realized_outcome_ref=(
            observation.decision_outcome_observation_id if observation else None
        ),
        prediction_evidence_ref=(
            prediction.prediction_evidence_id if prediction else None
        ),
        prediction_error_ref=(
            prediction_error.prediction_error_id if prediction_error else None
        ),
        simulation_evidence_handoff_ref=(
            prediction.simulation_evidence_handoff_ref if prediction else None
        ),
        status=status,
        limitations=tuple(dict.fromkeys(limitations)),
        receipt_fingerprint=metadata_fingerprint(payload),
        closed_at=closed_at,
        created_at=created,
    )
