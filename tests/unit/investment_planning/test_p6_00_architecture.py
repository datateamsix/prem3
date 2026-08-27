"""P6-00 contract freeze: ownership, identity, baselines, API namespace."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.control_plane.models import DriveWorkspaceBinding
from app.control_plane.serialization import document_to_model
from app.domain.channels.bindings import PlanningChannelAllocation
from app.investment_optimization.authority import require_new_plan_version_on_approval
from app.investment_optimization.enums import OptimizationProposalStatus
from app.investment_planning.api_namespace import (
    CANONICAL_INVESTMENT_OPTIMIZATIONS,
    CANONICAL_INVESTMENT_PLANS,
    CANONICAL_INVESTMENT_PORTFOLIO,
    WORKSPACE_ALIAS_INVESTMENT_PLANS,
)
from app.investment_planning.authority import require_human_approver
from app.investment_planning.contracts import (
    InvestmentPlan,
    MoneyAmount,
    PortfolioSnapshotRef,
    actual_spend_is_not_approved_budget,
)
from app.investment_planning.drive_binding import BUDGET_DRIVE_FOLDER_FIELDS
from app.investment_planning.enums import (
    AmountKind,
    BudgetScope,
    InvestmentPlanStatus,
    PortfolioBaselineKind,
)
from app.investment_planning.errors import PlanningAuthorityError
from app.investment_planning.fingerprint import investment_plan_fingerprint
from app.investment_planning.ids import new_plan_id
from app.project.enums import CapabilityAvailability, CapabilityFamily, NextActionType
from app.project.tracks import planning_availability
from app.service.app import create_app


def _now() -> datetime:
    return datetime(2026, 8, 26, tzinfo=UTC)


def _plan(**overrides: object) -> InvestmentPlan:
    payload = {
        "plan_id": "ipln_aaaaaaaaaaaaaaaaaaaa",
        "tenant_id": "ten_bbbbbbbbbbbbbbbbbbbb",
        "project_id": "wsp_cccccccccccccccccccc",
        "workspace_id": "wsp_cccccccccccccccccccc",
        "name": "FY2027 Marketing Plan",
        "fiscal_year": 2027,
        "fiscal_start_month": 1,
        "currency": "USD",
        "budget_scope": BudgetScope.PAID_MEDIA_ONLY,
        "business_profile_snapshot_id": "bps_dddddddddddddddddddd",
        "business_profile_fingerprint": "fp_biq",
        "status": InvestmentPlanStatus.DRAFT,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": "user_music_center",
    }
    payload.update(overrides)
    return InvestmentPlan(**payload)


def test_investment_plan_is_project_scoped_and_optional_metadata() -> None:
    plan = _plan()
    assert plan.project_id == plan.workspace_id
    assert not hasattr(plan, "declared_annual_budget")
    dumped = plan.model_dump()
    assert "q1" not in dumped
    assert "allocations" not in dumped


def test_project_workspace_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="project_id must equal workspace_id"):
        _plan(workspace_id="wsp_otherproject00000000")


def test_amount_kinds_and_missing_not_zero() -> None:
    present = MoneyAmount(
        kind=AmountKind.APPROVED, currency="USD", value=Decimal("100.00"), missing=False
    )
    missing = MoneyAmount(kind=AmountKind.ACTUAL, currency="USD", value=None, missing=True)
    assert present.value == Decimal("100.00")
    assert missing.missing is True
    with pytest.raises(ValueError):
        MoneyAmount(kind=AmountKind.PLANNED, currency="USD", value=Decimal("0"), missing=True)
    with pytest.raises(ValueError):
        MoneyAmount(kind=AmountKind.PLANNED, currency="USD", value=None, missing=False)


def test_actual_spend_is_not_approved_budget() -> None:
    assert actual_spend_is_not_approved_budget(PortfolioBaselineKind.ACTUAL_YTD)
    assert actual_spend_is_not_approved_budget(PortfolioBaselineKind.GOVERNED_ACTUALS)
    assert not actual_spend_is_not_approved_budget(PortfolioBaselineKind.APPROVED_PLAN)
    snapshot = PortfolioSnapshotRef(
        snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        project_id="wsp_cccccccccccccccccccc",
        workspace_id="wsp_cccccccccccccccccccc",
        fiscal_year=2027,
        baseline_kind=PortfolioBaselineKind.ACTUAL_YTD,
        investment_plan_id=None,
        business_profile_snapshot_id="bps_dddddddddddddddddddd",
        fingerprint="fp_snap",
        created_at=_now(),
        created_by="user_music_center",
    )
    assert snapshot.baseline_kind is not PortfolioBaselineKind.APPROVED_PLAN


def test_canonical_api_namespace_has_workspace_alias() -> None:
    assert CANONICAL_INVESTMENT_PLANS.startswith("/v1/projects/{project_id}/")
    assert CANONICAL_INVESTMENT_PORTFOLIO.startswith("/v1/projects/{project_id}/")
    assert CANONICAL_INVESTMENT_OPTIMIZATIONS.startswith("/v1/projects/{project_id}/")
    assert WORKSPACE_ALIAS_INVESTMENT_PLANS.startswith("/v1/workspaces/{workspace_id}/")


def test_p6_00_does_not_register_fake_investment_plan_routes() -> None:
    schema = create_app().openapi()
    paths = schema.get("paths", {})
    for path in paths:
        assert "investment-plan" not in path
        assert "investment-portfolio" not in path
        assert "investment-optimization" not in path


def test_drive_budget_folder_fields_are_optional_on_historical_bindings() -> None:
    for field in BUDGET_DRIVE_FOLDER_FIELDS:
        info = DriveWorkspaceBinding.model_fields[field]
        assert info.default is None
    historical = {
        "tenant_id": "ten_bbbbbbbbbbbbbbbbbbbb",
        "workspace_id": "wsp_cccccccccccccccccccc",
        "connection_id": "gconn_aaaaaaaaaaaaaaaaaaa",
        "root_folder_id": "fld_root",
        "imports_folder_id": "fld_imports",
        "exports_folder_id": "fld_exports",
        "reports_folder_id": "fld_reports",
        "status": "ACTIVE",
        "import_enabled": True,
        "export_enabled": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    binding = document_to_model(DriveWorkspaceBinding, historical)
    assert binding.budgets_folder_id is None
    assert binding.budget_templates_folder_id is None
    assert binding.budget_plans_folder_id is None
    assert binding.budget_scenarios_folder_id is None
    assert binding.budget_proposals_folder_id is None


def test_human_approval_rejects_service_accounts() -> None:
    assert require_human_approver("user_music_center") == "user_music_center"
    with pytest.raises(PlanningAuthorityError):
        require_human_approver("worker@prem3.iam.gserviceaccount.com")
    with pytest.raises(PlanningAuthorityError):
        require_human_approver("service-account:meridian-worker")


def test_proposal_approval_does_not_mutate_active_plan() -> None:
    actor = require_new_plan_version_on_approval(
        current_status=OptimizationProposalStatus.RECOMMENDED,
        actor_id="user_music_center",
    )
    assert actor == "user_music_center"
    with pytest.raises(PlanningAuthorityError):
        require_new_plan_version_on_approval(
            current_status=OptimizationProposalStatus.DRAFT,
            actor_id="user_music_center",
        )


def test_plan_fingerprint_is_not_persist_permission() -> None:
    fp = investment_plan_fingerprint(
        plan_id=new_plan_id(),
        project_id="wsp_cccccccccccccccccccc",
        revision=1,
        status=InvestmentPlanStatus.DRAFT.value,
    )
    assert len(fp) == 64


def test_legacy_planning_channel_allocation_amount_field_remains_float() -> None:
    alloc = PlanningChannelAllocation(
        allocation_id="a1",
        channel_id="search_paid",
        channel_registry_version=1,
        amount=123456.78,
    )
    assert isinstance(alloc.amount, float)


def test_investment_plan_is_not_blocked_by_model_ready() -> None:
    availability, action = planning_availability(
        capability=CapabilityFamily.INVESTMENT_PLAN,
        entitled=True,
        model_ready=False,
        model_accepted=False,
    )
    assert availability is CapabilityAvailability.AVAILABLE_TO_CONFIGURE
    assert action is NextActionType.START_INVESTMENT_PLAN
    opt_availability, _ = planning_availability(
        capability=CapabilityFamily.BUDGET_OPTIMIZATION,
        entitled=True,
        model_ready=True,
        model_accepted=False,
    )
    assert opt_availability is CapabilityAvailability.NEEDS_ACCEPTED_MODEL
