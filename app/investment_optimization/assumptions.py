"""Pin and fingerprint future scenario assumptions. Amounts stay transient."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    UnitValueAssumption,
)
from app.investment_optimization.enums import AssumptionAuthority, AssumptionStatus
from app.investment_optimization.errors import (
    FinancialValueAssumptionRequiredError,
    FlightingAssumptionInvalidError,
    FutureCostAssumptionInvalidError,
)
from app.investment_planning.fingerprint import metadata_fingerprint


def _unit_value_body(item: UnitValueAssumption) -> dict[str, str]:
    return {
        "ref_id": item.ref_id,
        "source": item.source,
        "scope": item.scope,
        "currency": item.currency,
        "time_horizon": item.time_horizon,
        "freshness": item.freshness,
        "value": format(item.value, "f"),
    }


def assumption_fingerprint(assumptions: FutureScenarioAssumptions) -> str:
    costs = [
        {
            "ref_id": item.ref_id,
            "kind": item.kind.value,
            "unit": item.unit,
            "currency": item.currency,
            "period": item.period,
            "market_id": item.market_id or "",
            "channel_id": item.channel_id,
            "source": item.source,
            "freshness": item.freshness,
            "value": format(item.value, "f"),
        }
        for item in assumptions.cost_per_media_unit
    ]
    flighting = [
        {
            "ref_id": item.ref_id,
            "market_id": item.market_id or "",
            "channel_id": item.channel_id,
            "period": item.period,
            "weight": format(item.weight, "f"),
            "source": item.source,
            "authority": item.authority.value,
        }
        for item in assumptions.flighting
    ]
    revenue = assumptions.revenue_per_kpi
    revenue_body: dict[str, str] | str | None
    if isinstance(revenue, UnitValueAssumption):
        revenue_body = _unit_value_body(revenue)
    elif isinstance(revenue, Decimal):
        revenue_body = format(revenue, "f")
    else:
        revenue_body = None
    margin = None if assumptions.contribution_margin is None else _unit_value_body(
        assumptions.contribution_margin
    )
    return metadata_fingerprint(
        {
            "assumption_set_id": assumptions.assumption_set_id,
            "project_id": assumptions.project_id or "",
            "period_start": assumptions.period_start or "",
            "period_end": assumptions.period_end or "",
            "costs": costs,
            "cpm_pairs": [
                (channel, format(value, "f"))
                for channel, value in assumptions.future_cpm_by_channel
            ],
            "flighting": flighting,
            "revenue_per_kpi": revenue_body,
            "revenue_per_kpi_ref": assumptions.revenue_per_kpi_ref or "",
            "contribution_margin": margin,
            "contribution_margin_ref": assumptions.contribution_margin_ref or "",
            "source_refs": list(assumptions.source_refs),
            "authority": assumptions.authority.value,
            "status": assumptions.status.value,
        }
    )


def pin_assumptions(
    assumptions: FutureScenarioAssumptions, *, created_at: datetime | None = None
) -> FutureScenarioAssumptions:
    validate_future_cost_assumptions(assumptions)
    validate_flighting_assumptions(assumptions)
    pinned = assumptions.model_copy(
        update={
            "status": AssumptionStatus.PINNED,
            "created_at": created_at or assumptions.created_at,
            "cost_per_media_unit_refs": tuple(
                item.ref_id for item in assumptions.cost_per_media_unit
            ),
            "flighting_refs": tuple(item.ref_id for item in assumptions.flighting),
        }
    )
    return pinned.model_copy(update={"fingerprint": assumption_fingerprint(pinned)})


def validate_future_cost_assumptions(assumptions: FutureScenarioAssumptions) -> None:
    for item in assumptions.cost_per_media_unit:
        if item.value <= 0:
            raise FutureCostAssumptionInvalidError("Future media-unit cost must be positive.")
        if not item.unit or not item.currency or not item.period or not item.channel_id:
            raise FutureCostAssumptionInvalidError(
                "Future media-unit cost must pin unit, currency, period, and channel."
            )
        if not item.source or not item.freshness:
            raise FutureCostAssumptionInvalidError(
                "Future media-unit cost must pin source and freshness."
            )
    for channel_id, value in assumptions.future_cpm_by_channel:
        if not channel_id or value <= 0:
            raise FutureCostAssumptionInvalidError("Future CPM assumptions must be pinned.")


def validate_flighting_assumptions(assumptions: FutureScenarioAssumptions) -> None:
    by_channel: dict[str, Decimal] = {}
    for item in assumptions.flighting:
        if item.weight < 0:
            raise FlightingAssumptionInvalidError("Flighting weights cannot be negative.")
        if not item.channel_id or not item.period or not item.source:
            raise FlightingAssumptionInvalidError("Flighting must pin channel, period, and source.")
        key = f"{item.channel_id}:{item.period}"
        by_channel[key] = by_channel.get(key, Decimal("0")) + item.weight
    if assumptions.period_start and assumptions.period_end:
        if assumptions.period_start > assumptions.period_end:
            raise FlightingAssumptionInvalidError(
                "Assumption period_start must precede period_end."
            )


def governed_unit_value(assumptions: FutureScenarioAssumptions) -> UnitValueAssumption | None:
    revenue = assumptions.revenue_per_kpi
    if isinstance(revenue, UnitValueAssumption):
        if not revenue.source or not revenue.currency or not revenue.freshness:
            raise FinancialValueAssumptionRequiredError(
                "Revenue per KPI requires a governed source, currency, and freshness."
            )
        return revenue
    if assumptions.contribution_margin is not None:
        margin = assumptions.contribution_margin
        if not margin.source or not margin.currency or not margin.freshness:
            raise FinancialValueAssumptionRequiredError(
                "Contribution margin requires a governed source, currency, and freshness."
            )
        return margin
    return None


def require_financial_value(assumptions: FutureScenarioAssumptions) -> UnitValueAssumption:
    value = governed_unit_value(assumptions)
    if value is None:
        raise FinancialValueAssumptionRequiredError(
            "Financial-value optimization requires governed revenue_per_kpi or contribution margin."
        )
    return value


def has_governed_financial_value(assumptions: FutureScenarioAssumptions | None) -> bool:
    if assumptions is None:
        return False
    try:
        return governed_unit_value(assumptions) is not None
    except FinancialValueAssumptionRequiredError:
        return False


def default_empty_assumptions(
    *, assumption_set_id: str, project_id: str | None = None
) -> FutureScenarioAssumptions:
    empty = FutureScenarioAssumptions(
        assumption_set_id=assumption_set_id,
        project_id=project_id,
        authority=AssumptionAuthority.SYSTEM_DERIVED,
        status=AssumptionStatus.PINNED,
    )
    return empty.model_copy(update={"fingerprint": assumption_fingerprint(empty)})
