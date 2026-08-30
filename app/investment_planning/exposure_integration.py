"""P6-08 feeds into existing P6-07 contracts. Does not mutate constraint families."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.assumptions import pin_assumptions
from app.investment_optimization.constraints import constraint_set_fingerprint
from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
)
from app.investment_planning.enums import ExposureOptimizationRole
from app.investment_planning.exposure_guardrails import ExposureGuardrailQualificationReceipt

MODEL_INPUT_LIMITATION = "EXPOSURE_MODEL_INPUT_PINNED"


def attach_qualified_exposure_guardrails(
    constraint_set: OptimizationConstraintSet,
    receipts: tuple[ExposureGuardrailQualificationReceipt, ...],
) -> OptimizationConstraintSet:
    """Attach Role B IDs after qualification. Client POST still goes through pin_constraint_set."""
    qualified = tuple(
        item.guardrail_id
        for item in receipts
        if item.assigned_role is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
        and item.role_supported
        and item.spend_quality_relationship
    )
    if not qualified:
        return constraint_set
    updated = constraint_set.model_copy(
        update={"exposure_guardrails": qualified, "fingerprint": ""}
    )
    return updated.model_copy(update={"fingerprint": constraint_set_fingerprint(updated)})


def attach_model_input_to_assumptions(
    assumptions: FutureScenarioAssumptions,
    receipts: tuple[ExposureGuardrailQualificationReceipt, ...],
    *,
    created_at: datetime,
) -> FutureScenarioAssumptions:
    """Attach Role A qualification refs to FutureScenarioAssumptions.source_refs."""
    refs = tuple(
        item.qualification_id
        for item in receipts
        if item.assigned_role is ExposureOptimizationRole.MODEL_INPUT
        and item.role_supported
        and item.model_input_supported
    )
    if not refs:
        return assumptions
    limitations = assumptions.limitations
    if MODEL_INPUT_LIMITATION not in limitations:
        limitations = limitations + (MODEL_INPUT_LIMITATION,)
    updated = assumptions.model_copy(
        update={
            "source_refs": assumptions.source_refs + refs,
            "limitations": limitations,
        }
    )
    return pin_assumptions(updated, created_at=created_at)
