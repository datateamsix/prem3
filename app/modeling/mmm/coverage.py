"""Measurement Cycle is decision context. The MMM model window is coverage-bound."""

from __future__ import annotations

from app.modeling.common.errors import InputContractMismatchError, StaleApprovalError
from app.modeling.mmm.contracts import FitApproval, ModelPlan, ModelReadyCoverage

MUSIC_CENTER_MODEL_READY_COVERAGE = ModelReadyCoverage(
    earliest_time="2024-01-01",
    latest_time="2026-06-29",
    n_times=131,
    n_geos=4,
    n_treatments=4,
    n_controls=3,
    geos=("CA", "FL", "NY", "TX"),
    source="datasets/music_center/dataset_a/truth/expected_model_ready_weekly.csv",
    shared_usable_historical_coverage="2024-01-01/2026-06-29",
    channel_limiting_coverage={
        "paid_search": "2024-01-01/2026-06-29",
        "shopping": "2024-01-01/2026-06-29",
        "paid_social": "2024-01-01/2026-06-29",
        "organic_sessions": "2024-01-01/2026-06-29",
    },
)


def candidate_window_from_coverage(coverage: ModelReadyCoverage) -> tuple[str, str]:
    """Select the verified shared usable history. Never copy Measurement Cycle dates."""
    return coverage.earliest_time, coverage.latest_time


def assert_model_window_inside_coverage(
    *,
    model_window_start: str,
    model_window_end: str,
    coverage: ModelReadyCoverage,
) -> None:
    if model_window_start > model_window_end:
        raise InputContractMismatchError("Model window start must not follow end.")
    if (
        model_window_start < coverage.earliest_time
        or model_window_end > coverage.latest_time
    ):
        raise InputContractMismatchError(
            "Model window is outside verified ModelReady coverage."
        )


def assert_cycle_does_not_define_window(
    *,
    cycle_start: str | None,
    cycle_end: str | None,
    model_window_start: str,
    model_window_end: str,
    coverage: ModelReadyCoverage | None = None,
) -> None:
    """A Measurement Cycle date range is not an implicit MMM model window."""
    if cycle_start is None or cycle_end is None:
        return
    if (model_window_start, model_window_end) != (cycle_start, cycle_end):
        return
    if coverage is None:
        raise InputContractMismatchError(
            "Measurement Cycle dates must not default the MMM model window."
        )
    if cycle_start < coverage.earliest_time or cycle_end > coverage.latest_time:
        raise InputContractMismatchError(
            "Measurement Cycle dates must not default the MMM model window."
        )


def assert_window_bound_by_model_decision(plan: ModelPlan, *, approved: bool) -> None:
    if not approved:
        raise InputContractMismatchError(
            "Model window requires an explicit MODEL_WINDOW decision."
        )
    if not plan.model_window_start or not plan.model_window_end:
        raise InputContractMismatchError("Model window is missing from the ModelPlan.")


def assert_window_change_invalidates_approval(
    *,
    plan: ModelPlan,
    approval: FitApproval | None,
) -> None:
    if approval is None:
        return
    if approval.model_plan_fingerprint != plan.fingerprint:
        raise StaleApprovalError("Changed model window invalidates fit approval.")
