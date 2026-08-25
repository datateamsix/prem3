"""Dedicated MMM modeling state machine. Does not replace frozen MODEL_READY."""

from __future__ import annotations

from enum import StrEnum

from app.modeling.common.errors import IllegalModelingTransitionError


class MMMModelingStage(StrEnum):
    MODEL_READY = "MODEL_READY"
    DESIGNING_MODEL = "DESIGNING_MODEL"
    AWAITING_ASSUMPTION_DECISIONS = "AWAITING_ASSUMPTION_DECISIONS"
    CONFIGURING_MODEL = "CONFIGURING_MODEL"
    PRIOR_VALIDATION = "PRIOR_VALIDATION"
    READY_TO_FIT = "READY_TO_FIT"
    AWAITING_FIT_APPROVAL = "AWAITING_FIT_APPROVAL"
    FITTING_MODEL = "FITTING_MODEL"
    EVALUATING_MODEL = "EVALUATING_MODEL"
    AWAITING_MODEL_REVIEW = "AWAITING_MODEL_REVIEW"
    ITERATION_REQUIRED = "ITERATION_REQUIRED"
    ITERATING_MODEL = "ITERATING_MODEL"
    MODEL_ACCEPTED = "MODEL_ACCEPTED"
    INTERPRETING_MODEL = "INTERPRETING_MODEL"
    HANDOFF_READY = "HANDOFF_READY"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


TRACK_PROJECTED_STAGES = frozenset(
    {
        MMMModelingStage.MODEL_READY,
        MMMModelingStage.DESIGNING_MODEL,
        MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS,
        MMMModelingStage.READY_TO_FIT,
        MMMModelingStage.FITTING_MODEL,
        MMMModelingStage.AWAITING_MODEL_REVIEW,
        MMMModelingStage.ITERATION_REQUIRED,
        MMMModelingStage.MODEL_ACCEPTED,
    }
)

_LEGAL: dict[MMMModelingStage, frozenset[MMMModelingStage]] = {
    MMMModelingStage.MODEL_READY: frozenset(
        {MMMModelingStage.DESIGNING_MODEL, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.DESIGNING_MODEL: frozenset(
        {MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS: frozenset(
        {MMMModelingStage.CONFIGURING_MODEL, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.CONFIGURING_MODEL: frozenset(
        {
            MMMModelingStage.PRIOR_VALIDATION,
            MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.PRIOR_VALIDATION: frozenset(
        {MMMModelingStage.READY_TO_FIT, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.READY_TO_FIT: frozenset(
        {MMMModelingStage.AWAITING_FIT_APPROVAL, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.AWAITING_FIT_APPROVAL: frozenset(
        {
            MMMModelingStage.FITTING_MODEL,
            MMMModelingStage.ITERATION_REQUIRED,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.FITTING_MODEL: frozenset(
        {
            MMMModelingStage.EVALUATING_MODEL,
            MMMModelingStage.ITERATION_REQUIRED,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.EVALUATING_MODEL: frozenset(
        {MMMModelingStage.AWAITING_MODEL_REVIEW, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.AWAITING_MODEL_REVIEW: frozenset(
        {
            MMMModelingStage.ITERATING_MODEL,
            MMMModelingStage.MODEL_ACCEPTED,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.ITERATION_REQUIRED: frozenset(
        {MMMModelingStage.DESIGNING_MODEL, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.ITERATING_MODEL: frozenset(
        {
            MMMModelingStage.DESIGNING_MODEL,
            MMMModelingStage.CONFIGURING_MODEL,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.MODEL_ACCEPTED: frozenset(
        {
            MMMModelingStage.INTERPRETING_MODEL,
            MMMModelingStage.HANDOFF_READY,
            MMMModelingStage.COMPLETE,
            MMMModelingStage.FAILED,
        }
    ),
    MMMModelingStage.INTERPRETING_MODEL: frozenset(
        {MMMModelingStage.HANDOFF_READY, MMMModelingStage.COMPLETE, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.HANDOFF_READY: frozenset(
        {MMMModelingStage.COMPLETE, MMMModelingStage.FAILED}
    ),
    MMMModelingStage.COMPLETE: frozenset(),
    MMMModelingStage.FAILED: frozenset(),
}


def assert_legal_modeling_transition(
    current: MMMModelingStage, nxt: MMMModelingStage
) -> None:
    allowed = _LEGAL[current]
    if nxt not in allowed:
        raise IllegalModelingTransitionError(
            f"Illegal modeling transition {current.value} -> {nxt.value}"
        )


def projected_track_state(stage: MMMModelingStage) -> str:
    if stage in TRACK_PROJECTED_STAGES:
        return stage.value
    if stage in {
        MMMModelingStage.CONFIGURING_MODEL,
        MMMModelingStage.PRIOR_VALIDATION,
        MMMModelingStage.AWAITING_FIT_APPROVAL,
    }:
        return MMMModelingStage.READY_TO_FIT.value
    if stage in {MMMModelingStage.EVALUATING_MODEL}:
        return MMMModelingStage.AWAITING_MODEL_REVIEW.value
    if stage in {
        MMMModelingStage.ITERATING_MODEL,
        MMMModelingStage.INTERPRETING_MODEL,
        MMMModelingStage.HANDOFF_READY,
        MMMModelingStage.COMPLETE,
    }:
        return (
            MMMModelingStage.MODEL_ACCEPTED.value
            if stage is not MMMModelingStage.ITERATING_MODEL
            else MMMModelingStage.DESIGNING_MODEL.value
        )
    if stage is MMMModelingStage.FAILED:
        return MMMModelingStage.FAILED.value
    return stage.value
