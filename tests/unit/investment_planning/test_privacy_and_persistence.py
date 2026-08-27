"""P6-00 persistence barrier and private/no-store proofs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.investment_optimization.contracts import (
    ConstraintSetPayload,
    OptimizationExecutionPayload,
    ScenarioAssumptionPayload,
)
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    InvestmentPlanValidationReceipt,
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioComparisonView,
    PortfolioEvidenceCoverage,
    PortfolioSnapshotRef,
    PortfolioSourceFreshness,
    PortfolioSummary,
    PortfolioView,
)
from app.investment_planning.enums import (
    AmountKind,
    BudgetSourceGrain,
    InvestmentPlanReadyStatus,
    PortfolioBaselineKind,
)
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.firestore import FirestoreInvestmentPlanningStore
from app.investment_planning.privacy import (
    PRIVATE_NO_STORE_HEADERS,
    amount_bearing_response_headers,
    is_amount_bearing,
    safe_log_text,
)
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from tests.unit.investment_planning.test_p6_00_architecture import _plan
from tests.unit.support.fake_firestore import FakeFirestore


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def _view() -> PortfolioView:
    amount = MoneyAmount(
        kind=AmountKind.APPROVED, currency="USD", value=Decimal("123456.78"), missing=False
    )
    return PortfolioView(
        snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        currency="USD",
        baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
        summary=PortfolioSummary(currency="USD", totals=(amount,)),
        allocations=(
            PortfolioAllocationView(
                fiscal_year=2027,
                quarter=1,
                market_id="mkt_us",
                channel_id="search_paid",
                channel_registry_version=1,
                amounts=(amount,),
            ),
        ),
        coverage=PortfolioEvidenceCoverage(),
        freshness=PortfolioSourceFreshness(),
    )


def test_amount_bearing_models_cannot_be_stored() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    view = _view()
    with pytest.raises(PersistenceBarrierError, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(view)
    with pytest.raises(PersistenceBarrierError):
        store.put(view.summary)
    with pytest.raises(PersistenceBarrierError):
        store.put(view.allocations[0])
    comparison = PortfolioComparisonView(
        baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
        comparison_kind=AmountKind.ACTUAL,
        allocations=view.allocations,
    )
    with pytest.raises(PersistenceBarrierError):
        store.put(comparison)
    assert store.stored_types() == ()


def test_optimization_payloads_cannot_be_stored() -> None:
    store = InMemoryOptimizationMetadataStore()
    with pytest.raises(PersistenceBarrierError):
        store.put(OptimizationExecutionPayload(execution_plan_id="oexec_aaaaaaaaaaaaaaaaaa"))
    with pytest.raises(PersistenceBarrierError):
        store.put(ConstraintSetPayload(constraint_set_id="ocst_aaaaaaaaaaaaaaaaaaaa"))
    with pytest.raises(PersistenceBarrierError):
        store.put(ScenarioAssumptionPayload(assumption_set_id="oasm_aaaaaaaaaaaaaaaaaaaa"))


def test_metadata_snapshot_ref_can_be_stored() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    ref = PortfolioSnapshotRef(
        snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        workspace_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
        investment_plan_id="ipln_aaaaaaaaaaaaaaaaaaaa",
        business_profile_snapshot_id="bps_dddddddddddddddddddd",
        fingerprint="fp_snap",
        created_at=_now(),
        created_by="user_music_center",
    )
    stored = store.put(ref)
    assert stored.snapshot_id == ref.snapshot_id
    dumped = stored.model_dump()
    assert "123456.78" not in str(dumped)
    assert "allocations" not in dumped


def test_private_no_store_headers() -> None:
    headers = amount_bearing_response_headers()
    assert headers["Cache-Control"] == "private, no-store"
    assert headers == PRIVATE_NO_STORE_HEADERS
    assert is_amount_bearing(_view()) is True
    assert is_amount_bearing(
        PortfolioSnapshotRef(
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
    ) is False


def test_synthetic_amounts_are_redacted_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    view = _view()
    logger = logging.getLogger("prem3.investment_planning")
    with caplog.at_level(logging.INFO, logger="prem3.investment_planning"):
        logger.info("portfolio %s", safe_log_text(view.model_dump()))
    assert "123456.78" not in caplog.text
    assert "[REDACTED_AMOUNT]" in caplog.text


def test_firestore_store_is_metadata_only_and_round_trips() -> None:
    store = FirestoreInvestmentPlanningStore(FakeFirestore())
    with pytest.raises(PersistenceBarrierError, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(_view())
    store.put(_plan())
    plan = store.get_plan("ipln_aaaaaaaaaaaaaaaaaaaa")
    assert plan is not None
    source = BudgetDriveSourceVersion(
        source_version_id="bsrc_aaaaaaaaaaaaaaaaaaa",
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        project_id=plan.project_id,
        workspace_id=plan.workspace_id,
        drive_connection_id="gconn_aaaaaaaaaaaaaaaaaaa",
        budgets_folder_id="folder_budgets",
        drive_file_id="file_plan",
        file_name="plan.csv",
        mime_type="text/csv",
        schema_version="ingested_v1",
        mapping_version="v1",
        source_grain=BudgetSourceGrain.MARKET_CHANNEL_QUARTER,
        created_at=_now(),
        created_by="user_music_center",
    )
    stored_source = store.put(source)
    mapping = BudgetColumnMapping(
        mapping_id="imap_aaaaaaaaaaaaaaaaaaaa",
        plan_id=plan.plan_id,
        source_version_id=source.source_version_id,
        market_column="market_id",
        channel_column="channel",
        quarter_columns=("Q1", "Q2", "Q3", "Q4"),
        confirmed=True,
    )
    store.put(mapping)
    receipt = InvestmentPlanValidationReceipt(
        receipt_id="iprc_aaaaaaaaaaaaaaaaaaaa",
        plan_id=plan.plan_id,
        source_version_id=source.source_version_id,
        status=InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY,
        created_at=_now(),
    )
    store.put(receipt)
    loaded_source = store.get_source(source.source_version_id)
    assert loaded_source == stored_source
    assert store.mapping_for_source(source.source_version_id) == mapping
    assert store.latest_receipt(plan.plan_id) == receipt
    dumped = str(store.get_plan(plan.plan_id).model_dump()) + str(loaded_source.model_dump())
    assert "123456.78" not in dumped
    assert "allocations" not in dumped
