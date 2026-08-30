"""Join P6-03A actual spend as execution context. Descriptive flags only."""

from __future__ import annotations

from decimal import Decimal

from app.investment_planning.contracts import ActualSpendAllocation
from app.investment_planning.enums import DeliveryHealthFlag
from app.investment_planning.exposure_evidence import DeliveryHealthEvidence
from app.investment_planning.exposure_observations import ExposureMetricObservation

QUALITY_FLAGS = frozenset(
    {
        DeliveryHealthFlag.LOW_VIEWABILITY,
        DeliveryHealthFlag.HIGH_IVT,
        DeliveryHealthFlag.LOW_IN_TARGET_RATE,
        DeliveryHealthFlag.LOW_UNIQUE_REACH,
        DeliveryHealthFlag.OVER_FREQUENCY,
    }
)


def actual_spend_unchanged(
    allocations: tuple[ActualSpendAllocation, ...],
) -> tuple[ActualSpendAllocation, ...]:
    """Exposure evidence must not rewrite actual-spend amounts."""
    return allocations


def high_spend_low_quality_flags(
    *,
    allocations: tuple[ActualSpendAllocation, ...],
    observations: tuple[ExposureMetricObservation, ...],
    evidence: DeliveryHealthEvidence,
    spend_threshold: Decimal = Decimal("100.00"),
) -> tuple[DeliveryHealthFlag, ...]:
    """Descriptive only. Does not create optimizer constraints or change amounts."""
    del observations
    weak = bool(QUALITY_FLAGS.intersection(evidence.flags))
    heavy = any(
        item.amount is not None and item.amount >= spend_threshold and not item.missing
        for item in allocations
    )
    if weak and heavy:
        return (DeliveryHealthFlag.HIGH_SPEND_LOW_QUALITY,)
    return ()
