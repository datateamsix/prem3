"""Investment Plan lifecycle. Approval is human-only and readiness-gated."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_planning.authority import require_human_approver
from app.investment_planning.contracts import InvestmentPlan, InvestmentPlanValidationReceipt
from app.investment_planning.enums import InvestmentPlanReadyStatus, InvestmentPlanStatus
from app.investment_planning.errors import (
    CanonicalMarketContractPendingError,
    PlanningAuthorityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.identity import CANONICAL_MARKET_CONTRACT_INTEGRATED
from app.investment_planning.fingerprint import investment_plan_fingerprint
from app.investment_planning.ids import new_plan_id


def mark_validated(plan: InvestmentPlan, receipt: InvestmentPlanValidationReceipt) -> InvestmentPlan:
    if receipt.plan_id != plan.plan_id:
        raise PlanningAuthorityError("Validation receipt does not belong to this plan.")
    return plan.model_copy(
        update={"status": InvestmentPlanStatus.VALIDATED, "updated_at": datetime.now(UTC)}
    )


def approve_plan(
    *,
    plan: InvestmentPlan,
    receipt: InvestmentPlanValidationReceipt,
    actor_id: str,
) -> InvestmentPlan:
    require_human_approver(actor_id)
    if receipt.plan_id != plan.plan_id:
        raise PlanningAuthorityError("Validation receipt does not belong to this plan.")
    if receipt.status is not InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY:
        if (
            "CANONICAL_MARKET_CONTRACT" in receipt.error_codes
            and not CANONICAL_MARKET_CONTRACT_INTEGRATED
        ):
            raise CanonicalMarketContractPendingError(
                "INVESTMENT_PLAN_READY cannot be declared for a market-bearing plan until "
                "the IG-01 canonical-market contract is integrated.",
                code="CANONICAL_MARKET_CONTRACT_PENDING",
            )
        if "MARKETS_RESOLVED" in receipt.error_codes:
            raise UnresolvedMarketIdentityError(
                "INVESTMENT_PLAN_READY requires every market reference to resolve to a "
                "canonical Identity Graph market_id.",
                code="UNRESOLVED_MARKET_IDENTITY",
            )
        raise PlanningAuthorityError("Plan is not INVESTMENT_PLAN_READY.")
    now = datetime.now(UTC)
    approved = plan.model_copy(
        update={
            "status": InvestmentPlanStatus.APPROVED,
            "approved_at": now,
            "approved_by": actor_id,
            "updated_at": now,
        }
    )
    investment_plan_fingerprint(
        plan_id=approved.plan_id,
        project_id=approved.project_id,
        revision=approved.revision,
        status=approved.status.value,
    )
    return approved


def revise_plan(*, plan: InvestmentPlan, actor_id: str) -> InvestmentPlan:
    require_human_approver(actor_id)
    if plan.status is not InvestmentPlanStatus.APPROVED:
        raise PlanningAuthorityError("Only an approved plan can be revised.")
    now = datetime.now(UTC)
    return InvestmentPlan(
        plan_id=new_plan_id(),
        tenant_id=plan.tenant_id,
        project_id=plan.project_id,
        workspace_id=plan.workspace_id,
        name=plan.name,
        fiscal_year=plan.fiscal_year,
        fiscal_start_month=plan.fiscal_start_month,
        currency=plan.currency,
        budget_scope=plan.budget_scope,
        budget_scope_custom_text=plan.budget_scope_custom_text,
        business_profile_snapshot_id=plan.business_profile_snapshot_id,
        business_profile_fingerprint=plan.business_profile_fingerprint,
        active_source_version_id=None,
        status=InvestmentPlanStatus.DRAFT,
        revision=plan.revision + 1,
        predecessor_plan_id=plan.plan_id,
        created_at=now,
        updated_at=now,
        created_by=actor_id,
    )
