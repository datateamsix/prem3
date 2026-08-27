"""P6-03 evidence coverage and deterministic observations."""

from __future__ import annotations

from decimal import Decimal
from inspect import signature

from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioSnapshotRef,
)
from app.investment_planning.coverage import (
    OPTIMIZATION_READY,
    assemble_evidence_coverage,
    coverage_payload_has_optimization_ready,
)
from app.investment_planning.enums import (
    AmountKind,
    EvidenceCoverageLabel,
    EvidenceCoverageScope,
    EvidenceCoverageStatus,
    ObservationSeverity,
    PortfolioBaselineKind,
    PortfolioCoverageState,
    PortfolioObservationType,
)
from app.investment_planning.observations import emit_portfolio_observations
from tests.unit.investment_planning.test_p6_00_architecture import _now
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A, _source


def _snapshot() -> PortfolioSnapshotRef:
    return PortfolioSnapshotRef(
        snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        workspace_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
        business_profile_snapshot_id="bps_dddddddddddddddddddd",
        fingerprint="fp_snap",
        created_at=_now(),
        created_by="user_music_center",
    )


def _cell(*, approved: str | None, actual: str | None) -> PortfolioAllocationView:
    amounts: list[MoneyAmount] = []
    if approved is None:
        amounts.append(
            MoneyAmount(kind=AmountKind.APPROVED, currency="USD", value=None, missing=True)
        )
    else:
        amounts.append(
            MoneyAmount(
                kind=AmountKind.APPROVED, currency="USD", value=Decimal(approved), missing=False
            )
        )
    if actual is None:
        amounts.append(
            MoneyAmount(kind=AmountKind.ACTUAL, currency="USD", value=None, missing=True)
        )
    else:
        amounts.append(
            MoneyAmount(
                kind=AmountKind.ACTUAL, currency="USD", value=Decimal(actual), missing=False
            )
        )
    return PortfolioAllocationView(
        fiscal_year=2027,
        quarter=1,
        market_id=MARKET_A,
        channel_id="search_paid",
        channel_registry_version=1,
        amounts=tuple(amounts),
    )


def test_coverage_uses_explicit_scope() -> None:
    coverage = assemble_evidence_coverage(
        snapshot=_snapshot(),
        actuals_source=_source(),
        accepted_mmm_result_ref="mmm_accepted_1",
        mta_result_ref="mta_run_1",
    )
    assert coverage.scope is EvidenceCoverageScope.PROJECT
    scopes = {item.category: item.scope for item in coverage.items}
    assert scopes[EvidenceCoverageLabel.DATA_FOUNDATION] is EvidenceCoverageScope.PROJECT
    assert scopes[EvidenceCoverageLabel.MMM] is EvidenceCoverageScope.PROJECT


def test_missing_evidence_not_zero() -> None:
    coverage = assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=None)
    assert coverage.status is EvidenceCoverageStatus.MISSING
    assert coverage.accepted_mmm is False
    assert coverage.items == ()


def test_mta_coverage_not_labeled_causal() -> None:
    coverage = assemble_evidence_coverage(
        snapshot=_snapshot(),
        actuals_source=None,
        mta_result_ref="mta_run_1",
        accepted_mmm_result_ref="mmm_accepted_1",
    )
    mta = next(item for item in coverage.items if item.category is EvidenceCoverageLabel.MTA)
    mmm = next(item for item in coverage.items if item.category is EvidenceCoverageLabel.MMM)
    assert mta.causal is False
    assert mmm.causal is True


def test_accepted_mmm_coverage_distinct_from_mta() -> None:
    coverage = assemble_evidence_coverage(
        snapshot=_snapshot(),
        actuals_source=None,
        accepted_mmm_result_ref="mmm_accepted_1",
        mta_result_ref="mta_run_1",
    )
    assert coverage.accepted_mmm is True
    assert coverage.mta_available is True
    assert EvidenceCoverageLabel.MMM in coverage.labels
    assert EvidenceCoverageLabel.MTA in coverage.labels


