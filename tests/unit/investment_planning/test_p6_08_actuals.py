"""P6-08 actual-spend context. Exposure does not rewrite actuals."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.investment_planning.enums import DeliveryHealthFlag
from app.investment_planning.exposure_actuals import (
    actual_spend_unchanged,
    high_spend_low_quality_flags,
)
from app.investment_planning.exposure_evidence import (
    compile_delivery_health_evidence,
    default_exposure_risk_policy,
)
from tests.unit.investment_planning.p6_08_support import (
    PROJECT,
    observation,
    spend_allocation,
)


def test_actual_spend_context_from_p6_03a() -> None:
    allocation = spend_allocation(amount="400.00")
    assert allocation.amount == Decimal("400.00")
    assert allocation.market_id
    assert allocation.channel_id


def test_exposure_evidence_does_not_change_actual_amount() -> None:
    original = spend_allocation(amount="250.00")
    unchanged = actual_spend_unchanged((original,))
    assert unchanged[0].amount == original.amount
    assert unchanged[0] is original


def test_high_spend_low_quality_flag_descriptive_only() -> None:
    now = datetime(2027, 2, 1, tzinfo=UTC)
    policy = default_exposure_risk_policy(created_at=now)
    rows = (observation(metric_id="VIEWABILITY_RATE", value="0.40"),)
    evidence = compile_delivery_health_evidence(
        project_id=PROJECT,
        period="FY2027Q1",
        observations=rows,
        policy=policy,
        created_at=now,
    )
    allocations = (spend_allocation(amount="400.00"),)
    flags = high_spend_low_quality_flags(
        allocations=allocations,
        observations=rows,
        evidence=evidence,
    )
    assert DeliveryHealthFlag.HIGH_SPEND_LOW_QUALITY in flags
    assert allocations[0].amount == Decimal("400.00")
    assert actual_spend_unchanged(allocations)[0].amount == Decimal("400.00")
