"""Deterministic portfolio aggregates. Never sum ratios."""

from __future__ import annotations

from app.modeling.mmm.results.contracts import (
    MetricAvailability,
    MetricValue,
    MMMChannelResult,
    MMMPortfolioSummary,
)
from app.modeling.mmm.results.validation import metric_value


def _usable(metric: MetricValue) -> bool:
    return metric.availability in {MetricAvailability.VALUE, MetricAvailability.ZERO}


def build_portfolio_summary(
    channels: tuple[MMMChannelResult, ...] | list[MMMChannelResult],
) -> MMMPortfolioSummary:
    spend_total = 0.0
    spend_ok = False
    outcome_total = 0.0
    outcome_ok = False
    for channel in channels:
        if _usable(channel.spend) and channel.spend.value is not None:
            spend_total += channel.spend.value
            spend_ok = True
        if _usable(channel.incremental_outcome) and channel.incremental_outcome.value is not None:
            outcome_total += channel.incremental_outcome.value
            outcome_ok = True

    total_spend = (
        metric_value(spend_total, source_method="deterministic.portfolio.total_spend")
        if spend_ok
        else MetricValue(availability=MetricAvailability.NOT_AVAILABLE)
    )
    modeled_incremental = (
        metric_value(
            outcome_total,
            source_method="deterministic.portfolio.modeled_incremental_outcome",
        )
        if outcome_ok
        else MetricValue(availability=MetricAvailability.NOT_AVAILABLE)
    )
    if (
        spend_ok
        and outcome_ok
        and total_spend.value is not None
        and total_spend.value > 0
        and modeled_incremental.value is not None
    ):
        portfolio_roi = metric_value(
            modeled_incremental.value / total_spend.value,
            source_method="deterministic.portfolio.portfolio_roi",
        )
    else:
        portfolio_roi = MetricValue(availability=MetricAvailability.NOT_AVAILABLE)

    return MMMPortfolioSummary(
        total_spend=total_spend,
        modeled_incremental_outcome=modeled_incremental,
        portfolio_roi=portfolio_roi,
    )
