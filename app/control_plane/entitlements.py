"""Deterministic plan defaults and subscription → entitlement projection seam.

Price IDs stay in billing configuration. This module maps provider subscription
status onto PreM3 entitlement state and plan capacity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import assert_never

from app.control_plane.ids import new_entitlement_snapshot_id
from app.control_plane.models import (
    EntitlementSnapshot,
    EntitlementSource,
    EntitlementStatus,
    Feature,
    SubscriptionProjection,
)

PLANNER_FEATURES: frozenset[Feature] = frozenset()

PAID_FEATURES: frozenset[Feature] = frozenset(
    {
        Feature.PROJECT_CREATE,
        Feature.PLANNING_RUN,
        Feature.PLAN_COMPILE,
        Feature.PLAN_EXPORT,
        Feature.DATASET_CREATE,
        Feature.DATA_UPLOAD,
        Feature.DATASET_ASSESSMENT,
        Feature.SAFE_REMEDIATION,
        Feature.BIGQUERY_PUBLISH,
        Feature.OFFICIAL_MERIDIAN_EDA,
        Feature.MERIDIAN_INTEGRATION,
        Feature.REGISTRY_RESEARCH,
        Feature.TEAM_SEATS,
        Feature.FOUNDATION,
        Feature.MMM,
        Feature.MTA,
        Feature.FORECASTING,
        Feature.SCENARIO_SIMULATION,
        Feature.BUDGET_OPTIMIZATION,
        Feature.DECISION_INTELLIGENCE,
    }
)


class PlanId(StrEnum):
    PLANNER = "planner"
    PROJECT = "project"
    PORTFOLIO = "portfolio"
    ENTERPRISE = "enterprise"


PLAN_MAX_ACTIVE_PROJECTS: dict[str, int] = {
    PlanId.PLANNER: 0,
    PlanId.PROJECT: 1,
    PlanId.PORTFOLIO: 10,
    PlanId.ENTERPRISE: 50,
}

PAID_PLAN_IDS: frozenset[str] = frozenset(
    {PlanId.PROJECT, PlanId.PORTFOLIO, PlanId.ENTERPRISE}
)

# Stripe API version 2026-07-29.dahlia subscription.status values.
STRIPE_SUBSCRIPTION_STATUSES: frozenset[str] = frozenset(
    {
        "incomplete",
        "incomplete_expired",
        "trialing",
        "active",
        "past_due",
        "canceled",
        "unpaid",
        "paused",
    }
)


class UnsupportedSubscriptionStatusError(ValueError):
    """Raised when a provider subscription status has no fail-closed PreM3 mapping."""


def _features_for_plan(plan_id: str) -> frozenset[Feature]:
    if plan_id == PlanId.PLANNER:
        return PLANNER_FEATURES
    if plan_id not in PAID_PLAN_IDS:
        raise ValueError(f"Unknown plan_id: {plan_id}")
    features = set(PAID_FEATURES)
    if plan_id in {PlanId.PORTFOLIO, PlanId.ENTERPRISE}:
        features.add(Feature.PORTFOLIO_VIEW)
    if plan_id == PlanId.ENTERPRISE:
        features.add(Feature.API_ACCESS)
    return frozenset(features)


def default_planner_entitlement(
    *,
    tenant_id: str,
    now: datetime | None = None,
    snapshot_id: str | None = None,
) -> EntitlementSnapshot:
    """Only valid default entitlement: Planner with max_active_projects = 0."""
    stamp = now or datetime.now(UTC)
    return EntitlementSnapshot(
        snapshot_id=snapshot_id or new_entitlement_snapshot_id(),
        tenant_id=tenant_id,
        plan_id=PlanId.PLANNER,
        features=PLANNER_FEATURES,
        limits={"max_active_projects": PLAN_MAX_ACTIVE_PROJECTS[PlanId.PLANNER]},
        status=EntitlementStatus.ACTIVE,
        valid_until=None,
        source=EntitlementSource.DEFAULT,
        created_at=stamp,
    )


def entitlement_for_plan(
    *,
    tenant_id: str,
    plan_id: str,
    source: EntitlementSource,
    status: EntitlementStatus = EntitlementStatus.ACTIVE,
    valid_until: datetime | None = None,
    now: datetime | None = None,
    snapshot_id: str | None = None,
) -> EntitlementSnapshot:
    if plan_id not in PLAN_MAX_ACTIVE_PROJECTS:
        raise ValueError(f"Unknown plan_id: {plan_id}")
    stamp = now or datetime.now(UTC)
    return EntitlementSnapshot(
        snapshot_id=snapshot_id or new_entitlement_snapshot_id(),
        tenant_id=tenant_id,
        plan_id=plan_id,
        features=_features_for_plan(plan_id),
        limits={"max_active_projects": PLAN_MAX_ACTIVE_PROJECTS[plan_id]},
        status=status,
        valid_until=valid_until,
        source=source,
        created_at=stamp,
    )


def map_stripe_subscription_status(status: str) -> EntitlementStatus:
    """Map every known Stripe subscription status. Unknown statuses are not ACTIVE."""
    key = status.strip().lower()
    if key == "active":
        return EntitlementStatus.ACTIVE
    if key == "trialing":
        return EntitlementStatus.TRIALING
    if key == "past_due":
        return EntitlementStatus.PAST_DUE
    if key == "incomplete":
        return EntitlementStatus.INCOMPLETE
    if key in {"canceled", "unpaid", "paused", "incomplete_expired"}:
        return EntitlementStatus.CANCELED
    raise UnsupportedSubscriptionStatusError(status)


def allows_paid_capacity_mutation(status: EntitlementStatus) -> bool:
    if status is EntitlementStatus.ACTIVE:
        return True
    if status is EntitlementStatus.TRIALING:
        return True
    if status is EntitlementStatus.PAST_DUE:
        return False
    if status is EntitlementStatus.CANCELED:
        return False
    if status is EntitlementStatus.INCOMPLETE:
        return False
    assert_never(status)


def projections_materially_equal(
    current: SubscriptionProjection | None, incoming: SubscriptionProjection
) -> bool:
    if current is None:
        return False
    return (
        current.tenant_id == incoming.tenant_id
        and current.provider_subscription_id == incoming.provider_subscription_id
        and current.provider_customer_id == incoming.provider_customer_id
        and current.plan_id == incoming.plan_id
        and current.status == incoming.status
        and current.current_period_end == incoming.current_period_end
        and current.cancel_at_period_end == incoming.cancel_at_period_end
    )


def entitlements_materially_equal(
    current: EntitlementSnapshot | None, incoming: EntitlementSnapshot
) -> bool:
    if current is None:
        return False
    return (
        current.tenant_id == incoming.tenant_id
        and current.plan_id == incoming.plan_id
        and current.status == incoming.status
        and current.max_active_projects == incoming.max_active_projects
        and current.features == incoming.features
        and current.source == incoming.source
    )


def project_subscription_to_entitlement(
    subscription: SubscriptionProjection,
    *,
    now: datetime | None = None,
) -> EntitlementSnapshot:
    """Pure seam: SubscriptionProjection → new immutable EntitlementSnapshot.

    Business operations consume the entitlement, never raw Stripe objects.
    Unknown provider statuses fail closed and never become ACTIVE.
    """
    mapped = map_stripe_subscription_status(subscription.status)
    return entitlement_for_plan(
        tenant_id=subscription.tenant_id,
        plan_id=subscription.plan_id,
        source=EntitlementSource.BILLING_PROVIDER,
        status=mapped,
        valid_until=subscription.current_period_end,
        now=now,
    )
