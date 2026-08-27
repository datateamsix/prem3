"""P6-01 validation, source identity, and approval gating."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.control_plane.models import DriveWorkspaceBinding
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.governance.codes import BindingStatus
from app.identity_graph.contracts import CanonicalMarket
from app.identity_graph.enums import MarketKind, MarketStatus
from app.identity_graph.ids import new_market_id
from app.identity_graph.store import InMemoryIdentityGraphStore
from app.integrations.google.adapters import DriveFile
from app.investment_planning.contracts import BudgetColumnMapping
from app.investment_planning.drive_binding import CSV_MIME
from app.investment_planning.enums import (
    BudgetValidationCode,
    InvestmentPlanReadyStatus,
    MappingMethod,
)
from app.investment_planning.errors import SourceChangedSinceLoadError, UnresolvedMarketIdentityError
from app.investment_planning.identity import assert_investment_plan_ready_permitted
from app.investment_planning.lifecycle import approve_plan
from app.investment_planning.mapping import propose_column_mapping
from app.investment_planning.markets import IdentityGraphMarketDirectory
from app.investment_planning.parser import parse_budget_bytes
from app.investment_planning.source import assert_source_unchanged, require_source_identity
from app.investment_planning.validator import validate_budget_plan
from tests.unit.google_support import google_harness
from tests.unit.investment_planning.test_p6_00_architecture import _plan
from tests.unit.test_prem3_drive_governance import _setup_drive


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def test_source_change_fails_closed() -> None:
    loaded = require_source_identity(
        DriveFile(
            file_id="file_1",
            name="plan.csv",
            mime_type=CSV_MIME,
            parents=("folder_1",),
            md5="abc",
            head_revision_id="rev1",
            version="1",
            size_bytes=12,
        )
    )
    changed = DriveFile(
        file_id="file_1",
        name="plan.csv",
        mime_type=CSV_MIME,
        parents=("folder_1",),
        md5="def",
        head_revision_id="rev2",
        version="2",
        size_bytes=13,
    )
    with pytest.raises(SourceChangedSinceLoadError):
        assert_source_unchanged(loaded=loaded, current=changed)


def test_unknown_market_id_fails_closed() -> None:
    csv_bytes = (
        b"market_id,channel,Q1,Q2,Q3,Q4\n"
        b"mkt_us,search_paid,100,100,100,100\n"
    )
    table = parse_budget_bytes(data=csv_bytes, mime_type=CSV_MIME, file_name="plan.csv")
    proposal = propose_column_mapping(
        table,
        plan_id="ipln_aaaaaaaaaaaaaaaaaaaa",
        source_version_id="bsrc_aaaaaaaaaaaaaaaaaaa",
        confirmed=True,
    )
    binding = _binding()
    file = DriveFile(
        file_id="file_plan",
        name="plan.csv",
        mime_type=CSV_MIME,
        parents=(binding.budgets_folder_id or "folder_budgets",),
        md5="abc",
        head_revision_id="rev1",
        version="1",
        size_bytes=len(csv_bytes),
    )
    receipt = validate_budget_plan(
        plan=_plan(),
        binding=binding,
        file=file,
        table=table,
        mapping=proposal.mapping,
        loaded_identity=require_source_identity(file),
        known_market_ids=frozenset(),
        blanks_acknowledged=True,
    )
    assert receipt.status is not InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
    codes = {check.code: check.passed for check in receipt.checks}
    assert codes[BudgetValidationCode.MARKETS_RESOLVED.value] is False
    assert codes[BudgetValidationCode.CANONICAL_MARKET_CONTRACT.value] is True
    with pytest.raises(UnresolvedMarketIdentityError):
        approve_plan(plan=_plan(), receipt=receipt, actor_id="user_music_center")


def test_iso_and_display_names_do_not_resolve_markets() -> None:
    csv_bytes = b"market_id,channel,Q1,Q2,Q3,Q4\nUS,search_paid,1,1,1,1\n"
    table = parse_budget_bytes(data=csv_bytes, mime_type=CSV_MIME, file_name="plan.csv")
    mapping = BudgetColumnMapping(
        mapping_id="imap_aaaaaaaaaaaaaaaaaaaa",
        plan_id="ipln_aaaaaaaaaaaaaaaaaaaa",
        source_version_id="bsrc_aaaaaaaaaaaaaaaaaaa",
        market_column="market_id",
        channel_column="channel",
        quarter_columns=("Q1", "Q2", "Q3", "Q4"),
        mapping_method=MappingMethod.EXPLICIT_USER_MAP,
        confirmed=True,
    )
    binding = _binding()
    file = DriveFile(
        file_id="file_plan",
        name="plan.csv",
        mime_type=CSV_MIME,
        parents=(binding.budgets_folder_id or "folder_budgets",),
        md5="abc",
        head_revision_id="rev1",
        version="1",
        size_bytes=20,
    )
    receipt = validate_budget_plan(
        plan=_plan(),
        binding=binding,
        file=file,
        table=table,
        mapping=mapping,
        loaded_identity=require_source_identity(file),
        known_market_ids=frozenset({"mkt_us"}),
        blanks_acknowledged=True,
    )
    assert receipt.status is not InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
    assert any(not check.passed and check.code == "MARKETS_RESOLVED" for check in receipt.checks)


def test_investment_plan_ready_requires_resolved_market_refs() -> None:
    market_id = new_market_id()
    store = InMemoryIdentityGraphStore()
    store.put_market(
        CanonicalMarket(
            market_id=market_id,
            tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
            project_id="wsp_cccccccccccccccccccc",
            name="DACH",
            market_kind=MarketKind.MULTI_COUNTRY_REGION,
            status=MarketStatus.ACTIVE,
            country_codes=("DE", "AT", "CH"),
            created_at=_now(),
            updated_at=_now(),
            created_by="user_music_center",
        )
    )
    directory = IdentityGraphMarketDirectory(store)
    csv_bytes = (
        f"market_id,channel,Q1,Q2,Q3,Q4\n{market_id},search_paid,100,100,100,100\n"
    ).encode()
    table = parse_budget_bytes(data=csv_bytes, mime_type=CSV_MIME, file_name="plan.csv")
    proposal = propose_column_mapping(
        table,
        plan_id="ipln_aaaaaaaaaaaaaaaaaaaa",
        source_version_id="bsrc_aaaaaaaaaaaaaaaaaaa",
        confirmed=True,
    )
    binding = _binding()
    file = DriveFile(
        file_id="file_plan",
        name="plan.csv",
        mime_type=CSV_MIME,
        parents=(binding.budgets_folder_id or "folder_budgets",),
        md5="abc",
        head_revision_id="rev1",
        version="1",
        size_bytes=len(csv_bytes),
    )
    known = directory.known_market_ids(
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
    )
    receipt = validate_budget_plan(
        plan=_plan(),
        binding=binding,
        file=file,
        table=table,
        mapping=proposal.mapping,
        loaded_identity=require_source_identity(file),
        known_market_ids=known,
        blanks_acknowledged=True,
        directory=directory,
    )
    assert receipt.status is InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
    codes = {check.code: check.passed for check in receipt.checks}
    assert codes[BudgetValidationCode.MARKETS_RESOLVED.value] is True
    assert codes[BudgetValidationCode.CHANNELS_RESOLVED.value] is True
    approved = approve_plan(plan=_plan(), receipt=receipt, actor_id="user_music_center")
    assert approved.status.value == "APPROVED"


def test_create_and_ingest_keeps_amounts_off_control_plane() -> None:
    from app.business_iq.contracts import BusinessIdentity, BusinessProfile, Market, MarketingChannel
    from app.business_iq.store import InMemoryBusinessIqStore
    from app.core.contracts import utc_now
    from app.investment_planning.service import InvestmentPlanService
    from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore

    harness = google_harness()
    _setup_drive(harness)
    tenant = harness["tenant"]
    project_id = harness["workspace"]["workspace_id"]
    now = utc_now()
    profile = BusinessProfile(
        profile_id="bpf_aaaaaaaaaaaaaaaaaaaa",
        tenant_id=tenant.tenant_id,
        workspace_id=project_id,
        version=1,
        fingerprint="fp_biq",
        current_snapshot_id="bps_dddddddddddddddddddd",
        business_identity=BusinessIdentity(),
        markets=(Market(market_id="mkt_us", name="United States"),),
        marketing_portfolio=(
            MarketingChannel(
                channel_id="bch_search",
                canonical_name="Paid Search",
                registry_channel_id="search_paid",
                channel_registry_version=1,
            ),
        ),
        created_at=now,
        updated_at=now,
        updated_by="user_music_center",
        created_by="user_music_center",
    )
    store = InMemoryBusinessIqStore()
    store.put_profile(profile)
    planning = InMemoryInvestmentPlanningMetadataStore()
    service = InvestmentPlanService(
        repo=harness["repo"],
        store=planning,
        drive=harness["drive"],
        connections=harness["client"].app.state.google_connections
        if hasattr(harness["client"].app.state, "google_connections")
        else harness["client"].app.state.drive_bindings._connections,
        drive_bindings=harness["client"].app.state.drive_bindings,
        business_iq=store,
    )
    ctx = TenantContext(
        tenant_id=tenant.tenant_id,
        user_id="user_acme",
        auth_state=AuthState.AUTHENTICATED,
    )
    csv_bytes = (
        b"market_id,channel,Q1,Q2,Q3,Q4\n"
        b"mkt_us,search_paid,250000,0,,100\n"
    )
    with bind_tenant(ctx):
        plan = service.create_plan(
            project_id=project_id,
            name="FY2027",
            fiscal_year=2027,
            actor_id="user_acme",
        )
        source, _table, proposal = service.ingest_bytes(
            plan_id=plan.plan_id,
            file_name="FY2027_marketing_budget_v001.csv",
            mime_type=CSV_MIME,
            data=csv_bytes,
            actor_id="user_acme",
        )
        receipt = service.validate(
            plan_id=plan.plan_id,
            mapping_id=proposal.mapping.mapping_id,
            table=_table,
            blanks_acknowledged=True,
        )
        with pytest.raises(UnresolvedMarketIdentityError):
            service.approve(
                plan_id=plan.plan_id, receipt_id=receipt.receipt_id, actor_id="user_acme"
            )
    dumped = source.model_dump()
    assert "250000" not in str(dumped)
    assert receipt.status is not InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
    assert_investment_plan_ready_permitted(market_bearing=False)


def _binding() -> DriveWorkspaceBinding:
    return DriveWorkspaceBinding(
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        workspace_id="wsp_cccccccccccccccccccc",
        connection_id="gconn_aaaaaaaaaaaaaaaaaaa",
        root_folder_id="folder_root",
        imports_folder_id="folder_imports",
        exports_folder_id="folder_exports",
        reports_folder_id="folder_reports",
        budgets_folder_id="folder_budgets",
        budget_templates_folder_id="folder_templates",
        budget_plans_folder_id="folder_plans",
        budget_scenarios_folder_id="folder_scenarios",
        budget_proposals_folder_id="folder_proposals",
        status=BindingStatus.ACTIVE.value,
        import_enabled=True,
        export_enabled=True,
        created_at=_now(),
        updated_at=_now(),
    )
