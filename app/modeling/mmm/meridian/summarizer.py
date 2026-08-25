"""Official Summarizer adapter. HTML is presentation; typed values are authority."""

from __future__ import annotations

import json
from typing import Any

from app.modeling.mmm.contracts import ResultsSummary


def _scalarize(value: Any) -> Any:
    """Firestore rejects nested arrays; keep maps JSON-safe."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _scalarize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), default=str)
    return str(value)


def _metric_map(value: Any) -> dict[str, Any]:
    """Coerce Analyzer outputs into a Firestore-safe JSON object."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): _scalarize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return {"json": json.dumps(list(value), default=str)}
    return {"value": _scalarize(value)}


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
