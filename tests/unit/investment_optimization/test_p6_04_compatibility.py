"""P6-04 period/currency/spend compatibility and portfolio coverage states."""

from __future__ import annotations

from app.investment_optimization.compatibility import (
    currency_issues,
    period_issues,
    spend_semantics_issues,
)
from app.investment_optimization.coverage import assemble_optimization_evidence_coverage
from app.investment_optimization.enums import (
    OptimizationIssueCode,
    OptimizationReadinessStatus,
    SpendSemantics,
)
from app.investment_optimization.mapping import build_portfolio_model_mapping
from app.investment_optimization.readiness import (
    build_optimization_input_contract,
    evaluate_readiness,
)
from app.investment_planning.enums import (
    PortfolioBaselineKind,
    PortfolioCoverageState,
    PortfolioObservationType,
)
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    complete_contract,
    now,
    observation,
    portfolio_view,
    snapshot,
    spend_variable,
)


def _mapping(view, contract):
    return build_portfolio_model_mapping(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=view.snapshot_id,
        baseline_kind=view.baseline_kind,
        view=view,
        contract=contract,
        created_at=now(),
        created_by="user_music_center",
    )


def _ready(view, contract, *, state=PortfolioCoverageState.PLAN_ONLY, snap=None, extra=()):
    mapping = _mapping(view, contract)
    snap = snap or snapshot()
    coverage = assemble_optimization_evidence_coverage(mapping=mapping, contract=contract)
    input_contract = build_optimization_input_contract(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot=snap,
        view=view,
        mapping=mapping,
        contract=contract,
        created_at=now(),
        issues=(),
    )
    return evaluate_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        coverage_state=state,
        snapshot=snap,
        view=view,
        contract=contract,
        mapping=mapping,
        coverage=coverage,
        input_contract=input_contract,
        created_at=now(),
        extra_issues=extra,
    )


def test_period_compatible() -> None:
    contract = complete_contract(window=("2024-01-01", "2026-12-31"), future_horizon_allowed=True)
    assert period_issues(view=portfolio_view(), contract=contract) == ()


def test_period_incompatible_review_required() -> None:
    contract = complete_contract(window=("2020-01-01", "2020-12-31"), future_horizon_allowed=False)
    issues = period_issues(view=portfolio_view(), contract=contract)
    assert issues[0].code is OptimizationIssueCode.PERIOD_COMPATIBILITY_REVIEW_REQUIRED


def test_currency_match() -> None:
    assert currency_issues(view=portfolio_view(), contract=complete_contract()) == ()


def test_currency_mismatch_review_required() -> None:
    issues = currency_issues(view=portfolio_view(currency="EUR"), contract=complete_contract())
    assert issues[0].code is OptimizationIssueCode.CURRENCY_COMPATIBILITY_REVIEW_REQUIRED


def test_spend_semantics_match() -> None:
    view = portfolio_view()
    contract = complete_contract()
    assert spend_semantics_issues(mapping=_mapping(view, contract), contract=contract) == ()


def test_spend_semantics_mismatch_not_ready() -> None:
    view = portfolio_view()
    contract = complete_contract(
        variables=(spend_variable(semantics=SpendSemantics.IMPRESSIONS),)
    )
    receipt = _ready(view, contract)
    assert receipt.status is OptimizationReadinessStatus.NOT_READY
    assert any(
        issue.code is OptimizationIssueCode.SPEND_SEMANTICS_MISMATCH
        for issue in receipt.issues
    )


def test_plan_only_can_be_optimization_ready() -> None:
    receipt = _ready(portfolio_view(), complete_contract(), state=PortfolioCoverageState.PLAN_ONLY)
    assert receipt.status is OptimizationReadinessStatus.OPTIMIZATION_READY


def test_plan_and_actuals_can_be_optimization_ready() -> None:
    receipt = _ready(
        portfolio_view(), complete_contract(), state=PortfolioCoverageState.PLAN_AND_ACTUALS
    )
    assert receipt.status is OptimizationReadinessStatus.OPTIMIZATION_READY


def test_actuals_only_not_optimization_ready() -> None:
    receipt = _ready(
        portfolio_view(baseline=PortfolioBaselineKind.ACTUAL_YTD),
        complete_contract(),
        state=PortfolioCoverageState.ACTUALS_ONLY,
        snap=snapshot(baseline=PortfolioBaselineKind.ACTUAL_YTD),
    )
    assert receipt.status is OptimizationReadinessStatus.NOT_READY
    assert any(
        issue.code is OptimizationIssueCode.APPROVED_PLAN_REQUIRED
        for issue in receipt.issues
    )


def test_neither_not_configured() -> None:
    receipt = evaluate_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        coverage_state=PortfolioCoverageState.NEITHER,
        snapshot=None,
        view=None,
        contract=None,
        mapping=None,
        coverage=None,
        input_contract=None,
        created_at=now(),
    )
    assert receipt.status is OptimizationReadinessStatus.NOT_CONFIGURED


def test_actuals_never_replace_approved_baseline() -> None:
    receipt = _ready(
        portfolio_view(baseline=PortfolioBaselineKind.ACTUAL_YTD),
        complete_contract(),
        state=PortfolioCoverageState.PLAN_ONLY,
        snap=snapshot(baseline=PortfolioBaselineKind.APPROVED_PLAN),
    )
    assert any(
        issue.code is OptimizationIssueCode.ACTUALS_NEVER_REPLACE_APPROVED_BASELINE
        for issue in receipt.issues
    )
    assert receipt.status is not OptimizationReadinessStatus.OPTIMIZATION_READY


def test_observation_blockers_prevent_ready() -> None:
    view = portfolio_view(observations=(observation(PortfolioObservationType.UNRESOLVED_MARKET),))
    receipt = _ready(view, complete_contract())
    assert receipt.status is OptimizationReadinessStatus.NOT_READY
    assert any(issue.code is OptimizationIssueCode.OBSERVATION_BLOCKER for issue in receipt.issues)


def test_actual_exceeds_plan_does_not_block() -> None:
    view = portfolio_view(observations=(observation(PortfolioObservationType.ACTUAL_EXCEEDS_PLAN),))
    receipt = _ready(view, complete_contract())
    assert receipt.status is OptimizationReadinessStatus.OPTIMIZATION_READY
