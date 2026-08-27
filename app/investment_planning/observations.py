"""Deterministic portfolio observations. Findings, not recommendations."""

from __future__ import annotations

from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioEvidenceCoverage,
    PortfolioObservation,
)
from app.investment_planning.enums import (
    AmountKind,
    EvidenceCoverageStatus,
    ObservationSeverity,
    PortfolioCoverageState,
    PortfolioObservationType,
)
from app.investment_planning.ids import new_observation_id


def _amount(allocation: PortfolioAllocationView, kind: AmountKind) -> MoneyAmount | None:
    for amount in allocation.amounts:
        if amount.kind is kind:
            return amount
    return None


def emit_portfolio_observations(
    *,
    project_id: str,
    allocations: tuple[PortfolioAllocationView, ...],
    coverage: PortfolioEvidenceCoverage,
    snapshot_fingerprint: str | None,
    coverage_state: PortfolioCoverageState,
    actuals_error_code: str | None,
    stale_actuals: bool,
) -> tuple[PortfolioObservation, ...]:
    rows: list[PortfolioObservation] = []
    if actuals_error_code == "ACTUALS_SOURCE_NOT_CONFIGURED":
        rows.append(
            _observation(
                project_id=project_id,
                observation_type=PortfolioObservationType.MISSING_ACTUALS_SOURCE,
                severity=ObservationSeverity.REVIEW,
                message_key="actuals_source_not_configured",
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
    elif actuals_error_code == "ACTUALS_SOURCE_UNAVAILABLE":
        rows.append(
            _observation(
                project_id=project_id,
                observation_type=PortfolioObservationType.MISSING_ACTUALS_SOURCE,
                severity=ObservationSeverity.WARNING,
                message_key="actuals_source_unavailable",
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
    if stale_actuals:
        rows.append(
            _observation(
                project_id=project_id,
                observation_type=PortfolioObservationType.STALE_ACTUALS_SOURCE,
                severity=ObservationSeverity.REVIEW,
                message_key="actuals_source_stale",
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
    for allocation in allocations:
        approved = _amount(allocation, AmountKind.APPROVED)
        actual = _amount(allocation, AmountKind.ACTUAL)
        plan_known = (
            approved is not None and not approved.missing and approved.value is not None
        )
        actual_known = actual is not None and not actual.missing and actual.value is not None
        if plan_known and actual_known:
            assert approved is not None and actual is not None
            if actual.value > approved.value:
                rows.append(
                    _observation(
                        project_id=project_id,
                        observation_type=PortfolioObservationType.ACTUAL_EXCEEDS_PLAN,
                        severity=ObservationSeverity.WARNING,
                        message_key="actual_exceeds_plan",
                        snapshot_fingerprint=snapshot_fingerprint,
                        allocation=allocation,
                    )
                )
            elif actual.value < approved.value:
                rows.append(
                    _observation(
                        project_id=project_id,
                        observation_type=PortfolioObservationType.ACTUAL_BELOW_PLAN,
                        severity=ObservationSeverity.INFO,
                        message_key="actual_below_plan",
                        snapshot_fingerprint=snapshot_fingerprint,
                        allocation=allocation,
                    )
                )
        elif plan_known and (actual is None or actual.missing):
            if actuals_error_code is None:
                rows.append(
                    _observation(
                        project_id=project_id,
                        observation_type=PortfolioObservationType.PLAN_WITHOUT_ACTUALS,
                        severity=ObservationSeverity.REVIEW,
                        message_key="plan_cell_missing_actual",
                        snapshot_fingerprint=snapshot_fingerprint,
                        allocation=allocation,
                    )
                )
        elif actual_known and (approved is None or approved.missing):
            rows.append(
                _observation(
                    project_id=project_id,
                    observation_type=PortfolioObservationType.ACTUAL_WITHOUT_PLAN,
                    severity=ObservationSeverity.INFO,
                    message_key="actual_cell_without_plan",
                    snapshot_fingerprint=snapshot_fingerprint,
                    allocation=allocation,
                )
            )
    measurement_items = [
        item
        for item in coverage.items
        if item.category.value in {"MMM", "MTA", "EXPERIMENT", "BRAND", "EXPOSURE_INTEGRITY"}
    ]
    if not measurement_items:
        rows.append(
            _observation(
                project_id=project_id,
                observation_type=PortfolioObservationType.MEASUREMENT_COVERAGE_MISSING,
                severity=ObservationSeverity.REVIEW,
                message_key="measurement_coverage_missing",
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
    elif coverage.status is EvidenceCoverageStatus.PARTIAL:
        rows.append(
            _observation(
                project_id=project_id,
                observation_type=PortfolioObservationType.MEASUREMENT_COVERAGE_PARTIAL,
                severity=ObservationSeverity.INFO,
                message_key="measurement_coverage_partial",
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
    del coverage_state  # reserved for state-scoped observation policy
    return tuple(rows)


def _observation(
    *,
    project_id: str,
    observation_type: PortfolioObservationType,
    severity: ObservationSeverity,
    message_key: str,
    snapshot_fingerprint: str | None,
    allocation: PortfolioAllocationView | None = None,
) -> PortfolioObservation:
    return PortfolioObservation(
        observation_id=new_observation_id(),
        project_id=project_id,
        observation_type=observation_type,
        severity=severity,
        subject_market_id=None if allocation is None else allocation.market_id,
        subject_channel_id=None if allocation is None else allocation.channel_id,
        fiscal_year=None if allocation is None else allocation.fiscal_year,
        quarter=None if allocation is None else allocation.quarter,
        message_key=message_key,
        snapshot_fingerprint=snapshot_fingerprint,
        code=observation_type.value,
    )
