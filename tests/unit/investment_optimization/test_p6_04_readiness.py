"""P6-04 readiness receipts, staleness, and required checks."""

from __future__ import annotations

from app.investment_optimization.coverage import assemble_optimization_evidence_coverage
from app.investment_optimization.enums import (
    POLICY_VERSION,
    REQUIRED_READINESS_CHECKS,
    MappingKind,
    OptimizationReadinessStatus,
)
from app.investment_optimization.mapping import build_portfolio_model_mapping
from app.investment_optimization.readiness import (
    build_optimization_input_contract,
    evaluate_readiness,
    receipt_is_stale,
)
from app.investment_planning.enums import PortfolioCoverageState
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    allocation,
    complete_contract,
    now,
    portfolio_view,
    snapshot,
    spend_variable,
)


def _bundle(view=None, contract=None):
    view = view or portfolio_view()
    contract = contract or complete_contract()
    mapping = build_portfolio_model_mapping(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=view.snapshot_id,
        baseline_kind=view.baseline_kind,
        view=view,
        contract=contract,
        created_at=now(),
        created_by="user_music_center",
    )
    snap = snapshot()
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
    receipt = evaluate_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        coverage_state=PortfolioCoverageState.PLAN_ONLY,
        snapshot=snap,
        view=view,
        contract=contract,
        mapping=mapping,
        coverage=coverage,
        input_contract=input_contract,
        created_at=now(),
    )
    return mapping, input_contract, receipt


def test_all_required_checks_pass_optimization_ready() -> None:
    _mapping, _input, receipt = _bundle()
    assert tuple(item.code for item in receipt.checks) == REQUIRED_READINESS_CHECKS
    assert all(item.passed for item in receipt.checks)
    assert receipt.status is OptimizationReadinessStatus.OPTIMIZATION_READY
    assert receipt.policy_version == POLICY_VERSION


def test_any_blocking_check_prevents_ready() -> None:
    _mapping, _input, receipt = _bundle(
        view=portfolio_view(rows=(allocation("mkt_us", "tv_paid"),))
    )
    assert receipt.status is OptimizationReadinessStatus.NOT_READY
    assert any(not item.passed for item in receipt.checks)


def test_review_mapping_returns_review_required() -> None:
    contract = complete_contract(
        variables=(
            spend_variable("meta_spend", "social_paid"),
            spend_variable("tiktok_spend", "social_paid"),
        )
    )
    _mapping, _input, receipt = _bundle(
        view=portfolio_view(rows=(allocation("mkt_us", "social_paid"),)),
        contract=contract,
    )
    assert _mapping.mapping_entries[0].mapping_kind is MappingKind.ONE_TO_MANY
    assert receipt.status is OptimizationReadinessStatus.REVIEW_REQUIRED


def test_readiness_receipt_binds_all_fingerprints() -> None:
    mapping, input_contract, receipt = _bundle()
    assert receipt.portfolio_fingerprint == snapshot().fingerprint
    assert receipt.model_fingerprint == complete_contract().fingerprint
    assert receipt.mapping_fingerprint == mapping.fingerprint
    assert receipt.input_contract_fingerprint == input_contract.fingerprint
    assert receipt.model_consumption_contract_fingerprint == complete_contract().fingerprint


def test_stale_plan_invalidates_readiness() -> None:
    _mapping, _input, receipt = _bundle()
    assert receipt_is_stale(
        receipt,
        portfolio_fingerprint="fp_new",
        model_fingerprint=None,
        mapping_fingerprint=None,
    )


def test_stale_model_invalidates_readiness() -> None:
    _mapping, _input, receipt = _bundle()
    assert receipt_is_stale(
        receipt,
        portfolio_fingerprint=None,
        model_fingerprint="fp_new",
        mapping_fingerprint=None,
    )


def test_stale_mapping_invalidates_readiness() -> None:
    _mapping, _input, receipt = _bundle()
    assert receipt_is_stale(
        receipt,
        portfolio_fingerprint=None,
        model_fingerprint=None,
        mapping_fingerprint="fp_new",
    )


def test_idempotent_fingerprint() -> None:
    first = _bundle()[2]
    second = _bundle()[2]
    assert first.fingerprint == second.fingerprint
    assert first.receipt_id != second.receipt_id
