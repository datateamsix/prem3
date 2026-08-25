"""Official Summarizer adapter. HTML is presentation; typed values are authority."""

from __future__ import annotations

from typing import Any

from app.modeling.mmm.contracts import ResultsSummary


def _metric_map(value: Any) -> dict[str, Any]:
    """Coerce Analyzer outputs into a JSON object. Meridian often returns lists."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        pairs = True
        mapped: dict[str, Any] = {}
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                mapped[str(item[0])] = item[1]
                continue
            pairs = False
            break
        if pairs and mapped:
            return mapped
        return {"values": value}
    return {"value": value}


def structured_results(
    *,
    html_ref: str | None,
    requested_date_range: str | None,
    effective_date_range: str | None,
    values: dict[str, Any] | None = None,
    html_sha256: str | None = None,
) -> ResultsSummary:
    payload = values or {}
    incremental = payload.get("incremental_outcomes")
    if incremental is None:
        incremental = payload.get("incremental_outcome")
    contribution = payload.get("channel_contribution")
    if contribution is None:
        contribution = payload.get("contribution")
    mroi = payload.get("mroi")
    if mroi is None:
        mroi = payload.get("marginal_roi")
    return ResultsSummary(
        html_ref=html_ref,
        html_sha256=html_sha256,
        requested_date_range=requested_date_range,
        effective_date_range=effective_date_range or requested_date_range,
        model_fit=_metric_map(payload.get("model_fit")),
        incremental_outcomes=_metric_map(incremental),
        channel_contribution=_metric_map(contribution),
        roi=_metric_map(payload.get("roi")),
        mroi=_metric_map(mroi),
        response_curve_metadata=_metric_map(payload.get("response_curve_metadata")),
        baseline=_metric_map(payload.get("baseline")),
        adstock_saturation=_metric_map(payload.get("adstock_saturation")),
    )
