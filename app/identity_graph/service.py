"""Project-scoped Marketing Identity Graph service. In-memory contract behavior for IG-00."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.business_iq.store import BusinessIqStore
from app.core.errors import InvalidResourceIdentifierError
from app.core.tenancy import require_tenant
from app.domain.channels.registry import cached_channel_registry
from app.domain.channels.validation import ChannelValidationError, assert_channel_id_in_registry
from app.identity_graph.contracts import (
    AudienceBindingCoverage,
    AudienceExternalBinding,
    AudienceLedgerValidationReceipt,
    AudienceLineage,
    BusinessMarketBinding,
    CampaignCreateResult,
    CampaignExternalBinding,
    CampaignIdentityHandoff,
    CampaignIdentityResolution,
    CampaignLedgerValidationReceipt,
    CampaignLineage,
    CampaignTrackingBinding,
    CampaignTrackingInstructions,
    CanonicalAudience,
    CanonicalCampaign,
    CanonicalMarket,
    CanonicalPersona,
    CustomCampaignIdentifierRule,
    GA4MarketCoverage,
    GA4PropertySourceBinding,
    GA4SourceTopology,
    GA4TopologyDiscoveryResult,
    GA4TopologyReadinessReceipt,
    IdentityCoverageReadModel,
    IdentityGraphOverview,
    MarketResolutionEvidence,
    MarketResolutionPolicy,
    MTAIdentityTouchpointRefs,
    ObservedCampaignSignals,
    PersonaLedgerValidationReceipt,
    TrackingObservation,
    TrackingVerificationReceipt,
)
from app.identity_graph.discovery import ProviderDiscovery, UnconfiguredProviderDiscovery
from app.identity_graph.enums import (
    AudienceRefreshCadence,
    AudienceSourceKind,
    AudienceStatus,
    AudienceType,
    BindingStatus,
    BqLocationClass,
    CampaignIdentitySource,
    CampaignOwnerType,
    CampaignStatus,
    CustomIdentifierCanonicalRole,
    CustomIdentifierScope,
    GA4TopologyKind,
    GA4TopologyReadinessState,
    IdentityGraphCapabilityState,
    IdentityGraphComponentState,
    IdentitySourceAuthority,
    MappingMethod,
    MarketCoverageStatus,
    MarketingIdentityEdgeType,
    MarketingIdentityNodeType,
    MarketKind,
    MarketMappingMethod,
    MarketResolutionMethod,
    MarketStatus,
    ObservationSourceKind,
    ObservationStatus,
    ObservedIdentifierKind,
    PersonaStatus,
    ResolutionAuthority,
    SourceOverlapPolicy,
    TopologyStatus,
    TrackingImplementationStatus,
    TrackingInstructionProvenance,
    TrackingKind,
    VerificationStatus,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.fingerprint import identity_fingerprint
from app.identity_graph.ids import (
    assert_audience_id_shape,
    assert_campaign_id_shape,
    assert_market_id_shape,
    assert_persona_id_shape,
    new_audience_id,
    new_binding_id,
    new_campaign_id,
    new_edge_id,
    new_ga4_source_binding_id,
    new_market_id,
    new_observation_id,
    new_persona_id,
    new_policy_id,
    new_receipt_id,
    new_rule_id,
    new_topology_id,
    new_tracking_binding_id,
)
from app.identity_graph.ledgers import (
    assert_audience_status_transition,
    assert_persona_status_transition,
    ledger_state_from_receipts,
    validate_source_ref,
    would_create_audience_cycle,
)
from app.identity_graph.relationships import MarketingIdentityEdge
from app.identity_graph.resolution import (
    CampaignIdentityResolver,
    assert_not_self_parent,
    assert_parent_same_project,
    would_create_cycle,
)
from app.identity_graph.store import IdentityGraphStore, InMemoryIdentityGraphStore
from app.registry.loader import load_registry


def require_canonical_provider_id(provider_id: str) -> None:
    catalog = load_registry()
    if not any(entry.provider_id == provider_id for entry in catalog.providers):
        raise IdentityGraphError(
            f"Unknown provider_id {provider_id!r} is not in the provider registry.",
            code="UNKNOWN_PROVIDER",
        )


def assert_authority_not_silently_verified(
    current: IdentitySourceAuthority, proposed: IdentitySourceAuthority
) -> None:
    if (
        current == IdentitySourceAuthority.PROVIDER_DISCOVERED
        and proposed == IdentitySourceAuthority.SYSTEM_VERIFIED
    ):
        raise IdentityGraphError(
            "PROVIDER_DISCOVERED cannot become SYSTEM_VERIFIED without confirmation.",
            code="AUTHORITY_PROMOTION_FORBIDDEN",
        )


_GEO_LEVEL_TO_KIND = {
    "COUNTRY": MarketKind.COUNTRY,
    "REGION": MarketKind.REGION,
    "MULTI_COUNTRY_REGION": MarketKind.MULTI_COUNTRY_REGION,
    "SUBNATIONAL": MarketKind.SUBNATIONAL,
    "GLOBAL": MarketKind.GLOBAL,
    "CUSTOM": MarketKind.CUSTOM,
}

_UNEVIDENCED_TRACKING = frozenset(
    {
        TrackingImplementationStatus.OBSERVED,
        TrackingImplementationStatus.VERIFIED,
    }
)

_STATUS_TRANSITIONS: dict[CampaignStatus, frozenset[CampaignStatus]] = {
    CampaignStatus.PLANNED: frozenset({CampaignStatus.ACTIVE, CampaignStatus.ARCHIVED}),
    CampaignStatus.ACTIVE: frozenset(
        {CampaignStatus.PAUSED, CampaignStatus.COMPLETE, CampaignStatus.ARCHIVED}
    ),
    CampaignStatus.PAUSED: frozenset(
        {CampaignStatus.ACTIVE, CampaignStatus.COMPLETE, CampaignStatus.ARCHIVED}
    ),
    CampaignStatus.COMPLETE: frozenset({CampaignStatus.ARCHIVED}),
    CampaignStatus.ARCHIVED: frozenset(),
}


def _market_kind_from_biq(geo_level: str | None) -> MarketKind:
    if geo_level is None:
        return MarketKind.CUSTOM
    return _GEO_LEVEL_TO_KIND.get(geo_level.upper(), MarketKind.CUSTOM)


def _validate_planned_dates(start: str | None, end: str | None) -> None:
    if start is None or end is None:
        return
    if end < start:
        raise IdentityGraphError(
            "planned_end_date must be on or after planned_start_date.",
            code="DATE_ORDER",
        )


def _planned_dates_overlap(
    start: str | None,
    end: str | None,
    window_start: str | None,
    window_end: str | None,
) -> bool:
    if window_start is None and window_end is None:
        return True
    if start is None and end is None:
        return True
    campaign_start = start or "0000-01-01"
    campaign_end = end or "9999-12-31"
    query_start = window_start or "0000-01-01"
    query_end = window_end or "9999-12-31"
    return campaign_start <= query_end and campaign_end >= query_start


class CampaignIdentityService:
    def __init__(
        self,
        *,
        store: IdentityGraphStore | None = None,
        business_iq_store: BusinessIqStore | None = None,
        provider_discovery: ProviderDiscovery | None = None,
    ) -> None:
        self.store = store or InMemoryIdentityGraphStore()
        self.business_iq_store = business_iq_store
        self.resolver = CampaignIdentityResolver()
        self.provider_discovery = provider_discovery or UnconfiguredProviderDiscovery()

    def create_campaign(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        description: str | None = None,
        status: CampaignStatus = CampaignStatus.PLANNED,
        market_ids: tuple[str, ...] = (),
        channel_ids: tuple[str, ...] = (),
        parent_campaign_id: str | None = None,
        planned_start_date: str | None = None,
        planned_end_date: str | None = None,
        utm_campaign: str | None = None,
        campaign_name_raw: str | None = None,
        owner_type: CampaignOwnerType | None = None,
        owner_ref: str | None = None,
        owner_label: str | None = None,
        objective_ref: str | None = None,
        objective_label: str | None = None,
        persona_ids: tuple[str, ...] = (),
        audience_ids: tuple[str, ...] = (),
    ) -> CampaignCreateResult:
        self._authorize(tenant_id)
        campaign_id = new_campaign_id(issued=self.store.issued_campaign_ids())
        now = datetime.now(UTC)
        campaign = CanonicalCampaign(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            project_id=project_id,
            parent_campaign_id=None,
            name=name,
            campaign_name_raw=campaign_name_raw or name,
            description=description,
            status=status,
            market_ids=market_ids,
            channel_ids=channel_ids,
            persona_ids=persona_ids,
            audience_ids=audience_ids,
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
            owner_type=owner_type,
            owner_ref=owner_ref,
            owner_label=owner_label,
            objective_ref=objective_ref,
            objective_label=objective_label,
            campaign_id_authority=IdentitySourceAuthority.PREM3_GENERATED,
            market_scope_authority=IdentitySourceAuthority.USER_DECLARED,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        self._validate_create_payload(campaign)
        if parent_campaign_id is not None:
            campaign = campaign.model_copy(update={"parent_campaign_id": parent_campaign_id})
            self._validate_parent(campaign)
        campaign = campaign.model_copy(update={"fingerprint": identity_fingerprint(campaign)})
        self.store.put_campaign(campaign)
        tracking = self._default_utm_binding(campaign, actor_id=actor_id)
        self.store.put_tracking(tracking)
        self._write_campaign_edges(campaign, tracking)
        instructions = self._mint_tracking_instructions(
            campaign, display=utm_campaign or name, generated_at=now
        )
        self.store.put_tracking_instructions(instructions)
        self.validate_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        return CampaignCreateResult(
            campaign=campaign, tracking=tracking, instructions=instructions
        )

    def get_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign:
        self._authorize(tenant_id)
        return self._require_campaign(tenant_id, project_id, campaign_id)

    def list_campaigns(
        self,
        *,
        tenant_id: str,
        project_id: str,
        status: CampaignStatus | None = None,
        market_id: str | None = None,
        channel_id: str | None = None,
        parent_campaign_id: str | None = None,
        planned_start_date: str | None = None,
        planned_end_date: str | None = None,
        owner_ref: str | None = None,
    ) -> list[CanonicalCampaign]:
        self._authorize(tenant_id)
        rows = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        if status is not None:
            rows = [item for item in rows if item.status == status]
        if market_id is not None:
            rows = [item for item in rows if market_id in item.market_ids]
        if channel_id is not None:
            rows = [item for item in rows if channel_id in item.channel_ids]
        if parent_campaign_id is not None:
            rows = [item for item in rows if item.parent_campaign_id == parent_campaign_id]
        if owner_ref is not None:
            rows = [item for item in rows if item.owner_ref == owner_ref]
        if planned_start_date is not None or planned_end_date is not None:
            rows = [
                item
                for item in rows
                if _planned_dates_overlap(
                    item.planned_start_date,
                    item.planned_end_date,
                    planned_start_date,
                    planned_end_date,
                )
            ]
        return rows

    def update_campaign(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        updates: dict[str, Any],
    ) -> CanonicalCampaign:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        allowed = {
            "name",
            "description",
            "status",
            "market_ids",
            "channel_ids",
            "parent_campaign_id",
            "planned_start_date",
            "planned_end_date",
            "owner_type",
            "owner_ref",
            "owner_label",
            "objective_ref",
            "objective_label",
            "persona_ids",
            "audience_ids",
            "utm_campaign",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise IdentityGraphError(
                f"Unsupported campaign update fields: {', '.join(sorted(unknown))}.",
                code="UNSUPPORTED_UPDATE",
            )
        patch: dict[str, Any] = {}
        utm_campaign = updates.pop("utm_campaign", None) if "utm_campaign" in updates else None
        for key, value in updates.items():
            if key in {"market_ids", "channel_ids", "persona_ids", "audience_ids"}:
                patch[key] = tuple(value) if value is not None else ()
            elif key == "status":
                next_status = value if isinstance(value, CampaignStatus) else CampaignStatus(value)
                self._assert_status_transition(campaign.status, next_status)
                patch["status"] = next_status
            elif key == "owner_type":
                patch["owner_type"] = (
                    None
                    if value is None
                    else value
                    if isinstance(value, CampaignOwnerType)
                    else CampaignOwnerType(value)
                )
            else:
                patch[key] = value
        if "name" in patch:
            patch["campaign_name_raw"] = patch["name"]
        patch["updated_at"] = datetime.now(UTC)
        updated = campaign.model_copy(update=patch)
        self._validate_create_payload(updated, require_scope=True)
        if updated.parent_campaign_id is not None:
            self._validate_parent(updated)
        elif "parent_campaign_id" in patch and updated.parent_campaign_id is None:
            pass
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_campaign(updated)
        if updated.parent_campaign_id != campaign.parent_campaign_id:
            self._replace_child_edge(updated)
        if (
            updated.persona_ids != campaign.persona_ids
            or updated.audience_ids != campaign.audience_ids
        ):
            self._sync_campaign_target_edges(updated)
        instructions = self.store.get_tracking_instructions(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if instructions is not None and ("name" in patch or utm_campaign is not None):
            display = utm_campaign or updated.name
            refreshed = instructions.model_copy(
                update={
                    "utm_campaign": display,
                    "recommended_utm_campaign": display,
                    "query_parameters": {
                        **instructions.query_parameters,
                        "utm_id": updated.campaign_id,
                        "utm_campaign": display,
                    },
                }
            )
            refreshed = refreshed.model_copy(
                update={"fingerprint": identity_fingerprint(refreshed)}
            )
            self.store.put_tracking_instructions(refreshed)
        self.validate_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        return updated

    def tracking_instructions(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignTrackingInstructions:
        self._authorize(tenant_id)
        self._require_campaign(tenant_id, project_id, campaign_id)
        found = self.store.get_tracking_instructions(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Tracking instructions missing for {campaign_id}.",
                code="TRACKING_MISSING",
            )
        if found.implementation_status in _UNEVIDENCED_TRACKING:
            if not self._tracking_status_evidenced(
                tenant_id=tenant_id,
                project_id=project_id,
                campaign_id=campaign_id,
                status=found.implementation_status,
            ):
                raise IdentityGraphError(
                    "Observed or verified tracking requires IG-03 evidence.",
                    code="TRACKING_STATUS_UNEVIDENCED",
                )
        return found

    def children(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> tuple[CanonicalCampaign, ...]:
        self._authorize(tenant_id)
        self._require_campaign(tenant_id, project_id, campaign_id)
        return tuple(
            item
            for item in self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
            if item.parent_campaign_id == campaign_id
        )

    def lineage(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignLineage:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        ancestors: list[str] = []
        seen: set[str] = set()
        current = campaign.parent_campaign_id
        while current and current not in seen:
            seen.add(current)
            parent = self.store.get_campaign(
                tenant_id=tenant_id, project_id=project_id, campaign_id=current
            )
            if parent is None:
                break
            ancestors.append(parent.campaign_id)
            current = parent.parent_campaign_id
        child_ids = tuple(item.campaign_id for item in self.children(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        ))
        return CampaignLineage(
            campaign_id=campaign.campaign_id,
            parent_campaign_id=campaign.parent_campaign_id,
            ancestors=tuple(ancestors),
            children=child_ids,
        )

    def validate_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> CampaignLedgerValidationReceipt:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        issues: list[str] = []
        campaign_id_valid = True
        try:
            assert_campaign_id_shape(campaign.campaign_id)
        except (ValueError, InvalidResourceIdentifierError):
            campaign_id_valid = False
            issues.append("CAMPAIGN_ID_SHAPE")
        project_scoped = (
            campaign.tenant_id == tenant_id and campaign.project_id == project_id
        )
        if not project_scoped:
            issues.append("PROJECT_SCOPE")
        markets_known = True
        channels_known = True
        dates_valid = True
        hierarchy_valid = True
        try:
            self._validate_markets_required(campaign.market_ids)
            self._validate_markets(tenant_id, project_id, campaign.market_ids)
        except IdentityGraphError as exc:
            markets_known = False
            issues.append(exc.code)
        try:
            self._validate_channels_required(campaign.channel_ids)
            self._validate_channels(campaign.channel_ids)
        except IdentityGraphError as exc:
            channels_known = False
            issues.append(exc.code)
        try:
            _validate_planned_dates(campaign.planned_start_date, campaign.planned_end_date)
        except IdentityGraphError:
            dates_valid = False
            issues.append("DATE_ORDER")
        try:
            if campaign.parent_campaign_id is not None:
                self._validate_parent(campaign)
        except IdentityGraphError as exc:
            hierarchy_valid = False
            issues.append(exc.code)
        try:
            CampaignStatus(campaign.status)
            status_valid = True
        except ValueError:
            status_valid = False
            issues.append("STATUS_INVALID")
        instructions = self.store.get_tracking_instructions(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        tracking_present = (
            instructions is not None
            and instructions.utm_id == campaign.campaign_id
            and instructions.parameter_name == "utm_id"
            and instructions.parameter_value == campaign.campaign_id
        )
        if not tracking_present:
            issues.append("TRACKING_INSTRUCTION")
        if (
            instructions is not None
            and instructions.implementation_status in _UNEVIDENCED_TRACKING
            and not self._tracking_status_evidenced(
                tenant_id=tenant_id,
                project_id=project_id,
                campaign_id=campaign_id,
                status=instructions.implementation_status,
            )
        ):
            issues.append("TRACKING_STATUS_UNEVIDENCED")
        if issues:
            if "TRACKING_STATUS_UNEVIDENCED" in issues or "HIERARCHY_CYCLE" in issues:
                state = IdentityGraphCapabilityState.REVIEW_REQUIRED
            else:
                state = IdentityGraphCapabilityState.PARTIAL
        else:
            state = IdentityGraphCapabilityState.READY
        receipt = CampaignLedgerValidationReceipt(
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign.campaign_id,
            state=state,
            campaign_id_valid=campaign_id_valid,
            project_scoped=project_scoped,
            markets_known=markets_known,
            channels_known=channels_known,
            dates_valid=dates_valid,
            hierarchy_valid=hierarchy_valid,
            status_valid=status_valid,
            tracking_instruction_present=tracking_present,
            prohibited_fields_absent=True,
            issues=tuple(dict.fromkeys(issues)),
        )
        receipt = receipt.model_copy(update={"fingerprint": identity_fingerprint(receipt)})
        return self.store.put_campaign_receipt(receipt)

    def delete_campaign(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> None:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        externals = self.store.list_external(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        child_rows = self.children(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        extra_tracking = [
            item
            for item in self.store.list_tracking(
                tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
            )
            if item.tracking_kind != TrackingKind.PREM3_UTM_ID
        ]
        referenced = bool(externals or child_rows or extra_tracking)
        if campaign.status != CampaignStatus.PLANNED or referenced:
            raise IdentityGraphError(
                "Hard delete is only allowed for never-referenced drafts; archive instead.",
                code="CAMPAIGN_REFERENCED",
            )
        self.store.delete_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )

    def create_persona(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        description: str | None = None,
        status: PersonaStatus = PersonaStatus.DRAFT,
        market_ids: tuple[str, ...] = (),
        lifecycle_stage_refs: tuple[str, ...] = (),
        business_segment_ref: str | None = None,
        business_profile_snapshot_id: str | None = None,
        owner_type: CampaignOwnerType | None = None,
        owner_ref: str | None = None,
        owner_label: str | None = None,
    ) -> CanonicalPersona:
        self._authorize(tenant_id)
        self._require_name(name)
        now = datetime.now(UTC)
        persona = CanonicalPersona(
            persona_id=new_persona_id(issued=self.store.issued_persona_ids()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            status=status,
            market_ids=market_ids,
            lifecycle_stage_refs=lifecycle_stage_refs,
            business_segment_ref=business_segment_ref,
            business_profile_snapshot_id=business_profile_snapshot_id,
            owner_type=owner_type,
            owner_ref=owner_ref,
            owner_label=owner_label,
            persona_id_authority=IdentitySourceAuthority.PREM3_GENERATED,
            market_scope_authority=IdentitySourceAuthority.USER_DECLARED,
            definition_authority=IdentitySourceAuthority.USER_DECLARED,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        self._validate_persona_payload(persona)
        persona = persona.model_copy(update={"fingerprint": identity_fingerprint(persona)})
        self.store.put_persona(persona)
        self.validate_persona(
            tenant_id=tenant_id, project_id=project_id, persona_id=persona.persona_id
        )
        return persona

    def get_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona:
        self._authorize(tenant_id)
        return self._require_persona(tenant_id, project_id, persona_id)

    def list_personas(
        self,
        *,
        tenant_id: str,
        project_id: str,
        status: PersonaStatus | None = None,
        market_id: str | None = None,
        owner_ref: str | None = None,
    ) -> list[CanonicalPersona]:
        self._authorize(tenant_id)
        rows = self.store.list_personas(tenant_id=tenant_id, project_id=project_id)
        if status is not None:
            rows = [item for item in rows if item.status == status]
        if market_id is not None:
            rows = [item for item in rows if market_id in item.market_ids]
        if owner_ref is not None:
            rows = [item for item in rows if item.owner_ref == owner_ref]
        return rows

    def update_persona(
        self,
        *,
        tenant_id: str,
        project_id: str,
        persona_id: str,
        updates: dict[str, Any],
    ) -> CanonicalPersona:
        self._authorize(tenant_id)
        persona = self._require_persona(tenant_id, project_id, persona_id)
        allowed = {
            "name",
            "description",
            "status",
            "market_ids",
            "lifecycle_stage_refs",
            "business_segment_ref",
            "business_profile_snapshot_id",
            "owner_type",
            "owner_ref",
            "owner_label",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise IdentityGraphError(
                f"Unsupported persona update fields: {', '.join(sorted(unknown))}.",
                code="UNSUPPORTED_UPDATE",
            )
        patch: dict[str, Any] = {}
        for key, value in updates.items():
            if key in {"market_ids", "lifecycle_stage_refs"}:
                patch[key] = tuple(value) if value is not None else ()
            elif key == "status":
                next_status = value if isinstance(value, PersonaStatus) else PersonaStatus(value)
                assert_persona_status_transition(persona.status, next_status)
                patch["status"] = next_status
            elif key == "owner_type":
                patch["owner_type"] = (
                    None
                    if value is None
                    else value
                    if isinstance(value, CampaignOwnerType)
                    else CampaignOwnerType(value)
                )
            elif key == "name":
                self._require_name(str(value) if value is not None else "")
                patch[key] = value
            else:
                patch[key] = value
        patch["updated_at"] = datetime.now(UTC)
        updated = persona.model_copy(update=patch)
        self._validate_persona_payload(updated)
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_persona(updated)
        self.validate_persona(
            tenant_id=tenant_id, project_id=project_id, persona_id=persona_id
        )
        return updated

    def archive_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona:
        return self.update_persona(
            tenant_id=tenant_id,
            project_id=project_id,
            persona_id=persona_id,
            updates={"status": PersonaStatus.ARCHIVED},
        )

    def delete_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> None:
        self._authorize(tenant_id)
        persona = self._require_persona(tenant_id, project_id, persona_id)
        referenced = self._persona_is_referenced(
            tenant_id=tenant_id, project_id=project_id, persona_id=persona_id
        )
        if persona.status != PersonaStatus.DRAFT or referenced:
            raise IdentityGraphError(
                "Hard delete is only allowed for never-referenced drafts; archive instead.",
                code="PERSONA_REFERENCED",
            )
        self.store.delete_persona(
            tenant_id=tenant_id, project_id=project_id, persona_id=persona_id
        )

    def persona_audiences(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> tuple[CanonicalAudience, ...]:
        self._authorize(tenant_id)
        self._require_persona(tenant_id, project_id, persona_id)
        return tuple(
            item
            for item in self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
            if persona_id in item.persona_ids
        )

    def persona_campaigns(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> tuple[CanonicalCampaign, ...]:
        self._authorize(tenant_id)
        self._require_persona(tenant_id, project_id, persona_id)
        return tuple(
            item
            for item in self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
            if persona_id in item.persona_ids
        )

    def validate_persona(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> PersonaLedgerValidationReceipt:
        self._authorize(tenant_id)
        persona = self._require_persona(tenant_id, project_id, persona_id)
        issues: list[str] = []
        persona_id_valid = True
        try:
            assert_persona_id_shape(persona.persona_id)
        except (ValueError, InvalidResourceIdentifierError):
            persona_id_valid = False
            issues.append("PERSONA_ID_SHAPE")
        project_scoped = persona.tenant_id == tenant_id and persona.project_id == project_id
        if not project_scoped:
            issues.append("PROJECT_SCOPE")
        markets_known = True
        try:
            if persona.market_ids:
                self._validate_markets(tenant_id, project_id, persona.market_ids)
        except IdentityGraphError as exc:
            markets_known = False
            issues.append(exc.code)
        snapshot_valid = True
        try:
            self._validate_biq_snapshot(persona.business_profile_snapshot_id)
        except IdentityGraphError as exc:
            snapshot_valid = False
            issues.append(exc.code)
        try:
            PersonaStatus(persona.status)
            status_valid = True
        except ValueError:
            status_valid = False
            issues.append("STATUS_INVALID")
        if issues:
            if "HIERARCHY_CYCLE" in issues:
                state = IdentityGraphCapabilityState.REVIEW_REQUIRED
            else:
                state = IdentityGraphCapabilityState.PARTIAL
        else:
            state = IdentityGraphCapabilityState.READY
        receipt = PersonaLedgerValidationReceipt(
            tenant_id=tenant_id,
            project_id=project_id,
            persona_id=persona.persona_id,
            state=state,
            persona_id_valid=persona_id_valid,
            project_scoped=project_scoped,
            markets_known=markets_known,
            snapshot_valid=snapshot_valid,
            status_valid=status_valid,
            prohibited_fields_absent=True,
            issues=tuple(dict.fromkeys(issues)),
        )
        receipt = receipt.model_copy(update={"fingerprint": identity_fingerprint(receipt)})
        return self.store.put_persona_receipt(receipt)

    def create_audience(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        audience_type: AudienceType,
        source_kind: AudienceSourceKind,
        description: str | None = None,
        status: AudienceStatus = AudienceStatus.DRAFT,
        source_ref: str | None = None,
        market_ids: tuple[str, ...] = (),
        persona_ids: tuple[str, ...] = (),
        parent_audience_id: str | None = None,
        definition_summary: str | None = None,
        criteria_summary: str | None = None,
        effective_start_date: str | None = None,
        effective_end_date: str | None = None,
        refresh_cadence: AudienceRefreshCadence | None = None,
        owner_type: CampaignOwnerType | None = None,
        owner_ref: str | None = None,
        owner_label: str | None = None,
    ) -> CanonicalAudience:
        self._authorize(tenant_id)
        self._require_name(name)
        now = datetime.now(UTC)
        source_authority = (
            IdentitySourceAuthority.BUSINESS_IQ_DEFINED
            if source_kind == AudienceSourceKind.BUSINESS_IQ_DEFINED
            else IdentitySourceAuthority.USER_DECLARED
        )
        audience = CanonicalAudience(
            audience_id=new_audience_id(issued=self.store.issued_audience_ids()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            status=status,
            audience_type=audience_type,
            source_kind=source_kind,
            source_ref=source_ref,
            market_ids=market_ids,
            persona_ids=persona_ids,
            parent_audience_id=None,
            definition_summary=definition_summary,
            criteria_summary=criteria_summary,
            effective_start_date=effective_start_date,
            effective_end_date=effective_end_date,
            refresh_cadence=refresh_cadence,
            owner_type=owner_type,
            owner_ref=owner_ref,
            owner_label=owner_label,
            audience_id_authority=IdentitySourceAuthority.PREM3_GENERATED,
            market_scope_authority=IdentitySourceAuthority.USER_DECLARED,
            source_authority=source_authority,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        self._validate_audience_payload(audience)
        if parent_audience_id is not None:
            audience = audience.model_copy(update={"parent_audience_id": parent_audience_id})
            self._validate_audience_parent(audience)
        audience = audience.model_copy(update={"fingerprint": identity_fingerprint(audience)})
        self.store.put_audience(audience)
        self._sync_audience_edges(audience)
        self.validate_audience(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience.audience_id
        )
        return audience

    def get_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience:
        self._authorize(tenant_id)
        return self._require_audience(tenant_id, project_id, audience_id)

    def list_audiences(
        self,
        *,
        tenant_id: str,
        project_id: str,
        status: AudienceStatus | None = None,
        audience_type: AudienceType | None = None,
        source_kind: AudienceSourceKind | None = None,
        market_id: str | None = None,
        persona_id: str | None = None,
        owner_ref: str | None = None,
        parent_audience_id: str | None = None,
        effective_start_date: str | None = None,
        effective_end_date: str | None = None,
    ) -> list[CanonicalAudience]:
        self._authorize(tenant_id)
        rows = self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
        if status is not None:
            rows = [item for item in rows if item.status == status]
        if audience_type is not None:
            rows = [item for item in rows if item.audience_type == audience_type]
        if source_kind is not None:
            rows = [item for item in rows if item.source_kind == source_kind]
        if market_id is not None:
            rows = [item for item in rows if market_id in item.market_ids]
        if persona_id is not None:
            rows = [item for item in rows if persona_id in item.persona_ids]
        if owner_ref is not None:
            rows = [item for item in rows if item.owner_ref == owner_ref]
        if parent_audience_id is not None:
            rows = [item for item in rows if item.parent_audience_id == parent_audience_id]
        if effective_start_date is not None or effective_end_date is not None:
            rows = [
                item
                for item in rows
                if _planned_dates_overlap(
                    item.effective_start_date,
                    item.effective_end_date,
                    effective_start_date,
                    effective_end_date,
                )
            ]
        return rows

    def update_audience(
        self,
        *,
        tenant_id: str,
        project_id: str,
        audience_id: str,
        updates: dict[str, Any],
    ) -> CanonicalAudience:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        allowed = {
            "name",
            "description",
            "status",
            "audience_type",
            "source_kind",
            "source_ref",
            "market_ids",
            "persona_ids",
            "parent_audience_id",
            "definition_summary",
            "criteria_summary",
            "effective_start_date",
            "effective_end_date",
            "refresh_cadence",
            "owner_type",
            "owner_ref",
            "owner_label",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise IdentityGraphError(
                f"Unsupported audience update fields: {', '.join(sorted(unknown))}.",
                code="UNSUPPORTED_UPDATE",
            )
        patch: dict[str, Any] = {}
        for key, value in updates.items():
            if key in {"market_ids", "persona_ids"}:
                patch[key] = tuple(value) if value is not None else ()
            elif key == "status":
                next_status = (
                    value if isinstance(value, AudienceStatus) else AudienceStatus(value)
                )
                assert_audience_status_transition(audience.status, next_status)
                patch["status"] = next_status
            elif key == "audience_type":
                patch["audience_type"] = (
                    value if isinstance(value, AudienceType) else AudienceType(value)
                )
            elif key == "source_kind":
                kind = value if isinstance(value, AudienceSourceKind) else AudienceSourceKind(value)
                patch["source_kind"] = kind
                patch["source_authority"] = (
                    IdentitySourceAuthority.BUSINESS_IQ_DEFINED
                    if kind == AudienceSourceKind.BUSINESS_IQ_DEFINED
                    else IdentitySourceAuthority.USER_DECLARED
                )
            elif key == "refresh_cadence":
                patch["refresh_cadence"] = (
                    None
                    if value is None
                    else value
                    if isinstance(value, AudienceRefreshCadence)
                    else AudienceRefreshCadence(value)
                )
            elif key == "owner_type":
                patch["owner_type"] = (
                    None
                    if value is None
                    else value
                    if isinstance(value, CampaignOwnerType)
                    else CampaignOwnerType(value)
                )
            elif key == "name":
                self._require_name(str(value) if value is not None else "")
                patch[key] = value
            else:
                patch[key] = value
        patch["updated_at"] = datetime.now(UTC)
        updated = audience.model_copy(update=patch)
        self._validate_audience_payload(updated)
        if updated.parent_audience_id is not None:
            self._validate_audience_parent(updated)
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_audience(updated)
        self._sync_audience_edges(updated)
        self.validate_audience(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )
        return updated

    def archive_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience:
        return self.update_audience(
            tenant_id=tenant_id,
            project_id=project_id,
            audience_id=audience_id,
            updates={"status": AudienceStatus.ARCHIVED},
        )

    def delete_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> None:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        referenced = self._audience_is_referenced(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )
        if audience.status != AudienceStatus.DRAFT or referenced:
            raise IdentityGraphError(
                "Hard delete is only allowed for never-referenced drafts; archive instead.",
                code="AUDIENCE_REFERENCED",
            )
        self.store.delete_audience(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )

    def audience_personas(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> tuple[CanonicalPersona, ...]:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        return tuple(
            self._require_persona(tenant_id, project_id, persona_id)
            for persona_id in audience.persona_ids
        )

    def audience_campaigns(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> tuple[CanonicalCampaign, ...]:
        self._authorize(tenant_id)
        self._require_audience(tenant_id, project_id, audience_id)
        return tuple(
            item
            for item in self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
            if audience_id in item.audience_ids
        )

    def audience_children(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> tuple[CanonicalAudience, ...]:
        self._authorize(tenant_id)
        self._require_audience(tenant_id, project_id, audience_id)
        return tuple(
            item
            for item in self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
            if item.parent_audience_id == audience_id
        )

    def audience_lineage(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceLineage:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        ancestors: list[str] = []
        seen: set[str] = set()
        current = audience.parent_audience_id
        while current and current not in seen:
            seen.add(current)
            parent = self.store.get_audience(
                tenant_id=tenant_id, project_id=project_id, audience_id=current
            )
            if parent is None:
                break
            ancestors.append(parent.audience_id)
            current = parent.parent_audience_id
        child_ids = tuple(
            item.audience_id
            for item in self.audience_children(
                tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
            )
        )
        return AudienceLineage(
            audience_id=audience.audience_id,
            parent_audience_id=audience.parent_audience_id,
            ancestors=tuple(ancestors),
            children=child_ids,
        )

    def validate_audience(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceLedgerValidationReceipt:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        issues: list[str] = []
        audience_id_valid = True
        try:
            assert_audience_id_shape(audience.audience_id)
        except (ValueError, InvalidResourceIdentifierError):
            audience_id_valid = False
            issues.append("AUDIENCE_ID_SHAPE")
        project_scoped = audience.tenant_id == tenant_id and audience.project_id == project_id
        if not project_scoped:
            issues.append("PROJECT_SCOPE")
        markets_known = True
        try:
            if audience.market_ids:
                self._validate_markets(tenant_id, project_id, audience.market_ids)
        except IdentityGraphError as exc:
            markets_known = False
            issues.append(exc.code)
        personas_known = True
        try:
            self._validate_audience_persona_ids(audience)
        except IdentityGraphError as exc:
            personas_known = False
            issues.append(exc.code)
        type_valid = True
        try:
            AudienceType(audience.audience_type)
        except ValueError:
            type_valid = False
            issues.append("AUDIENCE_TYPE_INVALID")
        source_valid = True
        try:
            AudienceSourceKind(audience.source_kind)
            validate_source_ref(audience.source_ref)
        except (ValueError, IdentityGraphError) as exc:
            source_valid = False
            issues.append(getattr(exc, "code", "SOURCE_INVALID"))
        dates_valid = True
        try:
            _validate_planned_dates(audience.effective_start_date, audience.effective_end_date)
        except IdentityGraphError:
            dates_valid = False
            issues.append("DATE_ORDER")
        hierarchy_valid = True
        try:
            if audience.parent_audience_id is not None:
                self._validate_audience_parent(audience)
        except IdentityGraphError as exc:
            hierarchy_valid = False
            issues.append(exc.code)
        try:
            AudienceStatus(audience.status)
            status_valid = True
        except ValueError:
            status_valid = False
            issues.append("STATUS_INVALID")
        if issues:
            if "HIERARCHY_CYCLE" in issues:
                state = IdentityGraphCapabilityState.REVIEW_REQUIRED
            else:
                state = IdentityGraphCapabilityState.PARTIAL
        else:
            state = IdentityGraphCapabilityState.READY
        receipt = AudienceLedgerValidationReceipt(
            tenant_id=tenant_id,
            project_id=project_id,
            audience_id=audience.audience_id,
            state=state,
            audience_id_valid=audience_id_valid,
            project_scoped=project_scoped,
            markets_known=markets_known,
            personas_known=personas_known,
            type_valid=type_valid,
            source_valid=source_valid,
            dates_valid=dates_valid,
            hierarchy_valid=hierarchy_valid,
            status_valid=status_valid,
            prohibited_fields_absent=True,
            issues=tuple(dict.fromkeys(issues)),
        )
        receipt = receipt.model_copy(update={"fingerprint": identity_fingerprint(receipt)})
        return self.store.put_audience_receipt(receipt)

    def create_market(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        actor_id: str,
        description: str | None = None,
        market_kind: MarketKind = MarketKind.CUSTOM,
        country_codes: tuple[str, ...] = (),
        region_codes: tuple[str, ...] = (),
        status: MarketStatus = MarketStatus.ACTIVE,
    ) -> CanonicalMarket:
        self._authorize(tenant_id)
        now = datetime.now(UTC)
        market = CanonicalMarket(
            market_id=new_market_id(issued=self.store.issued_market_ids()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            market_kind=market_kind,
            status=status,
            country_codes=country_codes,
            region_codes=region_codes,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        market = market.model_copy(update={"fingerprint": identity_fingerprint(market)})
        return self.store.put_market(market)

    def bind_business_iq_markets(
        self, *, tenant_id: str, project_id: str, actor_id: str
    ) -> list[BusinessMarketBinding]:
        self._authorize(tenant_id)
        if self.business_iq_store is None:
            raise IdentityGraphError(
                "Business IQ store is required to bind markets.",
                code="UNKNOWN_MARKET",
            )
        profile = self.business_iq_store.get_profile(
            tenant_id=tenant_id, workspace_id=project_id
        )
        if profile is None:
            raise IdentityGraphError(
                "Business profile not found.",
                code="UNKNOWN_MARKET",
            )
        snapshot_id = profile.current_snapshot_id
        created: list[BusinessMarketBinding] = []
        for market in profile.markets:
            existing = self.store.get_market_binding(
                tenant_id=tenant_id,
                project_id=project_id,
                snapshot_id=snapshot_id,
                business_market_ref=market.market_id,
            )
            if existing is not None:
                created.append(existing)
                continue
            reused_id = self._canonical_id_for_legacy_ref(
                tenant_id=tenant_id,
                project_id=project_id,
                business_market_ref=market.market_id,
            )
            if reused_id is not None:
                mapping_method = MarketMappingMethod.EXACT_EXISTING_BINDING
                canonical_id = reused_id
            else:
                canonical = self.create_market(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name=market.name,
                    actor_id=actor_id,
                    market_kind=_market_kind_from_biq(market.geo_level),
                    description=market.custom_text,
                )
                mapping_method = MarketMappingMethod.SERVER_CREATED_FROM_BUSINESS_IQ
                canonical_id = canonical.market_id
            binding = BusinessMarketBinding(
                binding_id=new_binding_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                business_profile_snapshot_id=snapshot_id,
                business_market_ref=market.market_id,
                market_id=canonical_id,
                mapping_method=mapping_method,
                status=BindingStatus.CONFIRMED,
                confirmed_by=actor_id,
                confirmed_at=datetime.now(UTC),
            )
            binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
            created.append(self.store.put_market_binding(binding))
        return created

    def review_legacy_market_name_merge(
        self, *, tenant_id: str, project_id: str, display_name: str
    ) -> ResolutionAuthority:
        self._authorize(tenant_id)
        canonical_matches = [
            market
            for market in self.store.list_canonical_markets(
                tenant_id=tenant_id, project_id=project_id
            )
            if market.name == display_name
        ]
        biq_matches: list[str] = []
        if self.business_iq_store is not None:
            profile = self.business_iq_store.get_profile(
                tenant_id=tenant_id, workspace_id=project_id
            )
            if profile is not None:
                biq_matches = [
                    item.market_id for item in profile.markets if item.name == display_name
                ]
        if len(canonical_matches) > 1 or len(set(biq_matches)) > 1:
            return ResolutionAuthority.REVIEW_REQUIRED
        return ResolutionAuthority.UNRESOLVED

    def list_market_bindings(
        self, *, tenant_id: str, project_id: str
    ) -> list[BusinessMarketBinding]:
        self._authorize(tenant_id)
        return self.store.list_market_bindings(tenant_id=tenant_id, project_id=project_id)

    def list_markets(self, *, tenant_id: str, project_id: str) -> list[CanonicalMarket]:
        self._authorize(tenant_id)
        return self.store.list_canonical_markets(tenant_id=tenant_id, project_id=project_id)

    def set_parent(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        parent_campaign_id: str | None,
    ) -> CanonicalCampaign:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        updated = campaign.model_copy(
            update={"parent_campaign_id": parent_campaign_id, "updated_at": datetime.now(UTC)}
        )
        if parent_campaign_id is not None:
            self._validate_parent(updated)
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_campaign(updated)
        self._replace_child_edge(updated)
        return updated

    def bind_external(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        provider_id: str,
        external_campaign_id: str,
        external_account_id: str | None = None,
        external_campaign_name: str | None = None,
        mapping_method: MappingMethod = MappingMethod.PROVIDER_ID_EXACT,
        status: BindingStatus = BindingStatus.CONFIRMED,
        actor_id: str = "",
        effective_start: str | None = None,
        effective_end: str | None = None,
        source_ref: str | None = None,
        external_parent_id: str | None = None,
        external_campaign_status: str | None = None,
        authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_CONFIRMED,
    ) -> CampaignExternalBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        require_canonical_provider_id(provider_id)
        self._assert_live_target_not_archived(
            entity_status=campaign.status.value,
            binding_status=status,
        )
        now = datetime.now(UTC)
        binding = CampaignExternalBinding(
            binding_id=new_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign.campaign_id,
            provider_id=provider_id,
            external_account_id=external_account_id,
            external_campaign_id=external_campaign_id,
            external_campaign_name=external_campaign_name,
            external_parent_id=external_parent_id,
            external_campaign_status=external_campaign_status,
            effective_start=effective_start,
            effective_end=effective_end,
            mapping_method=mapping_method,
            status=status,
            authority=authority,
            confirmed_by=actor_id or None,
            confirmed_at=now if status == BindingStatus.CONFIRMED else None,
            source_ref=source_ref,
            created_at=now,
            updated_at=now,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_external(binding)
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_BOUND_TO_EXTERNAL,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign_id,
                to_node_type=MarketingIdentityNodeType.EXTERNAL_CAMPAIGN,
                to_node_id=external_campaign_id,
            )
        )
        return binding

    def get_external_binding(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> CampaignExternalBinding:
        self._authorize(tenant_id)
        found = self.store.get_external(
            tenant_id=tenant_id, project_id=project_id, binding_id=binding_id
        )
        if found is None:
            raise IdentityGraphError("External binding not found.", code="UNKNOWN_BINDING")
        return found

    def list_campaign_bindings(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> list[CampaignExternalBinding]:
        self._authorize(tenant_id)
        self._require_campaign(tenant_id, project_id, campaign_id)
        return self.store.list_external(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )

    def update_external_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        binding_id: str,
        updates: dict[str, Any],
    ) -> CampaignExternalBinding:
        self._authorize(tenant_id)
        binding = self.get_external_binding(
            tenant_id=tenant_id, project_id=project_id, binding_id=binding_id
        )
        allowed = {
            "external_campaign_name",
            "external_campaign_status",
            "effective_start",
            "effective_end",
            "status",
            "source_ref",
            "authority",
        }
        payload = {key: value for key, value in updates.items() if key in allowed}
        if "status" in payload and payload["status"] is not None:
            if not isinstance(payload["status"], BindingStatus):
                payload["status"] = BindingStatus(payload["status"])
            campaign = self._require_campaign(tenant_id, project_id, binding.campaign_id)
            self._assert_live_target_not_archived(
                entity_status=campaign.status.value,
                binding_status=payload["status"],
            )
        updated = binding.model_copy(
            update={**payload, "updated_at": datetime.now(UTC)}
        )
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_external(updated)
        return updated

    def update_external_name(
        self,
        *,
        tenant_id: str,
        project_id: str,
        binding_id: str,
        external_campaign_name: str,
    ) -> CampaignExternalBinding:
        return self.update_external_binding(
            tenant_id=tenant_id,
            project_id=project_id,
            binding_id=binding_id,
            updates={"external_campaign_name": external_campaign_name},
        )

    def bind_audience_external(
        self,
        *,
        tenant_id: str,
        project_id: str,
        audience_id: str,
        provider_id: str,
        external_audience_id: str,
        external_account_id: str | None = None,
        external_audience_name: str | None = None,
        audience_implementation_type: str | None = None,
        mapping_method: MappingMethod = MappingMethod.PROVIDER_ID_EXACT,
        status: BindingStatus = BindingStatus.CONFIRMED,
        actor_id: str = "",
        effective_start: str | None = None,
        effective_end: str | None = None,
        source_ref: str | None = None,
        authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_CONFIRMED,
    ) -> AudienceExternalBinding:
        self._authorize(tenant_id)
        audience = self._require_audience(tenant_id, project_id, audience_id)
        require_canonical_provider_id(provider_id)
        self._assert_live_target_not_archived(
            entity_status=audience.status.value,
            binding_status=status,
        )
        now = datetime.now(UTC)
        binding = AudienceExternalBinding(
            binding_id=new_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            audience_id=audience.audience_id,
            provider_id=provider_id,
            external_account_id=external_account_id,
            external_audience_id=external_audience_id,
            external_audience_name=external_audience_name,
            audience_implementation_type=audience_implementation_type,
            effective_start=effective_start,
            effective_end=effective_end,
            mapping_method=mapping_method,
            status=status,
            authority=authority,
            confirmed_by=actor_id or None,
            confirmed_at=now if status == BindingStatus.CONFIRMED else None,
            source_ref=source_ref,
            created_at=now,
            updated_at=now,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_audience_external(binding)
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.AUDIENCE_BOUND_TO_EXTERNAL,
                from_node_type=MarketingIdentityNodeType.AUDIENCE,
                from_node_id=audience_id,
                to_node_type=MarketingIdentityNodeType.EXTERNAL_AUDIENCE,
                to_node_id=external_audience_id,
            )
        )
        return binding

    def create_audience_external_binding(self, **kwargs: Any) -> AudienceExternalBinding:
        return self.bind_audience_external(**kwargs)

    def get_audience_external_binding(
        self, *, tenant_id: str, project_id: str, binding_id: str
    ) -> AudienceExternalBinding:
        self._authorize(tenant_id)
        found = self.store.get_audience_external(
            tenant_id=tenant_id, project_id=project_id, binding_id=binding_id
        )
        if found is None:
            raise IdentityGraphError("External binding not found.", code="UNKNOWN_BINDING")
        return found

    def list_audience_external_bindings(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> list[AudienceExternalBinding]:
        self._authorize(tenant_id)
        self._require_audience(tenant_id, project_id, audience_id)
        return self.store.list_audience_external(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )

    def update_audience_external_binding(
        self,
        *,
        tenant_id: str,
        project_id: str,
        binding_id: str,
        updates: dict[str, Any],
    ) -> AudienceExternalBinding:
        self._authorize(tenant_id)
        binding = self.get_audience_external_binding(
            tenant_id=tenant_id, project_id=project_id, binding_id=binding_id
        )
        allowed = {
            "external_audience_name",
            "effective_start",
            "effective_end",
            "status",
            "source_ref",
            "authority",
            "audience_implementation_type",
        }
        payload = {key: value for key, value in updates.items() if key in allowed}
        if "status" in payload and payload["status"] is not None:
            if not isinstance(payload["status"], BindingStatus):
                payload["status"] = BindingStatus(payload["status"])
            audience = self._require_audience(tenant_id, project_id, binding.audience_id)
            self._assert_live_target_not_archived(
                entity_status=audience.status.value,
                binding_status=payload["status"],
            )
        updated = binding.model_copy(update={**payload, "updated_at": datetime.now(UTC)})
        updated = updated.model_copy(update={"fingerprint": identity_fingerprint(updated)})
        self.store.put_audience_external(updated)
        return updated

    def bind_custom_identifier(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        parameter_name: str,
        parameter_value: str,
        actor_id: str,
        status: BindingStatus = BindingStatus.APPROVED,
    ) -> CampaignTrackingBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        if status != BindingStatus.APPROVED:
            raise IdentityGraphError(
                "Custom identifier bindings require an explicit APPROVED rule.",
                code="CUSTOM_IDENTIFIER_NOT_APPROVED",
            )
        self.create_custom_identifier_rule(
            tenant_id=tenant_id,
            project_id=project_id,
            parameter_name=parameter_name,
            parameter_scope=CustomIdentifierScope.GA4_EVENT_PARAM,
            actor_id=actor_id,
            status=BindingStatus.APPROVED,
        )
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign.campaign_id,
            parameter_name=parameter_name,
            parameter_value=parameter_value,
            tracking_kind=TrackingKind.CUSTOM_EVENT_PARAM,
            status=status,
            authority=IdentitySourceAuthority.USER_CONFIRMED,
            created_by=actor_id,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_tracking(binding)
        return binding

    def bind_user_confirmed_mapping(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        actor_id: str,
    ) -> CampaignTrackingBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign.campaign_id,
            parameter_name="user_confirmed",
            parameter_value=campaign.campaign_id,
            tracking_kind=TrackingKind.MANUAL_MAPPING,
            status=BindingStatus.CONFIRMED,
            authority=IdentitySourceAuthority.USER_CONFIRMED,
            created_by=actor_id,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_tracking(binding)
        return binding

    def resolve_observed(
        self,
        *,
        tenant_id: str,
        project_id: str,
        signals: ObservedCampaignSignals,
    ) -> CampaignIdentityResolution:
        self._authorize(tenant_id)
        resolved = self.resolver.resolve(
            campaigns=self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id),
            tracking=self.store.list_tracking(tenant_id=tenant_id, project_id=project_id),
            external=self.store.list_external(tenant_id=tenant_id, project_id=project_id),
            signals=signals,
            custom_rules=self.store.list_custom_rules(tenant_id=tenant_id, project_id=project_id),
            tenant_id=tenant_id,
            project_id=project_id,
        )
        return self.store.put_resolution(resolved)

    def create_custom_identifier_rule(
        self,
        *,
        tenant_id: str,
        project_id: str,
        parameter_name: str,
        parameter_scope: CustomIdentifierScope,
        actor_id: str = "",
        status: BindingStatus = BindingStatus.APPROVED,
        source_kind: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED,
        effective_start: str | None = None,
        effective_end: str | None = None,
    ) -> CustomCampaignIdentifierRule:
        del actor_id
        self._authorize(tenant_id)
        if status != BindingStatus.APPROVED:
            raise IdentityGraphError(
                "Custom identifier bindings require an explicit APPROVED rule.",
                code="CUSTOM_IDENTIFIER_NOT_APPROVED",
            )
        now = datetime.now(UTC)
        rule = CustomCampaignIdentifierRule(
            rule_id=new_rule_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            parameter_name=parameter_name,
            parameter_scope=parameter_scope,
            canonical_role=CustomIdentifierCanonicalRole.CAMPAIGN_ID,
            source_kind=source_kind,
            effective_start=effective_start,
            effective_end=effective_end,
            status=status,
            authority=IdentitySourceAuthority.USER_CONFIRMED,
            created_at=now,
            updated_at=now,
        )
        rule = rule.model_copy(update={"fingerprint": identity_fingerprint(rule)})
        return self.store.put_custom_rule(rule)

    def bind_tracking(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        tracking_kind: TrackingKind,
        parameter_name: str,
        parameter_value: str,
        actor_id: str,
        status: BindingStatus = BindingStatus.ACTIVE,
        effective_start: str | None = None,
        effective_end: str | None = None,
    ) -> CampaignTrackingBinding:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        if tracking_kind == TrackingKind.PREM3_UTM_ID and parameter_value != campaign.campaign_id:
            raise IdentityGraphError(
                "utm_id tracking value must equal campaign_id.",
                code="TRACKING_VALUE_MISMATCH",
            )
        if tracking_kind in {
            TrackingKind.CUSTOM_EVENT_PARAM,
            TrackingKind.CUSTOM_QUERY_PARAM,
        } and status != BindingStatus.APPROVED:
            raise IdentityGraphError(
                "Custom identifier bindings require an explicit APPROVED rule.",
                code="CUSTOM_IDENTIFIER_NOT_APPROVED",
            )
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign.campaign_id,
            parameter_name=parameter_name,
            parameter_value=parameter_value,
            tracking_kind=tracking_kind,
            status=status,
            effective_start=effective_start,
            effective_end=effective_end,
            created_by=actor_id,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_tracking(binding)
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_TRACKED_BY,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign_id,
                to_node_type=MarketingIdentityNodeType.CAMPAIGN,
                to_node_id=binding.tracking_binding_id,
            )
        )
        return binding

    def observe_tracking(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_ref: str,
        source_kind: ObservationSourceKind,
        observed_at: str,
        identifier_kind: ObservedIdentifierKind,
        parameter_value: str,
        parameter_name: str | None = None,
        observation_window_start: str | None = None,
        observation_window_end: str | None = None,
        external_provider_id: str | None = None,
        external_account_id: str | None = None,
        external_campaign_id: str | None = None,
        candidate_campaign_id: str | None = None,
    ) -> TrackingObservation:
        self._authorize(tenant_id)
        if not source_ref.strip():
            raise IdentityGraphError(
                "Tracking observation requires a governed source_ref.",
                code="SOURCE_REF_REQUIRED",
            )
        observation = TrackingObservation(
            observation_id=new_observation_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            source_ref=source_ref,
            source_kind=source_kind,
            observed_at=observed_at,
            identifier_kind=identifier_kind,
            parameter_value=parameter_value,
            parameter_name=parameter_name,
            observation_window_start=observation_window_start,
            observation_window_end=observation_window_end,
            external_provider_id=external_provider_id,
            external_account_id=external_account_id,
            external_campaign_id=external_campaign_id,
            candidate_campaign_id=candidate_campaign_id,
            observation_status=ObservationStatus.RECORDED,
        )
        observation = observation.model_copy(
            update={"evidence_fingerprint": identity_fingerprint(observation)}
        )
        return self.store.put_observation(observation)

    def resolve_tracking(
        self,
        *,
        tenant_id: str,
        project_id: str,
        observation_id: str | None = None,
        signals: ObservedCampaignSignals | None = None,
    ) -> CampaignIdentityResolution:
        self._authorize(tenant_id)
        observation = None
        if observation_id is not None:
            observation = self.store.get_observation(
                tenant_id=tenant_id, project_id=project_id, observation_id=observation_id
            )
            if observation is None:
                raise IdentityGraphError(
                    "Tracking observation not found.",
                    code="UNKNOWN_OBSERVATION",
                )
            signals = self._signals_from_observation(observation)
        if signals is None:
            raise IdentityGraphError(
                "Resolution requires an observation_id or signals.",
                code="RESOLUTION_INPUT_REQUIRED",
            )
        resolved = self.resolver.resolve(
            campaigns=self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id),
            tracking=self.store.list_tracking(tenant_id=tenant_id, project_id=project_id),
            external=self.store.list_external(tenant_id=tenant_id, project_id=project_id),
            signals=signals,
            custom_rules=self.store.list_custom_rules(tenant_id=tenant_id, project_id=project_id),
            tenant_id=tenant_id,
            project_id=project_id,
            observation_id=observation_id,
        )
        return self.store.put_resolution(resolved)

    def verify_tracking(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        observation_id: str | None = None,
    ) -> TrackingVerificationReceipt:
        self._authorize(tenant_id)
        campaign = self._require_campaign(tenant_id, project_id, campaign_id)
        instructions = self.store.get_tracking_instructions(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        expected = campaign.campaign_id
        tracking_binding_id = None
        tracking_rows = self.store.list_tracking(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        utm = next(
            (item for item in tracking_rows if item.tracking_kind == TrackingKind.PREM3_UTM_ID),
            None,
        )
        if utm is not None:
            tracking_binding_id = utm.tracking_binding_id
        observations = self.store.list_observations(tenant_id=tenant_id, project_id=project_id)
        selected = None
        if observation_id is not None:
            selected = self.store.get_observation(
                tenant_id=tenant_id, project_id=project_id, observation_id=observation_id
            )
            if selected is None:
                raise IdentityGraphError(
                    "Tracking observation not found.",
                    code="UNKNOWN_OBSERVATION",
                )
        else:
            matching = [
                item
                for item in observations
                if item.candidate_campaign_id == campaign_id
                or item.parameter_value == campaign_id
            ]
            selected = matching[-1] if matching else (observations[-1] if observations else None)
        if selected is None:
            receipt = self._verification_receipt(
                tenant_id=tenant_id,
                project_id=project_id,
                campaign_id=campaign_id,
                source_ref="",
                status=VerificationStatus.NOT_OBSERVED,
                observed_identifier="",
                expected_identifier=expected,
                observation_id="",
                resolution_id="",
                tracking_binding_id=tracking_binding_id,
                issues=("NOT_OBSERVED",),
            )
            return self.store.put_verification_receipt(receipt)

        resolved = self.resolve_tracking(
            tenant_id=tenant_id,
            project_id=project_id,
            observation_id=selected.observation_id,
        )
        observed_identifier = selected.parameter_value
        issues: list[str] = list(resolved.issues)
        if resolved.status == ResolutionAuthority.REVIEW_REQUIRED:
            status = VerificationStatus.REVIEW_REQUIRED
            issues.append("REVIEW_REQUIRED")
        elif resolved.status != ResolutionAuthority.RESOLVED or resolved.campaign_id is None:
            status = VerificationStatus.OBSERVED_UNVERIFIED
            issues.append("UNRESOLVED")
        elif resolved.campaign_id != campaign_id or observed_identifier != expected:
            status = VerificationStatus.REVIEW_REQUIRED
            issues.append("EXPECTED_IDENTIFIER_MISMATCH")
        else:
            status = VerificationStatus.VERIFIED
        receipt = self._verification_receipt(
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign_id,
            source_ref=selected.source_ref,
            status=status,
            observed_identifier=observed_identifier,
            expected_identifier=expected,
            observation_id=selected.observation_id,
            resolution_id=resolved.resolution_id,
            tracking_binding_id=tracking_binding_id,
            verification_method=resolved.source,
            issues=tuple(dict.fromkeys(issues)),
            verified_at=datetime.now(UTC) if status == VerificationStatus.VERIFIED else None,
        )
        stored = self.store.put_verification_receipt(receipt)
        if instructions is not None:
            next_status = instructions.implementation_status
            if status == VerificationStatus.VERIFIED:
                next_status = TrackingImplementationStatus.VERIFIED
            elif status in {
                VerificationStatus.OBSERVED_UNVERIFIED,
                VerificationStatus.REVIEW_REQUIRED,
            }:
                next_status = TrackingImplementationStatus.OBSERVED
            refreshed = instructions.model_copy(update={"implementation_status": next_status})
            refreshed = refreshed.model_copy(
                update={"fingerprint": identity_fingerprint(refreshed)}
            )
            self.store.put_tracking_instructions(refreshed)
        return stored

    def campaign_verification(
        self, *, tenant_id: str, project_id: str, campaign_id: str
    ) -> TrackingVerificationReceipt:
        self._authorize(tenant_id)
        self._require_campaign(tenant_id, project_id, campaign_id)
        rows = self.store.list_verification_receipts(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if rows:
            return rows[-1]
        return self.verify_tracking(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )

    def tracking_coverage(
        self, *, tenant_id: str, project_id: str
    ) -> IdentityCoverageReadModel:
        self._authorize(tenant_id)
        observations = self.store.list_observations(tenant_id=tenant_id, project_id=project_id)
        resolutions = self.store.list_resolutions(tenant_id=tenant_id, project_id=project_id)
        campaigns = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        receipts = self.store.list_verification_receipts(
            tenant_id=tenant_id, project_id=project_id
        )
        resolved_count = sum(
            1 for item in resolutions if item.status == ResolutionAuthority.RESOLVED
        )
        review_count = sum(
            1 for item in resolutions if item.status == ResolutionAuthority.REVIEW_REQUIRED
        )
        unresolved_count = sum(
            1 for item in resolutions if item.status == ResolutionAuthority.UNRESOLVED
        )
        observed_campaigns = {
            item.candidate_campaign_id
            for item in observations
            if item.candidate_campaign_id
        }
        observed_campaigns.update(
            item.campaign_id for item in resolutions if item.campaign_id
        )
        verified_campaigns = {
            item.campaign_id for item in receipts if item.status == VerificationStatus.VERIFIED
        }
        declared = 0
        for campaign in campaigns:
            instructions = self.store.get_tracking_instructions(
                tenant_id=tenant_id, project_id=project_id, campaign_id=campaign.campaign_id
            )
            if instructions is not None:
                declared += 1
        issues: list[str] = []
        if not observations:
            coverage_status = IdentityGraphCapabilityState.NOT_CONFIGURED
        elif review_count:
            coverage_status = IdentityGraphCapabilityState.REVIEW_REQUIRED
            issues.append("REVIEW_REQUIRED")
        elif unresolved_count:
            coverage_status = IdentityGraphCapabilityState.PARTIAL
            issues.append("UNRESOLVED")
        else:
            coverage_status = IdentityGraphCapabilityState.READY
        model = IdentityCoverageReadModel(
            tenant_id=tenant_id,
            project_id=project_id,
            observed_identifier_count=len(observations),
            resolved_identifier_count=resolved_count,
            unresolved_identifier_count=unresolved_count,
            review_required_count=review_count,
            campaigns_total=len(campaigns),
            campaigns_with_tracking_declared=declared,
            campaigns_observed=len(observed_campaigns),
            campaigns_verified=len(verified_campaigns),
            coverage_status=coverage_status,
            issues=tuple(issues),
        )
        model = model.model_copy(update={"fingerprint": identity_fingerprint(model)})
        return self.store.put_coverage(model)

    def audience_binding_coverage(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> AudienceBindingCoverage:
        self._authorize(tenant_id)
        self._require_audience(tenant_id, project_id, audience_id)
        rows = self.store.list_audience_external(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )
        live = {
            BindingStatus.CONFIRMED,
            BindingStatus.ACTIVE,
            BindingStatus.APPROVED,
        }
        active = [item for item in rows if item.status in live]
        providers = tuple(dict.fromkeys(item.provider_id for item in rows))
        if not rows:
            status = IdentityGraphCapabilityState.NOT_CONFIGURED
        elif any(item.status == BindingStatus.REVIEW_REQUIRED for item in rows):
            status = IdentityGraphCapabilityState.REVIEW_REQUIRED
        else:
            status = IdentityGraphCapabilityState.READY
        return AudienceBindingCoverage(
            audience_id=audience_id,
            tenant_id=tenant_id,
            project_id=project_id,
            provider_binding_count=len(rows),
            active_provider_binding_count=len(active),
            providers=providers,
            status=status,
            issues=(),
        )

    def identity_handoff(
        self,
        *,
        tenant_id: str,
        project_id: str,
        resolution: CampaignIdentityResolution,
        signals: ObservedCampaignSignals,
        source_ref: str | None = None,
        audience_id: str | None = None,
        audience_binding_id: str | None = None,
    ) -> CampaignIdentityHandoff:
        self._authorize(tenant_id)
        campaign = None
        if resolution.campaign_id is not None:
            campaign = self.store.get_campaign(
                tenant_id=tenant_id,
                project_id=project_id,
                campaign_id=resolution.campaign_id,
            )
        return self.resolver.handoff(
            resolution=resolution,
            campaign=campaign,
            signals=signals,
            audience_id=audience_id,
            audience_binding_id=audience_binding_id,
            source_ref=source_ref,
        )

    def discover_campaigns(
        self, *, tenant_id: str, project_id: str, provider_account_ref: str
    ) -> list[dict[str, str]]:
        self._authorize(tenant_id)
        del project_id
        return self.provider_discovery.discover_campaigns(provider_account_ref)

    def discover_audiences(
        self, *, tenant_id: str, project_id: str, provider_account_ref: str
    ) -> list[dict[str, str]]:
        self._authorize(tenant_id)
        del project_id
        return self.provider_discovery.discover_audiences(provider_account_ref)

    def upsert_ga4_source(
        self,
        *,
        tenant_id: str,
        project_id: str,
        ga4_property_id: str,
        bq_project_id: str,
        bq_dataset_id: str,
        bq_location: str = "",
        stream_ids: tuple[str, ...] = (),
        declared_market_ids: tuple[str, ...] = (),
        coverage_start: str | None = None,
        coverage_end: str | None = None,
        traffic_source_capability: bool | None = None,
        freshness_state: str | None = None,
        source_authority: IdentitySourceAuthority = IdentitySourceAuthority.USER_DECLARED,
        overlap_policy: SourceOverlapPolicy | None = None,
        ga4_source_binding_id: str | None = None,
    ) -> GA4PropertySourceBinding:
        self._authorize(tenant_id)
        if declared_market_ids:
            self._validate_markets(tenant_id, project_id, declared_market_ids)
        now = datetime.now(UTC)
        existing = None
        if ga4_source_binding_id is not None:
            existing = self.store.get_source(
                tenant_id=tenant_id,
                project_id=project_id,
                ga4_source_binding_id=ga4_source_binding_id,
            )
            if existing is not None:
                assert_authority_not_silently_verified(existing.source_authority, source_authority)
        binding = GA4PropertySourceBinding(
            ga4_source_binding_id=ga4_source_binding_id or new_ga4_source_binding_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            ga4_property_id=ga4_property_id,
            bq_project_id=bq_project_id,
            bq_dataset_id=bq_dataset_id,
            bq_location=bq_location,
            stream_ids=stream_ids,
            declared_market_ids=declared_market_ids,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            traffic_source_capability=traffic_source_capability,
            freshness_state=freshness_state,
            source_authority=source_authority,
            overlap_policy=overlap_policy,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        binding = binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})
        self.store.put_source(binding)
        for stream_id in stream_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=MarketingIdentityEdgeType.GA4_STREAM_BELONGS_TO_PROPERTY,
                    from_node_type=MarketingIdentityNodeType.GA4_STREAM,
                    from_node_id=stream_id,
                    to_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                    to_node_id=ga4_property_id,
                )
            )
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=MarketingIdentityEdgeType.BIGQUERY_SOURCE_EXPORTS_PROPERTY,
                from_node_type=MarketingIdentityNodeType.BIGQUERY_GA4_SOURCE,
                from_node_id=binding.ga4_source_binding_id,
                to_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                to_node_id=ga4_property_id,
            )
        )
        for market_id in declared_market_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=MarketingIdentityEdgeType.GA4_PROPERTY_COVERS_MARKET,
                    from_node_type=MarketingIdentityNodeType.GA4_PROPERTY,
                    from_node_id=ga4_property_id,
                    to_node_type=MarketingIdentityNodeType.MARKET,
                    to_node_id=market_id,
                )
            )
        return binding

    def upsert_topology(
        self,
        *,
        tenant_id: str,
        project_id: str,
        topology_kind: GA4TopologyKind,
        source_binding_ids: tuple[str, ...] = (),
        overlap_policy: SourceOverlapPolicy | None = None,
        market_resolution_policy_id: str | None = None,
        topology_id: str | None = None,
    ) -> GA4SourceTopology:
        self._authorize(tenant_id)
        sources = [
            self.store.get_source(
                tenant_id=tenant_id, project_id=project_id, ga4_source_binding_id=item
            )
            for item in source_binding_ids
        ]
        if any(item is None for item in sources):
            raise IdentityGraphError(
                "Topology referenced an unknown GA4 source binding.",
                code="UNKNOWN_GA4_SOURCE",
            )
        issues, status, direct_union_ready, location_class = self._assess_topology(
            topology_kind=topology_kind,
            overlap_policy=overlap_policy,
            sources=tuple(item for item in sources if item is not None),
            market_resolution_policy_id=market_resolution_policy_id,
        )
        topology = GA4SourceTopology(
            topology_id=topology_id or new_topology_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            source_binding_ids=source_binding_ids,
            topology_kind=topology_kind,
            market_resolution_policy_id=market_resolution_policy_id,
            overlap_policy=overlap_policy,
            status=status,
            issues=issues,
            direct_union_ready=direct_union_ready,
            location_class=location_class,
        )
        topology = topology.model_copy(update={"fingerprint": identity_fingerprint(topology)})
        return self.store.put_topology(topology)

    def upsert_market_policy(
        self,
        *,
        tenant_id: str,
        project_id: str,
        allowed_methods: tuple[MarketResolutionMethod, ...],
        policy_id: str | None = None,
    ) -> MarketResolutionPolicy:
        self._authorize(tenant_id)
        if not allowed_methods:
            raise IdentityGraphError(
                "MarketResolutionPolicy must declare allowed methods.",
                code="MARKET_POLICY_EMPTY",
            )
        policy = MarketResolutionPolicy(
            policy_id=policy_id or new_policy_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            allowed_methods=allowed_methods,
        )
        policy = policy.model_copy(update={"fingerprint": identity_fingerprint(policy)})
        return self.store.put_policy(policy)

    def resolve_market(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_ref: str,
        method: MarketResolutionMethod,
        market_id: str | None,
        policy_id: str | None = None,
        rule_ref: str | None = None,
    ) -> MarketResolutionEvidence:
        self._authorize(tenant_id)
        policy = self.store.get_policy(
            tenant_id=tenant_id, project_id=project_id, policy_id=policy_id
        )
        if policy is None:
            if method == MarketResolutionMethod.GEO_MAPPING:
                return MarketResolutionEvidence(
                    market_id=None,
                    method=MarketResolutionMethod.UNRESOLVED,
                    source_ref=source_ref,
                    authority=ResolutionAuthority.UNRESOLVED,
                    issues=("GEO_MAPPING_NOT_IMPLICIT_DEFAULT",),
                )
            if method == MarketResolutionMethod.UNRESOLVED or market_id is None:
                return MarketResolutionEvidence(
                    market_id=None,
                    method=MarketResolutionMethod.UNRESOLVED,
                    source_ref=source_ref,
                    authority=ResolutionAuthority.UNRESOLVED,
                    issues=("MARKET_UNRESOLVED",),
                )
            return MarketResolutionEvidence(
                market_id=None,
                method=MarketResolutionMethod.UNRESOLVED,
                source_ref=source_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("MARKET_POLICY_MISSING",),
            )
        if method not in policy.allowed_methods:
            return MarketResolutionEvidence(
                market_id=None,
                method=MarketResolutionMethod.UNRESOLVED,
                source_ref=source_ref,
                rule_ref=rule_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("METHOD_NOT_ALLOWED",),
            )
        if market_id is None:
            return MarketResolutionEvidence(
                market_id=None,
                method=method,
                source_ref=source_ref,
                rule_ref=rule_ref,
                authority=ResolutionAuthority.UNRESOLVED,
                issues=("MARKET_UNRESOLVED",),
            )
        self._validate_markets(tenant_id, project_id, (market_id,))
        return MarketResolutionEvidence(
            market_id=market_id,
            method=method,
            source_ref=source_ref,
            rule_ref=rule_ref,
            authority=ResolutionAuthority.RESOLVED,
        )

    def overview(self, *, tenant_id: str, project_id: str) -> IdentityGraphOverview:
        self._authorize(tenant_id)
        campaigns = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        personas = self.store.list_personas(tenant_id=tenant_id, project_id=project_id)
        audiences = self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
        sources = self.store.list_sources(tenant_id=tenant_id, project_id=project_id)
        mappings = self.store.list_external(tenant_id=tenant_id, project_id=project_id)
        topology = self.store.get_topology(tenant_id=tenant_id, project_id=project_id)
        components: list[IdentityGraphComponentState] = []
        issues: list[str] = []
        ledger_issues: list[str] = []
        receipts = [
            self.store.get_campaign_receipt(
                tenant_id=tenant_id, project_id=project_id, campaign_id=item.campaign_id
            )
            for item in campaigns
        ]
        persona_receipts = [
            self.store.get_persona_receipt(
                tenant_id=tenant_id, project_id=project_id, persona_id=item.persona_id
            )
            for item in personas
        ]
        audience_receipts = [
            self.store.get_audience_receipt(
                tenant_id=tenant_id, project_id=project_id, audience_id=item.audience_id
            )
            for item in audiences
        ]
        if not campaigns:
            campaign_ledger_state = IdentityGraphCapabilityState.NOT_CONFIGURED
        elif any(
            receipt is not None and receipt.state == IdentityGraphCapabilityState.REVIEW_REQUIRED
            for receipt in receipts
        ):
            campaign_ledger_state = IdentityGraphCapabilityState.REVIEW_REQUIRED
            ledger_issues.extend(
                issue
                for receipt in receipts
                if receipt is not None
                for issue in receipt.issues
            )
        elif campaigns and all(
            receipt is not None and receipt.state == IdentityGraphCapabilityState.READY
            for receipt in receipts
        ):
            campaign_ledger_state = IdentityGraphCapabilityState.READY
        else:
            campaign_ledger_state = IdentityGraphCapabilityState.PARTIAL
        persona_ledger_state = ledger_state_from_receipts(personas, persona_receipts)
        audience_ledger_state = ledger_state_from_receipts(audiences, audience_receipts)
        ledger_ready = campaign_ledger_state == IdentityGraphCapabilityState.READY
        if ledger_ready:
            components.append(IdentityGraphComponentState.CAMPAIGN_LEDGER_READY)
        if persona_ledger_state == IdentityGraphCapabilityState.READY:
            components.append(IdentityGraphComponentState.PERSONA_LEDGER_READY)
        if audience_ledger_state == IdentityGraphCapabilityState.READY:
            components.append(IdentityGraphComponentState.AUDIENCE_LEDGER_READY)
        canonical_markets = self.store.list_canonical_markets(
            tenant_id=tenant_id, project_id=project_id
        )
        topology_ready = (
            topology is not None
            and topology.status == TopologyStatus.READY
            and bool(canonical_markets)
            and topology.location_class != BqLocationClass.UNKNOWN_LOCATION
            and "MARKET_RESOLUTION_REQUIRED" not in topology.issues
            and "CROSS_LOCATION_REVIEW_REQUIRED" not in topology.issues
        )
        if topology_ready:
            components.append(IdentityGraphComponentState.GA4_TOPOLOGY_READY)
        if topology is not None:
            issues.extend(topology.issues)
        issues.extend(ledger_issues)
        review = (
            any(item.status == BindingStatus.REVIEW_REQUIRED for item in mappings)
            or (topology is not None and topology.status == TopologyStatus.REVIEW_REQUIRED)
            or campaign_ledger_state == IdentityGraphCapabilityState.REVIEW_REQUIRED
            or persona_ledger_state == IdentityGraphCapabilityState.REVIEW_REQUIRED
            or audience_ledger_state == IdentityGraphCapabilityState.REVIEW_REQUIRED
        )
        if review:
            state = IdentityGraphCapabilityState.REVIEW_REQUIRED
        elif not campaigns and not sources:
            state = IdentityGraphCapabilityState.NOT_CONFIGURED
        elif ledger_ready and (topology is None or topology_ready):
            state = IdentityGraphCapabilityState.READY
        else:
            state = IdentityGraphCapabilityState.PARTIAL
        return IdentityGraphOverview(
            tenant_id=tenant_id,
            project_id=project_id,
            capability_state=state,
            campaign_ledger_state=campaign_ledger_state,
            persona_ledger_state=persona_ledger_state,
            audience_ledger_state=audience_ledger_state,
            component_states=tuple(components),
            campaign_count=len(campaigns),
            persona_count=len(personas),
            audience_count=len(audiences),
            source_count=len(sources),
            mapping_count=len(mappings),
            issues=tuple(dict.fromkeys(issues)),
        )

    def mta_touchpoint_refs(
        self,
        *,
        campaign_id: str | None,
        parent_campaign_id: str | None,
        market_id: str,
        campaign_identity_source: CampaignIdentitySource,
        market_resolution_method: MarketResolutionMethod,
        ga4_source_binding_id: str | None,
    ) -> MTAIdentityTouchpointRefs:
        return MTAIdentityTouchpointRefs(
            campaign_id=campaign_id,
            parent_campaign_id=parent_campaign_id,
            market_id=market_id,
            campaign_identity_source=campaign_identity_source,
            market_resolution_method=market_resolution_method,
            ga4_source_binding_id=ga4_source_binding_id,
        )

    def list_sources(self, *, tenant_id: str, project_id: str) -> list[GA4PropertySourceBinding]:
        self._authorize(tenant_id)
        return self.store.list_sources(tenant_id=tenant_id, project_id=project_id)

    def list_mappings(self, *, tenant_id: str, project_id: str) -> list[CampaignExternalBinding]:
        self._authorize(tenant_id)
        return self.store.list_external(tenant_id=tenant_id, project_id=project_id)

    def discover_ga4_sources(
        self,
        *,
        tenant_id: str,
        project_id: str,
        tables: tuple[dict[str, Any], ...] = (),
    ) -> GA4TopologyDiscoveryResult:
        self._authorize(tenant_id)
        if not tables:
            return GA4TopologyDiscoveryResult(
                tenant_id=tenant_id,
                project_id=project_id,
                location_class=BqLocationClass.UNKNOWN_LOCATION,
                issues=("DISCOVERY_NOT_CONFIGURED",),
            )
        binding_ids: list[str] = []
        locations: list[str] = []
        issues: list[str] = []
        for table in tables:
            project = table.get("bq_project_id")
            dataset = table.get("bq_dataset_id")
            if not project or not dataset:
                issues.append("DISCOVERY_TABLE_INCOMPLETE")
                continue
            location = table.get("bq_location") or ""
            capability = table.get("traffic_source_capability")
            if isinstance(capability, bool):
                traffic_capability: bool | None = capability
            elif isinstance(capability, str):
                traffic_capability = capability.lower() == "true"
            else:
                traffic_capability = None
            source = self.upsert_ga4_source(
                tenant_id=tenant_id,
                project_id=project_id,
                ga4_property_id=str(table.get("ga4_property_id") or dataset),
                bq_project_id=str(project),
                bq_dataset_id=str(dataset),
                bq_location=str(location),
                coverage_start=table.get("coverage_start") or None,
                coverage_end=table.get("coverage_end") or None,
                traffic_source_capability=traffic_capability,
                freshness_state=table.get("freshness_state") or None,
                source_authority=IdentitySourceAuthority.DATA_FOUNDATION_DISCOVERED,
            )
            binding_ids.append(source.ga4_source_binding_id)
            locations.append(location)
        known = {item for item in locations if item}
        if not known:
            location_class = BqLocationClass.UNKNOWN_LOCATION
            issues.append("UNKNOWN_LOCATION")
        elif len(known) == 1:
            location_class = BqLocationClass.SAME_LOCATION
        else:
            location_class = BqLocationClass.CROSS_LOCATION
            issues.append("CROSS_LOCATION_REVIEW_REQUIRED")
        return GA4TopologyDiscoveryResult(
            tenant_id=tenant_id,
            project_id=project_id,
            discovered_source_binding_ids=tuple(binding_ids),
            bq_locations=tuple(sorted(known)),
            location_class=location_class,
            issues=tuple(dict.fromkeys(issues)),
        )

    def validate_ga4_topology(
        self, *, tenant_id: str, project_id: str
    ) -> GA4TopologyReadinessReceipt:
        self._authorize(tenant_id)
        markets = self.store.list_canonical_markets(tenant_id=tenant_id, project_id=project_id)
        topology = self.store.get_topology(tenant_id=tenant_id, project_id=project_id)
        sources = self.store.list_sources(tenant_id=tenant_id, project_id=project_id)
        issues: list[str] = []
        if not markets:
            issues.append("CANONICAL_MARKETS_REQUIRED")
        if topology is None:
            issues.append("TOPOLOGY_NOT_CONFIGURED")
            location_class = BqLocationClass.UNKNOWN_LOCATION
        else:
            issues.extend(topology.issues)
            location_class = topology.location_class
            if topology.location_class == BqLocationClass.UNKNOWN_LOCATION:
                issues.append("UNKNOWN_LOCATION_NOT_READY_FOR_UNIFIED_COMPILATION")
            if (
                topology.topology_kind
                in {GA4TopologyKind.SINGLE_MASTER_PROPERTY, GA4TopologyKind.MASTER_PLUS_REGIONAL}
                and topology.market_resolution_policy_id is None
                and len(markets) > 1
            ):
                issues.append("MARKET_RESOLUTION_REQUIRED")
        coverage: list[GA4MarketCoverage] = []
        for market in markets:
            bound = [
                source.ga4_source_binding_id
                for source in sources
                if market.market_id in source.declared_market_ids
            ]
            if bound:
                status = MarketCoverageStatus.COMPLETE
            elif sources:
                status = MarketCoverageStatus.MISSING
            else:
                status = MarketCoverageStatus.UNKNOWN
            coverage.append(
                GA4MarketCoverage(
                    market_id=market.market_id,
                    source_binding_ids=tuple(bound),
                    coverage_status=status,
                    issues=() if bound else ("MARKET_COVERAGE_MISSING",),
                )
            )
        if "CANONICAL_MARKETS_REQUIRED" in issues or "TOPOLOGY_NOT_CONFIGURED" in issues:
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_INCOMPLETE
        elif any(
            item in issues
            for item in (
                "CROSS_LOCATION_REVIEW_REQUIRED",
                "OVERLAP_POLICY_REQUIRED",
                "OVERLAP_REVIEW_REQUIRED",
                "MARKET_RESOLUTION_REQUIRED",
                "DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY",
            )
        ) or (topology is not None and topology.status == TopologyStatus.REVIEW_REQUIRED):
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_REVIEW_REQUIRED
        elif issues or any(
            item.coverage_status != MarketCoverageStatus.COMPLETE for item in coverage
        ):
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_INCOMPLETE
        else:
            state = GA4TopologyReadinessState.GA4_TOPOLOGY_READY
        receipt = GA4TopologyReadinessReceipt(
            tenant_id=tenant_id,
            project_id=project_id,
            topology_id=topology.topology_id if topology is not None else None,
            state=state,
            location_class=location_class,
            coverage=tuple(coverage),
            issues=tuple(dict.fromkeys(issues)),
        )
        receipt = receipt.model_copy(update={"fingerprint": identity_fingerprint(receipt)})
        return self.store.put_topology_receipt(receipt)

    def get_ga4_topology(self, *, tenant_id: str, project_id: str) -> GA4SourceTopology | None:
        self._authorize(tenant_id)
        return self.store.get_topology(tenant_id=tenant_id, project_id=project_id)

    def _authorize(self, tenant_id: str) -> None:
        bound = require_tenant()
        if bound.tenant_id != tenant_id:
            raise IdentityGraphError(
                "Caller cannot choose arbitrary tenant authority.",
                code="TENANT_MISMATCH",
            )

    def _assert_live_target_not_archived(
        self, *, entity_status: str, binding_status: BindingStatus
    ) -> None:
        if (
            entity_status == "ARCHIVED"
            and binding_status in {BindingStatus.CONFIRMED, BindingStatus.ACTIVE}
        ):
            raise IdentityGraphError(
                "Live bindings cannot target an archived campaign or audience.",
                code="ARCHIVED_TARGET",
            )

    def _tracking_status_evidenced(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        status: TrackingImplementationStatus,
    ) -> bool:
        receipts = self.store.list_verification_receipts(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if status == TrackingImplementationStatus.VERIFIED:
            return any(item.status == VerificationStatus.VERIFIED for item in receipts)
        observations = self.store.list_observations(tenant_id=tenant_id, project_id=project_id)
        related = [
            item
            for item in observations
            if item.candidate_campaign_id == campaign_id or item.parameter_value == campaign_id
        ]
        if related:
            return True
        return any(item.status != VerificationStatus.NOT_OBSERVED for item in receipts)

    def _signals_from_observation(
        self, observation: TrackingObservation
    ) -> ObservedCampaignSignals:
        utm_id = None
        custom_name = None
        custom_value = None
        if observation.identifier_kind == ObservedIdentifierKind.UTM_ID:
            utm_id = observation.parameter_value
        elif observation.identifier_kind == ObservedIdentifierKind.CUSTOM_PARAM:
            custom_name = observation.parameter_name
            custom_value = observation.parameter_value
        return ObservedCampaignSignals(
            utm_id=utm_id,
            utm_campaign=(
                observation.parameter_value
                if observation.identifier_kind == ObservedIdentifierKind.UTM_CAMPAIGN
                else None
            ),
            provider_id=observation.external_provider_id,
            external_account_id=observation.external_account_id,
            external_campaign_id=observation.external_campaign_id,
            custom_parameter_name=custom_name,
            custom_parameter_value=custom_value,
            observed_at=observation.observed_at,
        )

    def _verification_receipt(
        self,
        *,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        source_ref: str,
        status: VerificationStatus,
        observed_identifier: str,
        expected_identifier: str,
        observation_id: str,
        resolution_id: str,
        tracking_binding_id: str | None,
        issues: tuple[str, ...] = (),
        verification_method: CampaignIdentitySource | None = None,
        verified_at: datetime | None = None,
    ) -> TrackingVerificationReceipt:
        receipt = TrackingVerificationReceipt(
            receipt_id=new_receipt_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            campaign_id=campaign_id,
            source_ref=source_ref,
            status=status,
            observed_identifier=observed_identifier,
            expected_identifier=expected_identifier,
            observation_id=observation_id,
            resolution_id=resolution_id,
            tracking_binding_id=tracking_binding_id,
            verification_method=verification_method,
            issues=issues,
            verified_at=verified_at,
        )
        return receipt.model_copy(
            update={"evidence_fingerprint": identity_fingerprint(receipt)}
        )

    def _require_campaign(
        self, tenant_id: str, project_id: str, campaign_id: str
    ) -> CanonicalCampaign:
        found = self.store.get_campaign(
            tenant_id=tenant_id, project_id=project_id, campaign_id=campaign_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown campaign_id {campaign_id}.",
                code="UNKNOWN_CAMPAIGN",
            )
        return found

    def _require_persona(
        self, tenant_id: str, project_id: str, persona_id: str
    ) -> CanonicalPersona:
        found = self.store.get_persona(
            tenant_id=tenant_id, project_id=project_id, persona_id=persona_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown persona_id {persona_id}.",
                code="UNKNOWN_PERSONA",
            )
        return found

    def _require_audience(
        self, tenant_id: str, project_id: str, audience_id: str
    ) -> CanonicalAudience:
        found = self.store.get_audience(
            tenant_id=tenant_id, project_id=project_id, audience_id=audience_id
        )
        if found is None:
            raise IdentityGraphError(
                f"Unknown audience_id {audience_id}.",
                code="UNKNOWN_AUDIENCE",
            )
        return found

    def _require_name(self, name: str) -> None:
        if not name or not str(name).strip():
            raise IdentityGraphError("name is required.", code="NAME_REQUIRED")

    def _validate_biq_snapshot(self, snapshot_id: str | None) -> None:
        if not snapshot_id:
            return
        if self.business_iq_store is None:
            raise IdentityGraphError(
                "business_profile_snapshot_id cannot be validated without Business IQ.",
                code="UNKNOWN_SNAPSHOT",
            )
        found = self.business_iq_store.get_snapshot(snapshot_id)
        if found is None:
            raise IdentityGraphError(
                f"Unknown business_profile_snapshot_id {snapshot_id}.",
                code="UNKNOWN_SNAPSHOT",
            )

    def _validate_persona_payload(self, persona: CanonicalPersona) -> None:
        self._require_name(persona.name)
        if persona.market_ids:
            self._validate_markets(persona.tenant_id, persona.project_id, persona.market_ids)
        self._validate_biq_snapshot(persona.business_profile_snapshot_id)

    def _validate_audience_payload(self, audience: CanonicalAudience) -> None:
        self._require_name(audience.name)
        validate_source_ref(audience.source_ref)
        _validate_planned_dates(audience.effective_start_date, audience.effective_end_date)
        if audience.market_ids:
            self._validate_markets(audience.tenant_id, audience.project_id, audience.market_ids)
        self._validate_audience_persona_ids(audience)

    def _validate_audience_persona_ids(self, audience: CanonicalAudience) -> None:
        for persona_id in audience.persona_ids:
            try:
                assert_persona_id_shape(persona_id)
            except (ValueError, InvalidResourceIdentifierError) as exc:
                raise IdentityGraphError(
                    f"Unknown persona_id {persona_id}.",
                    code="UNKNOWN_PERSONA",
                ) from exc
            found = self.store.get_persona(
                tenant_id=audience.tenant_id,
                project_id=audience.project_id,
                persona_id=persona_id,
            )
            if found is None:
                raise IdentityGraphError(
                    f"Unknown persona_id {persona_id}.",
                    code="UNKNOWN_PERSONA",
                )

    def _validate_campaign_persona_ids(self, campaign: CanonicalCampaign) -> None:
        for persona_id in campaign.persona_ids:
            try:
                assert_persona_id_shape(persona_id)
            except (ValueError, InvalidResourceIdentifierError) as exc:
                raise IdentityGraphError(
                    f"Unknown persona_id {persona_id}.",
                    code="UNKNOWN_PERSONA",
                ) from exc
            found = self.store.get_persona(
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                persona_id=persona_id,
            )
            if found is None:
                raise IdentityGraphError(
                    f"Unknown persona_id {persona_id}.",
                    code="UNKNOWN_PERSONA",
                )
            if (
                found.status == PersonaStatus.ARCHIVED
                and campaign.status != CampaignStatus.ARCHIVED
            ):
                raise IdentityGraphError(
                    "Archived personas cannot be targeted by a non-archived campaign.",
                    code="ARCHIVED_TARGET",
                )

    def _validate_campaign_audience_ids(self, campaign: CanonicalCampaign) -> None:
        for audience_id in campaign.audience_ids:
            try:
                assert_audience_id_shape(audience_id)
            except (ValueError, InvalidResourceIdentifierError) as exc:
                raise IdentityGraphError(
                    f"Unknown audience_id {audience_id}.",
                    code="UNKNOWN_AUDIENCE",
                ) from exc
            found = self.store.get_audience(
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                audience_id=audience_id,
            )
            if found is None:
                raise IdentityGraphError(
                    f"Unknown audience_id {audience_id}.",
                    code="UNKNOWN_AUDIENCE",
                )
            if (
                found.status == AudienceStatus.ARCHIVED
                and campaign.status != CampaignStatus.ARCHIVED
            ):
                raise IdentityGraphError(
                    "Archived audiences cannot be targeted by a non-archived campaign.",
                    code="ARCHIVED_TARGET",
                )

    def _validate_audience_parent(self, audience: CanonicalAudience) -> None:
        parent_id = audience.parent_audience_id
        if parent_id is None:
            return
        assert_not_self_parent(audience.audience_id, parent_id)
        parent = self.store.get_audience(
            tenant_id=audience.tenant_id,
            project_id=audience.project_id,
            audience_id=parent_id,
        )
        if parent is None:
            raise IdentityGraphError(
                "Parent audience was not found in this project.",
                code="PARENT_CROSS_PROJECT",
            )
        if parent.tenant_id != audience.tenant_id or parent.project_id != audience.project_id:
            raise IdentityGraphError(
                "Audience parent must belong to the same project.",
                code="PARENT_CROSS_PROJECT",
            )
        parents = {
            item.audience_id: item.parent_audience_id
            for item in self.store.list_audiences(
                tenant_id=audience.tenant_id, project_id=audience.project_id
            )
        }
        parents[audience.audience_id] = audience.parent_audience_id
        if would_create_audience_cycle(
            audience_id=audience.audience_id,
            new_parent_id=parent_id,
            audiences=parents,
        ):
            raise IdentityGraphError(
                "Audience hierarchy rejects cycles.",
                code="HIERARCHY_CYCLE",
            )

    def _persona_is_referenced(
        self, *, tenant_id: str, project_id: str, persona_id: str
    ) -> bool:
        campaigns = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        if any(persona_id in item.persona_ids for item in campaigns):
            return True
        audiences = self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
        return any(persona_id in item.persona_ids for item in audiences)

    def _audience_is_referenced(
        self, *, tenant_id: str, project_id: str, audience_id: str
    ) -> bool:
        campaigns = self.store.list_campaigns(tenant_id=tenant_id, project_id=project_id)
        if any(audience_id in item.audience_ids for item in campaigns):
            return True
        audiences = self.store.list_audiences(tenant_id=tenant_id, project_id=project_id)
        return any(item.parent_audience_id == audience_id for item in audiences)

    def _sync_typed_edges(
        self,
        *,
        tenant_id: str,
        project_id: str,
        from_node_id: str,
        from_node_type: MarketingIdentityNodeType,
        edge_type: MarketingIdentityEdgeType,
        to_node_type: MarketingIdentityNodeType,
        to_ids: tuple[str, ...],
    ) -> None:
        existing = [
            item
            for item in self.store.list_edges(tenant_id=tenant_id, project_id=project_id)
            if item.from_node_id == from_node_id and item.edge_type == edge_type
        ]
        wanted = set(to_ids)
        have = {item.to_node_id: item for item in existing}
        for to_id, edge in have.items():
            if to_id not in wanted:
                self.store.delete_edge(
                    tenant_id=tenant_id, project_id=project_id, edge_id=edge.edge_id
                )
        for to_id in to_ids:
            if to_id in have:
                continue
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=edge_type,
                    from_node_type=from_node_type,
                    from_node_id=from_node_id,
                    to_node_type=to_node_type,
                    to_node_id=to_id,
                )
            )

    def _sync_audience_edges(self, audience: CanonicalAudience) -> None:
        self._sync_typed_edges(
            tenant_id=audience.tenant_id,
            project_id=audience.project_id,
            from_node_id=audience.audience_id,
            from_node_type=MarketingIdentityNodeType.AUDIENCE,
            edge_type=MarketingIdentityEdgeType.AUDIENCE_REPRESENTS_PERSONA,
            to_node_type=MarketingIdentityNodeType.PERSONA,
            to_ids=audience.persona_ids,
        )
        self._sync_typed_edges(
            tenant_id=audience.tenant_id,
            project_id=audience.project_id,
            from_node_id=audience.audience_id,
            from_node_type=MarketingIdentityNodeType.AUDIENCE,
            edge_type=MarketingIdentityEdgeType.AUDIENCE_AVAILABLE_IN_MARKET,
            to_node_type=MarketingIdentityNodeType.MARKET,
            to_ids=audience.market_ids,
        )

    def _sync_campaign_target_edges(self, campaign: CanonicalCampaign) -> None:
        self._sync_typed_edges(
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            from_node_id=campaign.campaign_id,
            from_node_type=MarketingIdentityNodeType.CAMPAIGN,
            edge_type=MarketingIdentityEdgeType.CAMPAIGN_TARGETS_PERSONA,
            to_node_type=MarketingIdentityNodeType.PERSONA,
            to_ids=campaign.persona_ids,
        )
        self._sync_typed_edges(
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            from_node_id=campaign.campaign_id,
            from_node_type=MarketingIdentityNodeType.CAMPAIGN,
            edge_type=MarketingIdentityEdgeType.CAMPAIGN_TARGETS_AUDIENCE,
            to_node_type=MarketingIdentityNodeType.AUDIENCE,
            to_ids=campaign.audience_ids,
        )

    def _canonical_id_for_legacy_ref(
        self, *, tenant_id: str, project_id: str, business_market_ref: str
    ) -> str | None:
        for binding in self.store.list_market_bindings(
            tenant_id=tenant_id, project_id=project_id
        ):
            if binding.business_market_ref == business_market_ref:
                return binding.market_id
        return None

    def _validate_scope(self, campaign: CanonicalCampaign) -> None:
        self._validate_create_payload(campaign)

    def _validate_create_payload(
        self, campaign: CanonicalCampaign, *, require_scope: bool = True
    ) -> None:
        _validate_planned_dates(campaign.planned_start_date, campaign.planned_end_date)
        self._validate_campaign_persona_ids(campaign)
        self._validate_campaign_audience_ids(campaign)
        self._validate_objective(campaign)
        if require_scope:
            self._validate_markets_required(campaign.market_ids)
            self._validate_channels_required(campaign.channel_ids)
        self._validate_channels(campaign.channel_ids)
        if campaign.market_ids:
            self._validate_markets(campaign.tenant_id, campaign.project_id, campaign.market_ids)

    def _validate_markets_required(self, market_ids: tuple[str, ...]) -> None:
        if not market_ids:
            raise IdentityGraphError(
                "Campaign create requires at least one canonical market_id.",
                code="MARKETS_REQUIRED",
            )

    def _validate_channels_required(self, channel_ids: tuple[str, ...]) -> None:
        if not channel_ids:
            raise IdentityGraphError(
                "Campaign create requires at least one Channel Registry channel_id.",
                code="CHANNELS_REQUIRED",
            )

    def _validate_channels(self, channel_ids: tuple[str, ...]) -> None:
        registry = cached_channel_registry()
        for channel_id in channel_ids:
            try:
                assert_channel_id_in_registry(channel_id, registry)
            except ChannelValidationError as exc:
                raise IdentityGraphError(str(exc), code="UNKNOWN_CHANNEL") from exc

    def _validate_objective(self, campaign: CanonicalCampaign) -> None:
        if not campaign.objective_ref:
            return
        if self.business_iq_store is None:
            raise IdentityGraphError(
                "objective_ref cannot be validated without Business IQ.",
                code="UNKNOWN_OBJECTIVE",
            )
        profile = self.business_iq_store.get_profile(
            tenant_id=campaign.tenant_id, workspace_id=campaign.project_id
        )
        if profile is None:
            raise IdentityGraphError(
                "objective_ref does not match a Business IQ objective on the current snapshot.",
                code="UNKNOWN_OBJECTIVE",
            )
        known = {item.objective_id for item in profile.measurement_objectives}
        if campaign.objective_ref not in known:
            raise IdentityGraphError(
                f"Unknown objective_ref {campaign.objective_ref}.",
                code="UNKNOWN_OBJECTIVE",
            )

    def _assert_status_transition(
        self, current: CampaignStatus, proposed: CampaignStatus
    ) -> None:
        if proposed == current:
            return
        allowed = _STATUS_TRANSITIONS.get(current, frozenset())
        if proposed not in allowed:
            raise IdentityGraphError(
                f"Status transition {current.value} → {proposed.value} is not allowed.",
                code="STATUS_TRANSITION",
            )

    def _mint_tracking_instructions(
        self,
        campaign: CanonicalCampaign,
        *,
        display: str,
        generated_at: datetime,
    ) -> CampaignTrackingInstructions:
        instructions = CampaignTrackingInstructions(
            campaign_id=campaign.campaign_id,
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            utm_id=campaign.campaign_id,
            parameter_name="utm_id",
            parameter_value=campaign.campaign_id,
            utm_campaign=display,
            recommended_utm_campaign=display,
            query_parameters={"utm_id": campaign.campaign_id, "utm_campaign": display},
            implementation_status=TrackingImplementationStatus.NOT_IMPLEMENTED,
            generation_provenance=TrackingInstructionProvenance.GENERATED,
            instruction_authority=IdentitySourceAuthority.PREM3_GENERATED,
            generated_at=generated_at,
        )
        return instructions.model_copy(update={"fingerprint": identity_fingerprint(instructions)})

    def _validate_markets(
        self, tenant_id: str, project_id: str, market_ids: tuple[str, ...]
    ) -> None:
        unknown: list[str] = []
        for market_id in market_ids:
            try:
                assert_market_id_shape(market_id)
            except (ValueError, InvalidResourceIdentifierError) as exc:
                raise IdentityGraphError(str(exc), code="UNKNOWN_MARKET") from exc
            found = self.store.get_market(
                tenant_id=tenant_id, project_id=project_id, market_id=market_id
            )
            if found is None:
                unknown.append(market_id)
        if unknown:
            raise IdentityGraphError(
                f"Unknown canonical market_id values: {', '.join(unknown)}.",
                code="UNKNOWN_MARKET",
            )

    def _validate_parent(self, campaign: CanonicalCampaign) -> None:
        parent_id = campaign.parent_campaign_id
        if parent_id is None:
            return
        assert_not_self_parent(campaign.campaign_id, parent_id)
        parent = self.store.get_campaign(
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            campaign_id=parent_id,
        )
        assert_parent_same_project(campaign, parent)
        indexed = {
            item.campaign_id: item
            for item in self.store.list_campaigns(
                tenant_id=campaign.tenant_id, project_id=campaign.project_id
            )
        }
        indexed[campaign.campaign_id] = campaign
        if would_create_cycle(
            campaign_id=campaign.campaign_id, new_parent_id=parent_id, campaigns=indexed
        ):
            raise IdentityGraphError(
                "Campaign hierarchy rejects cycles.",
                code="HIERARCHY_CYCLE",
            )

    def _default_utm_binding(
        self, campaign: CanonicalCampaign, *, actor_id: str
    ) -> CampaignTrackingBinding:
        binding = CampaignTrackingBinding(
            tracking_binding_id=new_tracking_binding_id(),
            tenant_id=campaign.tenant_id,
            project_id=campaign.project_id,
            campaign_id=campaign.campaign_id,
            parameter_name="utm_id",
            parameter_value=campaign.campaign_id,
            tracking_kind=TrackingKind.PREM3_UTM_ID,
            status=BindingStatus.ACTIVE,
            authority=IdentitySourceAuthority.PREM3_GENERATED,
            created_by=actor_id,
        )
        return binding.model_copy(update={"fingerprint": identity_fingerprint(binding)})

    def _write_campaign_edges(
        self, campaign: CanonicalCampaign, tracking: CampaignTrackingBinding
    ) -> None:
        if campaign.parent_campaign_id:
            self._replace_child_edge(campaign)
        for market_id in campaign.market_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=campaign.tenant_id,
                    project_id=campaign.project_id,
                    edge_type=MarketingIdentityEdgeType.CAMPAIGN_TARGETS_MARKET,
                    from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                    from_node_id=campaign.campaign_id,
                    to_node_type=MarketingIdentityNodeType.MARKET,
                    to_node_id=market_id,
                )
            )
        for channel_id in campaign.channel_ids:
            self.store.put_edge(
                MarketingIdentityEdge(
                    edge_id=new_edge_id(),
                    tenant_id=campaign.tenant_id,
                    project_id=campaign.project_id,
                    edge_type=MarketingIdentityEdgeType.CAMPAIGN_USES_CHANNEL,
                    from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                    from_node_id=campaign.campaign_id,
                    to_node_type=MarketingIdentityNodeType.CHANNEL,
                    to_node_id=channel_id,
                )
            )
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_TRACKED_BY,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign.campaign_id,
                to_node_type=MarketingIdentityNodeType.CAMPAIGN,
                to_node_id=tracking.tracking_binding_id,
            )
        )
        self._sync_campaign_target_edges(campaign)

    def _replace_child_edge(self, campaign: CanonicalCampaign) -> None:
        if campaign.parent_campaign_id is None:
            return
        self.store.put_edge(
            MarketingIdentityEdge(
                edge_id=new_edge_id(),
                tenant_id=campaign.tenant_id,
                project_id=campaign.project_id,
                edge_type=MarketingIdentityEdgeType.CAMPAIGN_CHILD_OF,
                from_node_type=MarketingIdentityNodeType.CAMPAIGN,
                from_node_id=campaign.campaign_id,
                to_node_type=MarketingIdentityNodeType.CAMPAIGN,
                to_node_id=campaign.parent_campaign_id,
            )
        )

    def _assess_topology(
        self,
        *,
        topology_kind: GA4TopologyKind,
        overlap_policy: SourceOverlapPolicy | None,
        sources: tuple[GA4PropertySourceBinding, ...],
        market_resolution_policy_id: str | None = None,
    ) -> tuple[tuple[str, ...], TopologyStatus, bool, BqLocationClass]:
        issues: list[str] = []
        locations = {item.bq_location for item in sources if item.bq_location}
        missing_location = any(not item.bq_location for item in sources)
        if missing_location or not locations:
            issues.append("BQ_LOCATION_MISSING")
            location_class = BqLocationClass.UNKNOWN_LOCATION
        elif len(locations) > 1:
            issues.append("CROSS_LOCATION_REVIEW_REQUIRED")
            location_class = BqLocationClass.CROSS_LOCATION
        else:
            location_class = BqLocationClass.SAME_LOCATION
        if topology_kind == GA4TopologyKind.MASTER_PLUS_REGIONAL and overlap_policy is None:
            issues.append("OVERLAP_POLICY_REQUIRED")
        declared = {market_id for source in sources for market_id in source.declared_market_ids}
        if (
            topology_kind
            in {GA4TopologyKind.SINGLE_MASTER_PROPERTY, GA4TopologyKind.MASTER_PLUS_REGIONAL}
            and len(declared) > 1
            and market_resolution_policy_id is None
        ):
            issues.append("MARKET_RESOLUTION_REQUIRED")
        if overlap_policy == SourceOverlapPolicy.DEDUPE_REQUIRED:
            issues.append("DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY")
        if overlap_policy == SourceOverlapPolicy.REVIEW_REQUIRED:
            issues.append("OVERLAP_REVIEW_REQUIRED")
        direct_union_ready = (
            location_class == BqLocationClass.SAME_LOCATION
            and overlap_policy
            not in {
                None,
                SourceOverlapPolicy.DEDUPE_REQUIRED,
                SourceOverlapPolicy.REVIEW_REQUIRED,
            }
            and "OVERLAP_POLICY_REQUIRED" not in issues
        )
        if "OVERLAP_POLICY_REQUIRED" in issues or overlap_policy in {
            SourceOverlapPolicy.DEDUPE_REQUIRED,
            SourceOverlapPolicy.REVIEW_REQUIRED,
        }:
            status = TopologyStatus.REVIEW_REQUIRED
        elif issues:
            status = TopologyStatus.PARTIAL
        else:
            status = TopologyStatus.READY
        return tuple(issues), status, direct_union_ready, location_class
