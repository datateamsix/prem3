"""Backend-owned public plan catalog. No Stripe Price IDs. No invented prices."""

from __future__ import annotations

from app.control_plane.entitlements import PLAN_MAX_ACTIVE_PROJECTS, PlanId
from app.service.billing_config import BillingConfig
from app.service.models import PlanCatalogEntry, PlanCatalogResponse

_PLAN_COPY: dict[str, tuple[str, str, list[str]]] = {
    PlanId.PLANNER: (
        "Planner",
        "Public deterministic PreM3 Planner. No paid Project slot.",
        ["Deterministic public Planner"],
    ),
    PlanId.PROJECT: (
        "Project",
        "One methodology-neutral active PreM3 Project with unlimited commercial re-evaluations.",
        ["One PreM3 Project", "Unlimited re-evaluations", "Meridian Integration"],
    ),
    PlanId.PORTFOLIO: (
        "Portfolio",
        "Up to ten methodology-neutral active PreM3 Projects with unlimited commercial re-evaluations.",
        ["Up to 10 PreM3 Projects", "Unlimited re-evaluations", "Meridian Integration"],
    ),
    PlanId.ENTERPRISE: (
        "Enterprise",
        "Up to fifty methodology-neutral active PreM3 Projects with unlimited commercial re-evaluations.",
        ["Up to 50 PreM3 Projects", "Unlimited re-evaluations", "Meridian Integration"],
    ),
}


def build_plan_catalog(
    *,
    config: BillingConfig | None = None,
    checkout_eligible: bool | None = None,
) -> PlanCatalogResponse:
    plans: list[PlanCatalogEntry] = []
    for plan_id in (PlanId.PLANNER, PlanId.PROJECT, PlanId.PORTFOLIO, PlanId.ENTERPRISE):
        display_name, description, features = _PLAN_COPY[plan_id]
        paid = plan_id != PlanId.PLANNER
        presentation = None
        if config is not None:
            presentation = config.catalog_presentation.get(plan_id)
        eligible = False
        if paid:
            if checkout_eligible is not None:
                eligible = checkout_eligible
            elif config is not None:
                eligible = config.checkout_eligible(plan_id)
        plans.append(
            PlanCatalogEntry(
                plan_id=plan_id,
                display_name=display_name,
                description=description,
                max_active_projects=PLAN_MAX_ACTIVE_PROJECTS[plan_id],
                feature_summary=features,
                billing_interval="month",
                display_price=presentation.display_price if presentation else None,
                amount=presentation.amount if presentation else None,
                currency=presentation.currency if presentation else None,
                checkout_eligible=eligible,
                unlimited_reevaluations=paid,
            )
        )
    return PlanCatalogResponse(plans=plans)
