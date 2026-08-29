"""Additive entitlement capability mapping. Old snapshots remain valid."""

from __future__ import annotations

from app.control_plane.entitlements import PAID_PLAN_IDS, PlanId
from app.control_plane.models import EntitlementSnapshot, Feature
from app.project.enums import CapabilityFamily

_FEATURE_BY_CAPABILITY: dict[CapabilityFamily, Feature] = {
    CapabilityFamily.FOUNDATION: Feature.FOUNDATION,
    CapabilityFamily.MMM: Feature.MMM,
    CapabilityFamily.MTA: Feature.MTA,
    CapabilityFamily.FORECASTING: Feature.FORECASTING,
    CapabilityFamily.SCENARIO_SIMULATION: Feature.SCENARIO_SIMULATION,
    CapabilityFamily.BUDGET_OPTIMIZATION: Feature.BUDGET_OPTIMIZATION,
    CapabilityFamily.DECISION_INTELLIGENCE: Feature.DECISION_INTELLIGENCE,
    CapabilityFamily.PORTFOLIO_VIEW: Feature.PORTFOLIO_VIEW,
    CapabilityFamily.TEAM_SEATS: Feature.TEAM_SEATS,
    CapabilityFamily.API_ACCESS: Feature.API_ACCESS,
}

_PAID_COMPAT_CAPABILITIES: frozenset[CapabilityFamily] = frozenset(
    {
        CapabilityFamily.FOUNDATION,
        CapabilityFamily.BUSINESS_IQ,
        CapabilityFamily.DATA_FOUNDATION,
        CapabilityFamily.MMM,
        CapabilityFamily.MTA,
        CapabilityFamily.FORECASTING,
        CapabilityFamily.SCENARIO_SIMULATION,
        CapabilityFamily.BUDGET_OPTIMIZATION,
        CapabilityFamily.DECISION_INTELLIGENCE,
        CapabilityFamily.TEAM_SEATS,
    }
)


def entitled_for_capability(
    snapshot: EntitlementSnapshot, capability: CapabilityFamily
) -> bool:
    if capability is CapabilityFamily.BUSINESS_IQ:
        capability = CapabilityFamily.FOUNDATION
    if capability is CapabilityFamily.DATA_FOUNDATION:
        capability = CapabilityFamily.FOUNDATION
    feature = _FEATURE_BY_CAPABILITY.get(capability)
    if feature is not None and feature in snapshot.features:
        return True
    if snapshot.plan_id == PlanId.PLANNER:
        return False
    if snapshot.plan_id not in PAID_PLAN_IDS:
        return False
    if capability is CapabilityFamily.PORTFOLIO_VIEW:
        return snapshot.plan_id in {PlanId.PORTFOLIO, PlanId.ENTERPRISE}
    if capability is CapabilityFamily.API_ACCESS:
        return snapshot.plan_id == PlanId.ENTERPRISE
    return capability in _PAID_COMPAT_CAPABILITIES


def capability_summary(snapshot: EntitlementSnapshot) -> list[str]:
    names = [feature.value for feature in sorted(snapshot.features, key=lambda item: item.value)]
    for capability in CapabilityFamily:
        if capability in {
            CapabilityFamily.BUSINESS_IQ,
            CapabilityFamily.DATA_FOUNDATION,
        }:
            continue
        if entitled_for_capability(snapshot, capability) and capability.value.lower() not in names:
            names.append(capability.value.lower())
    return sorted(set(names))