def test_coverage_does_not_emit_optimization_ready() -> None:
    coverage = assemble_evidence_coverage(
        snapshot=_snapshot(),
        actuals_source=_source(),
        accepted_mmm_result_ref="mmm_accepted_1",
        mta_result_ref="mta_run_1",
    )
    assert coverage_payload_has_optimization_ready(coverage) is False
    assert OPTIMIZATION_READY not in str(coverage.model_dump())


def test_actual_exceeds_plan_observation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual="140.00"),),
        coverage=assemble_evidence_coverage(
            snapshot=_snapshot(), actuals_source=_source(), accepted_mmm_result_ref="mmm_1"
        ),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_AND_ACTUALS,
        actuals_error_code=None,
        stale_actuals=False,
    )
    types = {item.observation_type for item in observations}
    assert PortfolioObservationType.ACTUAL_EXCEEDS_PLAN in types
    exceeds = next(
        item
        for item in observations
        if item.observation_type is PortfolioObservationType.ACTUAL_EXCEEDS_PLAN
    )
    assert exceeds.severity is ObservationSeverity.WARNING
    assert exceeds.snapshot_fingerprint == "fp_snap"
    assert "amount" not in exceeds.model_dump()


def test_actual_without_plan_observation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved=None, actual="25.00"),),
        coverage=assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=_source()),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.ACTUALS_ONLY,
        actuals_error_code=None,
        stale_actuals=False,
    )
    assert any(
        item.observation_type is PortfolioObservationType.ACTUAL_WITHOUT_PLAN
        for item in observations
    )


def test_plan_without_actual_observation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual=None),),
        coverage=assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=_source()),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_AND_ACTUALS,
        actuals_error_code=None,
        stale_actuals=False,
    )
    assert any(
        item.observation_type is PortfolioObservationType.PLAN_WITHOUT_ACTUALS
        for item in observations
    )
    missing_source = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual=None),),
        coverage=assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=None),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_ONLY,
        actuals_error_code="ACTUALS_SOURCE_NOT_CONFIGURED",
        stale_actuals=False,
    )
    types = {item.observation_type for item in missing_source}
    assert PortfolioObservationType.MISSING_ACTUALS_SOURCE in types
    assert PortfolioObservationType.PLAN_WITHOUT_ACTUALS not in types


def test_stale_actuals_observation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual="40.00"),),
        coverage=assemble_evidence_coverage(
            snapshot=_snapshot(), actuals_source=_source(), stale_actuals=True
        ),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_AND_ACTUALS,
        actuals_error_code=None,
        stale_actuals=True,
    )
    assert any(
        item.observation_type is PortfolioObservationType.STALE_ACTUALS_SOURCE
        for item in observations
    )


def test_missing_measurement_coverage_observation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(),
        coverage=assemble_evidence_coverage(snapshot=_snapshot(), actuals_source=None),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.NEITHER,
        actuals_error_code="ACTUALS_SOURCE_NOT_CONFIGURED",
        stale_actuals=False,
    )
    assert any(
        item.observation_type is PortfolioObservationType.MEASUREMENT_COVERAGE_MISSING
        for item in observations
    )


def test_observation_not_recommendation() -> None:
    observations = emit_portfolio_observations(
        project_id="wsp_cccccccccccccccccccc",
        allocations=(_cell(approved="100.00", actual="140.00"),),
        coverage=assemble_evidence_coverage(
            snapshot=_snapshot(), actuals_source=_source(), accepted_mmm_result_ref="mmm_1"
        ),
        snapshot_fingerprint="fp_snap",
        coverage_state=PortfolioCoverageState.PLAN_AND_ACTUALS,
        actuals_error_code=None,
        stale_actuals=False,
    )
    dumped = str([item.model_dump() for item in observations])
    assert "RECOMMENDED" not in dumped
    assert AmountKind.RECOMMENDED.value not in dumped


def test_observation_does_not_mutate_plan() -> None:

    params = signature(emit_portfolio_observations).parameters
    assert "plan" not in params
    assert "investment_plan" not in params
