"""LOCAL_ONLY learning candidates. No silent policy mutation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    ExperienceBoundary,
    LearningCandidateType,
    OutcomeLifecycleStatus,
)
from app.investment_optimization.errors import (
    LearningBoundaryViolationError,
    LearningReceiptNotReadyError,
)
from app.investment_optimization.ids import new_learning_receipt_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import (
    DecisionOutcomeLearningReceipt,
    PredictionErrorSummary,
    RecommendationAdherence,
    RecommendationOutcomeReceipt,
)


def choose_learning_candidate(
    *,
    receipt: RecommendationOutcomeReceipt,
    adherence: RecommendationAdherence | None,
    error: PredictionErrorSummary | None,
) -> LearningCandidateType:
    if receipt.status is not OutcomeLifecycleStatus.CLOSED:
        return LearningCandidateType.INSUFFICIENT_EVIDENCE
    if "OUTCOME_NOT_OBSERVED" in receipt.limitations:
        return LearningCandidateType.INSUFFICIENT_EVIDENCE
    if adherence is not None and adherence.l1_distance > 0.0:
        return LearningCandidateType.CONSTRAINT_POLICY_REVIEW
    if error is not None and error.absolute_error is not None and error.absolute_error > 0.0:
        return LearningCandidateType.MODEL_CALIBRATION_REVIEW
    return LearningCandidateType.NO_ACTION


def emit_learning_receipt(
    *,
    project_id: str,
    receipt: RecommendationOutcomeReceipt,
    adherence: RecommendationAdherence | None = None,
    error: PredictionErrorSummary | None = None,
    experience_boundary: ExperienceBoundary = ExperienceBoundary.LOCAL_ONLY,
) -> DecisionOutcomeLearningReceipt:
    if experience_boundary is not ExperienceBoundary.LOCAL_ONLY:
        raise LearningBoundaryViolationError("P6-10 authorizes LOCAL_ONLY learning only.")
    if receipt.status is not OutcomeLifecycleStatus.CLOSED:
        raise LearningReceiptNotReadyError("Learning requires a closed outcome receipt.")
    candidate = choose_learning_candidate(receipt=receipt, adherence=adherence, error=error)
    created = datetime.now(UTC)
    evidence = tuple(
        ref
        for ref in (
            receipt.decision_ref,
            receipt.prediction_error_ref,
            receipt.recommendation_adherence_ref,
            receipt.execution_adherence_ref,
        )
        if ref
    )
    payload = {
        "receipt": receipt.receipt_fingerprint,
        "candidate": candidate.value,
        "boundary": experience_boundary.value,
    }
    return DecisionOutcomeLearningReceipt(
        learning_receipt_id=new_learning_receipt_id(),
        project_id=project_id,
        recommendation_outcome_receipt_ref=receipt.recommendation_outcome_receipt_id,
        issue_type=candidate.value,
        evidence_refs=evidence,
        prediction_error_class=error.error_class if error else None,
        adherence_class=adherence.adherence_class if adherence else None,
        learning_candidate_type=candidate,
        experience_boundary=experience_boundary,
        fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )
