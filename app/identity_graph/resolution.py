"""Fail-closed campaign identity resolution and hierarchy checks."""

from __future__ import annotations

from app.core.contracts import utc_now
from app.identity_graph.contracts import (
    CampaignExternalBinding,
    CampaignIdentityHandoff,
    CampaignIdentityResolution,
    CampaignTrackingBinding,
    CanonicalCampaign,
    CustomCampaignIdentifierRule,
    ObservedCampaignSignals,
)
from app.identity_graph.enums import (
    BindingStatus,
    CampaignIdentitySource,
    ResolutionAuthority,
    TrackingKind,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.fingerprint import identity_fingerprint
from app.identity_graph.ids import new_resolution_id

_ACTIVE_TRACKING = {BindingStatus.ACTIVE, BindingStatus.CONFIRMED, BindingStatus.APPROVED}
_CONFIRMED_EXTERNAL = {BindingStatus.CONFIRMED, BindingStatus.ACTIVE}
_APPROVED_CUSTOM = {BindingStatus.APPROVED}
_USER_CONFIRMED = {BindingStatus.CONFIRMED, BindingStatus.APPROVED}
_CUSTOM_KINDS = {TrackingKind.CUSTOM_EVENT_PARAM, TrackingKind.CUSTOM_QUERY_PARAM}


def assert_not_self_parent(node_id: str, parent_id: str | None) -> None:
    if parent_id is not None and parent_id == node_id:
        raise IdentityGraphError(
            "A node cannot parent itself.",
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


def binding_in_effect(*, start: str | None, end: str | None, observed_at: str | None) -> bool:
    if observed_at is None:
        return True
    if start and observed_at < start:
        return False
    if end and observed_at > end:
        return False
    return True


def _hit(
    campaign_id: str, source: CampaignIdentitySource, binding_id: str
) -> tuple[str, CampaignIdentitySource, str]:
    return (campaign_id, source, binding_id)


def resolve_campaign_identity(
    *,
    campaigns: list[CanonicalCampaign],
    tracking: list[CampaignTrackingBinding],
    external: list[CampaignExternalBinding],
    signals: ObservedCampaignSignals,
    custom_rules: list[CustomCampaignIdentifierRule] | None = None,
    tenant_id: str = "",
    project_id: str = "",
    observation_id: str | None = None,
) -> CampaignIdentityResolution:
    """Precedence: PreM3 utm_id, confirmed external, approved custom, user-confirmed, unresolved.

    Fuzzy names never resolve. Conflicting exact campaign IDs require review.
    """
    del campaigns
    observed_at = signals.observed_at
    rules = custom_rules or []
    hits: list[tuple[str, CampaignIdentitySource, str]] = []

    if signals.utm_id:
        for binding in tracking:
            if (
                binding.tracking_kind == TrackingKind.PREM3_UTM_ID
                and binding.status in _ACTIVE_TRACKING
                and binding.parameter_name == "utm_id"
                and binding.parameter_value == signals.utm_id
                and binding_in_effect(
                    start=binding.effective_start,
                    end=binding.effective_end,
                    observed_at=observed_at,
                )
            ):
                hits.append(
                    _hit(
                        binding.campaign_id,
                        CampaignIdentitySource.PREM3_UTM_ID,
                        binding.tracking_binding_id,
                    )
                )

    if signals.provider_id and signals.external_campaign_id:
        account = signals.external_account_id or ""
        for binding in external:
            if binding.status not in _CONFIRMED_EXTERNAL:
                continue
            if not binding_in_effect(
                start=binding.effective_start,
                end=binding.effective_end,
                observed_at=observed_at,
            ):
                continue
            if binding.provider_id != signals.provider_id:
                continue
            if (binding.external_account_id or "") != account:
                continue
            if binding.external_campaign_id != signals.external_campaign_id:
                continue
            hits.append(
                _hit(
                    binding.campaign_id,
                    CampaignIdentitySource.EXTERNAL_CAMPAIGN_BINDING,
                    binding.binding_id,
                )
            )

    if signals.custom_parameter_name and signals.custom_parameter_value:
        custom_hits = [
            binding
            for binding in tracking
            if binding.tracking_kind in _CUSTOM_KINDS
            and binding.parameter_name == signals.custom_parameter_name
            and binding.parameter_value == signals.custom_parameter_value
            and binding_in_effect(
                start=binding.effective_start,
                end=binding.effective_end,
                observed_at=observed_at,
            )
        ]
        if custom_hits and not all(item.status in _APPROVED_CUSTOM for item in custom_hits):
            return _resolution(
                campaign_id=None,
                source=CampaignIdentitySource.CUSTOM_IDENTIFIER,
                status=ResolutionAuthority.REVIEW_REQUIRED,
                issues=("CUSTOM_IDENTIFIER_NOT_APPROVED",),
                signals=signals,
                tenant_id=tenant_id,
                project_id=project_id,
                observation_id=observation_id,
            )
        approved_rules = [
            rule
            for rule in rules
            if rule.parameter_name == signals.custom_parameter_name
            and rule.status in _APPROVED_CUSTOM
            and binding_in_effect(
                start=rule.effective_start,
                end=rule.effective_end,
                observed_at=observed_at,
            )
        ]
        if rules and custom_hits and not approved_rules:
            return _resolution(
                campaign_id=None,
                source=CampaignIdentitySource.CUSTOM_IDENTIFIER,
                status=ResolutionAuthority.REVIEW_REQUIRED,
                issues=("CUSTOM_IDENTIFIER_NOT_APPROVED",),
                signals=signals,
                tenant_id=tenant_id,
                project_id=project_id,
                observation_id=observation_id,
            )
        for binding in custom_hits:
            hits.append(
                _hit(
                    binding.campaign_id,
                    CampaignIdentitySource.CUSTOM_IDENTIFIER,
                    binding.tracking_binding_id,
                )
            )

    if signals.user_confirmed_campaign_id:
        confirmed = [
            binding
            for binding in tracking
            if binding.tracking_kind == TrackingKind.MANUAL_MAPPING
            and binding.status in _USER_CONFIRMED
            and binding.campaign_id == signals.user_confirmed_campaign_id
            and binding_in_effect(
                start=binding.effective_start,
                end=binding.effective_end,
                observed_at=observed_at,
            )
        ]
        if confirmed:
            hits.append(
                _hit(
                    signals.user_confirmed_campaign_id,
                    CampaignIdentitySource.USER_CONFIRMED_MAPPING,
                    confirmed[0].tracking_binding_id,
                )
            )

    # signals.fuzzy_name and utm_campaign are display context only and never become hits.

    matched_ids = tuple(dict.fromkeys(item[2] for item in hits))
    if not hits:
        return _resolution(
            campaign_id=None,
            source=CampaignIdentitySource.UNRESOLVED,
            status=ResolutionAuthority.UNRESOLVED,
            signals=signals,
            tenant_id=tenant_id,
            project_id=project_id,
            observation_id=observation_id,
        )

    campaign_ids = {item[0] for item in hits}
    if len(campaign_ids) > 1:
        return _resolution(
            campaign_id=None,
            source=CampaignIdentitySource.UNRESOLVED,
            status=ResolutionAuthority.REVIEW_REQUIRED,
            issues=("CONFLICTING_EXACT_BINDINGS", "BINDING_CONFLICT"),
            matched_binding_ids=matched_ids,
            conflicting_binding_ids=matched_ids,
            signals=signals,
            tenant_id=tenant_id,
            project_id=project_id,
            observation_id=observation_id,
        )

    precedence = [
        CampaignIdentitySource.PREM3_UTM_ID,
        CampaignIdentitySource.EXTERNAL_CAMPAIGN_BINDING,
        CampaignIdentitySource.CUSTOM_IDENTIFIER,
        CampaignIdentitySource.USER_CONFIRMED_MAPPING,
    ]
    source = next(item for item in precedence if item in {hit[1] for hit in hits})
    return _resolution(
        campaign_id=next(iter(campaign_ids)),
        source=source,
        status=ResolutionAuthority.RESOLVED,
        matched_binding_ids=matched_ids,
        signals=signals,
        tenant_id=tenant_id,
        project_id=project_id,
        observation_id=observation_id,
    )


def _resolution(
    *,
    campaign_id: str | None,
    source: CampaignIdentitySource,
    status: ResolutionAuthority,
    signals: ObservedCampaignSignals,
    tenant_id: str,
    project_id: str,
    observation_id: str | None,
    issues: tuple[str, ...] = (),
    matched_binding_ids: tuple[str, ...] = (),
    conflicting_binding_ids: tuple[str, ...] = (),
) -> CampaignIdentityResolution:
    resolved = CampaignIdentityResolution(
        campaign_id=campaign_id,
        source=source,
        status=status,
        resolution_id=new_resolution_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        observation_id=observation_id,
        resolution_method=source,
        matched_binding_ids=matched_binding_ids,
        conflicting_binding_ids=conflicting_binding_ids,
        issues=issues,
        campaign_name_raw=signals.external_campaign_name,
        external_campaign_name=signals.external_campaign_name,
        utm_campaign=signals.utm_campaign,
        resolved_at=utc_now(),
    )
    return resolved.model_copy(update={"fingerprint": identity_fingerprint(resolved)})


class CampaignIdentityResolver:
    """Central deterministic matcher. HTTP routers must not fork this logic."""

    def resolve(
        self,
        *,
        campaigns: list[CanonicalCampaign],
        tracking: list[CampaignTrackingBinding],
        external: list[CampaignExternalBinding],
        signals: ObservedCampaignSignals,
        custom_rules: list[CustomCampaignIdentifierRule] | None = None,
        tenant_id: str = "",
        project_id: str = "",
        observation_id: str | None = None,
    ) -> CampaignIdentityResolution:
        return resolve_campaign_identity(
            campaigns=campaigns,
            tracking=tracking,
            external=external,
            signals=signals,
            custom_rules=custom_rules,
            tenant_id=tenant_id,
            project_id=project_id,
            observation_id=observation_id,
        )

    def handoff(
        self,
        *,
        resolution: CampaignIdentityResolution,
        campaign: CanonicalCampaign | None,
        signals: ObservedCampaignSignals,
        audience_id: str | None = None,
        audience_binding_id: str | None = None,
        source_ref: str | None = None,
    ) -> CampaignIdentityHandoff:
        campaign_binding_id = next(
            (
                item
                for item in resolution.matched_binding_ids
                if item.startswith("igb_")
            ),
            None,
        )
        tracking_binding_id = next(
            (
                item
                for item in resolution.matched_binding_ids
                if item.startswith("igt_")
            ),
            None,
        )
        return CampaignIdentityHandoff(
            campaign_id=resolution.campaign_id,
            parent_campaign_id=campaign.parent_campaign_id if campaign else None,
            campaign_identity_source=resolution.source,
            campaign_binding_id=campaign_binding_id,
            tracking_binding_id=tracking_binding_id,
            resolution_status=resolution.status,
            resolution_fingerprint=resolution.fingerprint,
            provider_id=signals.provider_id,
            provider_account_id=signals.external_account_id,
            external_campaign_id=signals.external_campaign_id,
            utm_id=signals.utm_id,
            utm_campaign=signals.utm_campaign,
            custom_identifier=signals.custom_parameter_value,
            audience_id=audience_id,
            audience_binding_id=audience_binding_id,
            source_ref=source_ref,
        )
