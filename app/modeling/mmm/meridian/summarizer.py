"""Official Summarizer adapter. HTML is presentation; typed values are authority."""

from __future__ import annotations

from typing import Any

from app.modeling.mmm.contracts import ResultsSummary


def structured_results(
    *,
    html_ref: str | None,
    requested_date_range: str | None,
    effective_date_range: str | None,
    values: dict[str, Any] | None = None,
) -> ResultsSummary:
    payload = values or {}
    return ResultsSummary(
        html_ref=html_ref,
        requested_date_range=requested_date_range,
        effective_date_range=effective_date_range or requested_date_range,
        model_fit=dict(payload.get("model_fit") or {}),
        incremental_outcomes=dict(payload.get("incremental_outcomes") or {}),
        channel_contribution=dict(payload.get("channel_contribution") or {}),
        roi=dict(payload.get("roi") or {}),
        mroi=dict(payload.get("mroi") or {}),
        response_curve_metadata=dict(payload.get("response_curve_metadata") or {}),
        baseline=dict(payload.get("baseline") or {}),
        adstock_saturation=dict(payload.get("adstock_saturation") or {}),
    )
