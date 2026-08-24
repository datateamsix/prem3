"""Official ModelReviewer adapter. Does not reimplement health checks."""

from __future__ import annotations

from app.modeling.mmm.contracts import (
    MeridianModelHealthReceipt,
    OfficialCheckResult,
    OfficialHealthStatus,
)


def interpret_reviewer_results(
    *,
    model_version_id: str,
    fit_run_id: str,
    meridian_version: str,
    results: tuple[OfficialCheckResult, ...],
    health_html_ref: str | None = None,
    overall_health_score: float | None = None,
) -> MeridianModelHealthReceipt:
    blocking = sum(1 for item in results if item.status is OfficialHealthStatus.FAIL)
    review = sum(1 for item in results if item.status is OfficialHealthStatus.REVIEW)
    return MeridianModelHealthReceipt(
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        reviewer_version="meridian.model.reviewer.ModelReviewer",
        meridian_version=meridian_version,
        overall_health_score=overall_health_score,
        check_results=results,
        blocking_fail_count=blocking,
        review_count=review,
        health_html_ref=health_html_ref,
    )
