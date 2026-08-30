"""Consume P6-08 ExposureRiskHandoff without promoting Role C to a hard constraint."""

from __future__ import annotations

from app.investment_planning.enums import ExposureOptimizationRole
from app.investment_planning.exposure_guardrails import ExposureGuardrailQualificationReceipt
from app.investment_planning.exposure_handoff import ExposureRiskHandoff


def exposure_limitations(
    handoff: ExposureRiskHandoff | None,
    *,
    qualifications: tuple[ExposureGuardrailQualificationReceipt, ...] = (),
) -> tuple[str, ...]:
    if handoff is None:
        return ("EXPOSURE_RISK_NOT_QUALIFIED", "MISSING_EXPOSURE_HANDOFF")
    notes: list[str] = []
    if handoff.freshness in {"MISSING", "REVIEW_REQUIRED"}:
        notes.append("EXPOSURE_COVERAGE_NOT_ZERO_RISK")
    if not handoff.exposure_risk_evidence_refs:
        notes.append("EXPOSURE_EVIDENCE_MISSING")
    if handoff.risk_flags:
        notes.append("EXPOSURE_RISK_FLAGS_PRESENT")
    for receipt in qualifications:
        if receipt.assigned_role is ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL:
            notes.append("EXPOSURE_ROLE_C_NOT_HARD_CONSTRAINT")
        if (
            receipt.assigned_role is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
            and not receipt.role_supported
        ):
            notes.append("EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED")
    notes.extend(handoff.limitations)
    return tuple(dict.fromkeys(notes))


def role_c_is_hard_constraint(
    qualifications: tuple[ExposureGuardrailQualificationReceipt, ...],
) -> bool:
    return any(
        receipt.assigned_role is ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
        and receipt.requested_role is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
        and receipt.role_supported
        for receipt in qualifications
    )
