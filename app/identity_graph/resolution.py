"""Fail-closed campaign identity resolution and hierarchy checks."""

from __future__ import annotations

from app.identity_graph.contracts import (
    CampaignExternalBinding,
    CampaignIdentityResolution,
    CampaignTrackingBinding,
    CanonicalCampaign,
    ObservedCampaignSignals,
)
from app.identity_graph.enums import (
    BindingStatus,
    CampaignIdentitySource,
    ResolutionAuthority,
    TrackingKind,
)
from app.identity_graph.errors import IdentityGraphError

_ACTIVE_TRACKING = {BindingStatus.ACTIVE, BindingStatus.CONFIRMED, BindingStatus.APPROVED}
_CONFIRMED_EXTERNAL = {BindingStatus.CONFIRMED, BindingStatus.ACTIVE}
_APPROVED_CUSTOM = {BindingStatus.APPROVED}
_USER_CONFIRMED = {BindingStatus.CONFIRMED, BindingStatus.APPROVED}


def assert_not_self_parent(campaign_id: str, parent_campaign_id: str | None) -> None:
    if parent_campaign_id is not None and parent_campaign_id == campaign_id:
        raise IdentityGraphError(
            "A campaign cannot parent itself.",
            code="SELF_PARENT",
        )


def assert_parent_same_project(
    campaign: CanonicalCampaign, parent: CanonicalCampaign | None
) -> None:
    if parent is None:
        raise IdentityGraphError(
            "Parent campaign was not found in this project.",
            code="PARENT_CROSS_PROJECT",
        )
    if parent.tenant_id != campaign.tenant_id or parent.project_id != campaign.project_id:
        raise IdentityGraphError(
            "Campaign parent must belong to the same project.",
            code="PARENT_CROSS_PROJECT",
        )


def would_create_cycle(
    *,
    campaign_id: str,
    new_parent_id: str,
    campaigns: dict[str, CanonicalCampaign],
) -> bool:
    if campaign_id == new_parent_id:
        return True
    seen: set[str] = set()
    current: str | None = new_parent_id
    while current:
        if current == campaign_id:
            return True
        if current in seen:
            return True
        seen.add(current)
        parent = campaigns.get(current)
        current = parent.parent_campaign_id if parent is not None else None
    return False


def _hit(
    campaign_id: str, source: CampaignIdentitySource
) -> tuple[str, CampaignIdentitySource]:
    return (campaign_id, source)


def resolve_campaign_identity(
    *,
    campaigns: list[CanonicalCampaign],
    tracking: list[CampaignTrackingBinding],
    external: list[CampaignExternalBinding],
    signals: ObservedCampaignSignals,
) -> CampaignIdentityResolution:
    """Precedence: PreM3 utm_id, confirmed external, approved custom, user-confirmed, unresolved.

    Fuzzy names never resolve. Conflicting exact campaign IDs require review.
    """
    del campaigns
    hits: list[tuple[str, CampaignIdentitySource]] = []

    if signals.utm_id:
        for binding in tracking:
            if (
                binding.tracking_kind == TrackingKind.PREM3_UTM_ID
                and binding.status in _ACTIVE_TRACKING
                and binding.parameter_name == "utm_id"
                and binding.parameter_value == signals.utm_id
            ):
                hits.append(_hit(binding.campaign_id, CampaignIdentitySource.PREM3_UTM_ID))

    if signals.provider_id and signals.external_campaign_id:
        account = signals.external_account_id or ""
        for binding in external:
            if binding.status not in _CONFIRMED_EXTERNAL:
                continue
            if binding.provider_id != signals.provider_id:
                continue
            if (binding.external_account_id or "") != account:
                continue
            if binding.external_campaign_id != signals.external_campaign_id:
                continue
            hits.append(
                _hit(binding.campaign_id, CampaignIdentitySource.EXTERNAL_CAMPAIGN_BINDING)
            )

    if signals.custom_parameter_name and signals.custom_parameter_value:
        custom_hits = [
            binding
            for binding in tracking
            if binding.tracking_kind == TrackingKind.CUSTOM_EVENT_PARAM
            and binding.parameter_name == signals.custom_parameter_name
            and binding.parameter_value == signals.custom_parameter_value
        ]
        if custom_hits and not all(item.status in _APPROVED_CUSTOM for item in custom_hits):
            return CampaignIdentityResolution(
                campaign_id=None,
                source=CampaignIdentitySource.CUSTOM_IDENTIFIER,
                status=ResolutionAuthority.REVIEW_REQUIRED,
                issues=("CUSTOM_IDENTIFIER_NOT_APPROVED",),
                utm_campaign=signals.utm_campaign,
                external_campaign_name=signals.external_campaign_name,
            )
        for binding in custom_hits:
            hits.append(_hit(binding.campaign_id, CampaignIdentitySource.CUSTOM_IDENTIFIER))

    if signals.user_confirmed_campaign_id:
        confirmed = [
            binding
            for binding in tracking
            if binding.tracking_kind == TrackingKind.MANUAL_MAPPING
            and binding.status in _USER_CONFIRMED
            and binding.campaign_id == signals.user_confirmed_campaign_id
        ]
        if confirmed:
            hits.append(
                _hit(
                    signals.user_confirmed_campaign_id,
                    CampaignIdentitySource.USER_CONFIRMED_MAPPING,
                )
            )

    # signals.fuzzy_name is display context only and never becomes a hit.

    if not hits:
        return CampaignIdentityResolution(
            campaign_id=None,
            source=CampaignIdentitySource.UNRESOLVED,
            status=ResolutionAuthority.UNRESOLVED,
            campaign_name_raw=signals.external_campaign_name,
            external_campaign_name=signals.external_campaign_name,
            utm_campaign=signals.utm_campaign,
        )

    campaign_ids = {item[0] for item in hits}
    if len(campaign_ids) > 1:
        return CampaignIdentityResolution(
            campaign_id=None,
            source=CampaignIdentitySource.UNRESOLVED,
            status=ResolutionAuthority.REVIEW_REQUIRED,
            issues=("CONFLICTING_EXACT_BINDINGS",),
            campaign_name_raw=signals.external_campaign_name,
            external_campaign_name=signals.external_campaign_name,
            utm_campaign=signals.utm_campaign,
        )

    precedence = [
        CampaignIdentitySource.PREM3_UTM_ID,
        CampaignIdentitySource.EXTERNAL_CAMPAIGN_BINDING,
        CampaignIdentitySource.CUSTOM_IDENTIFIER,
        CampaignIdentitySource.USER_CONFIRMED_MAPPING,
    ]
    source = next(item for item in precedence if item in {hit[1] for hit in hits})
    return CampaignIdentityResolution(
        campaign_id=next(iter(campaign_ids)),
        source=source,
        status=ResolutionAuthority.RESOLVED,
        campaign_name_raw=signals.external_campaign_name,
        external_campaign_name=signals.external_campaign_name,
        utm_campaign=signals.utm_campaign,
    )
