"""Metric validation — missing, zero, value, and invalid are distinct."""

from __future__ import annotations

import math
from typing import Any

from app.modeling.mmm.results.contracts import (
    IntervalEvidence,
    MetricAvailability,
    MetricValue,
)


def is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


def classify_scalar(value: Any) -> tuple[float | None, MetricAvailability]:
    if value is None:
        return None, MetricAvailability.NOT_AVAILABLE
    if not is_finite_number(value):
        return None, MetricAvailability.INVALID
    number = float(value)
    if number == 0.0:
        return 0.0, MetricAvailability.ZERO
    return number, MetricAvailability.VALUE


def validate_interval(
    lower: Any,
    upper: Any,
    *,
    confidence_level: float | None = None,
) -> IntervalEvidence:
    if lower is None and upper is None:
        return IntervalEvidence(
            availability=MetricAvailability.NOT_AVAILABLE,
            confidence_level=confidence_level,
        )
    if not is_finite_number(lower) or not is_finite_number(upper):
        return IntervalEvidence(
            availability=MetricAvailability.INVALID,
            confidence_level=confidence_level,
        )
    lo = float(lower)
    hi = float(upper)
    if lo > hi:
        return IntervalEvidence(
            availability=MetricAvailability.INVALID,
            confidence_level=confidence_level,
        )
    return IntervalEvidence(
        lower=lo,
        upper=hi,
        confidence_level=confidence_level,
        availability=MetricAvailability.VALUE,
    )


def metric_value(
    value: Any,
    *,
    lower: Any = None,
    upper: Any = None,
    confidence_level: float | None = None,
    unit: str | None = None,
    source_method: str | None = None,
    forced_availability: MetricAvailability | None = None,
) -> MetricValue:
    if forced_availability is MetricAvailability.NOT_AVAILABLE:
        return MetricValue(
            value=None,
            availability=MetricAvailability.NOT_AVAILABLE,
            unit=unit,
            source_method=source_method,
        )
    if forced_availability is MetricAvailability.INVALID:
        return MetricValue(
            value=None,
            availability=MetricAvailability.INVALID,
            unit=unit,
            source_method=source_method,
        )
    number, availability = classify_scalar(value)
    interval = None
    if lower is not None or upper is not None:
        interval = validate_interval(lower, upper, confidence_level=confidence_level)
        if interval.availability is MetricAvailability.INVALID and availability is MetricAvailability.VALUE:
            # Keep point estimate but surface interval invalidity separately.
            pass
    return MetricValue(
        value=number,
        availability=availability,
        interval=interval,
        unit=unit,
        source_method=source_method,
    )


def channel_availability(*metrics: MetricValue) -> MetricAvailability:
    if any(item.availability is MetricAvailability.INVALID for item in metrics):
        return MetricAvailability.INVALID
    if any(
        item.availability in {MetricAvailability.VALUE, MetricAvailability.ZERO} for item in metrics
    ):
        return MetricAvailability.VALUE
    return MetricAvailability.NOT_AVAILABLE
