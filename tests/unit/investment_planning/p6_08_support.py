"""Shared P6-08 test helpers. Not production."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.investment_optimization.contracts import ModelConsumptionContract, ModelConsumptionVariable
from app.investment_optimization.enums import (
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
)
from app.investment_planning.contracts import ActualSpendAllocation
from app.investment_planning.enums import ExposureFreshnessState, ExposureQualityStatus
from app.investment_planning.exposure_metrics import get_metric_definition
from app.investment_planning.exposure_observations import (
    ExposureMetricObservation,
    observation_fingerprint,
)
from app.investment_planning.ids import new_actuals_source_id
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A

NOW = datetime(2027, 2, 1, tzinfo=UTC)
PROJECT = "wsp_cccccccccccccccccccc"
CHANNEL = "search_paid"


def observation(
    *,
    metric_id: str,
    value: str,
    market_id: str = MARKET_A,
    channel_id: str = CHANNEL,
    campaign_id: str | None = None,
    provider_id: str | None = "google_ads",
    freshness: ExposureFreshnessState = ExposureFreshnessState.FRESH,
    period: str = "FY2027Q1",
) -> ExposureMetricObservation:
    definition = get_metric_definition(metric_id)
    source_ref = "dfsrc_exposureaaaaaaaa"
    fingerprint = observation_fingerprint(
        project_id=PROJECT,
        period=period,
        market_id=market_id,
        channel_id=channel_id,
        metric_id=metric_id,
        source_ref=source_ref,
        as_of_time=NOW,
    )
    return ExposureMetricObservation(
        project_id=PROJECT,
        period=period,
        market_id=market_id,
        channel_id=channel_id,
        campaign_id=campaign_id,
        provider_id=provider_id,
        metric_id=metric_id,
        value=Decimal(value),
        unit=definition.unit,
        source_ref=source_ref,
        as_of_time=NOW,
        freshness=freshness,
        quality_status=ExposureQualityStatus.PASS,
        fingerprint=fingerprint,
    )


def rf_consumption() -> ModelConsumptionContract:
    return ModelConsumptionContract.model_construct(
        variables=(
            ModelConsumptionVariable.model_construct(
                model_variable_id="rf_youtube",
                model_variable_name="YouTube RF",
                variable_role=ModelVariableRole.MEDIA_SPEND,
                eligibility=ModelVariableOptimizationEligibility.OPTIMIZABLE,
            ),
        )
    )


def spend_allocation(*, amount: str = "400.00") -> ActualSpendAllocation:
    return ActualSpendAllocation(
        fiscal_year=2027,
        quarter=1,
        market_id=MARKET_A,
        channel_id=CHANNEL,
        amount=Decimal(amount),
        currency="USD",
        source_ref=new_actuals_source_id(),
        missing=False,
    )
