"""IG-04 unified analytics compiler. Consumes IG-01 topology and IG-03 campaign identity."""

from __future__ import annotations

from app.core.contracts import utc_now
from app.identity_graph.analytics.adapter import InMemoryAnalyticalAdapter
from app.identity_graph.analytics.channel import resolve_channel
from app.identity_graph.analytics.contracts import (
    UNIFIED_ANALYTICS_DATASET,
    AnalyticalArtifactRef,
    AnalyticalSessionSeed,
    AnalyticalSourceSelection,
    M5_03AnalyticalHandoff,
    MarketIdentityResolution,
    MtaJourneyRow,
    MtaTouchpointRow,
    UnifiedAnalyticsCompilation,
    UnifiedAnalyticsReadinessReceipt,
    UnifiedSessionRow,
)
from app.identity_graph.analytics.keys import journey_id, session_id
from app.identity_graph.analytics.overlap import (
    apply_overlap_filter,
    exclusion_template,
    overlap_compile_status,
)
from app.identity_graph.analytics.sql import sql_plan_fingerprint
from app.identity_graph.contracts import (
    AudienceExternalBinding,
    CampaignIdentityHandoff,
    GA4PropertySourceBinding,
    GA4SourceTopology,
    GA4TopologyReadinessReceipt,
    ObservedCampaignSignals,
)
from app.identity_graph.enums import (
    AnalyticalArtifactKind,
    AnalyticalCompilationPhase,
    AnalyticalCompilationStatus,
    BqLocationClass,
    CampaignIdentitySource,
    CrossLocationCompileStatus,
    GA4TopologyReadinessState,
    MarketResolutionMethod,
    OverlapCompileStatus,
    RowResolutionStatus,
    SettlementCompileStatus,
    SourceOverlapPolicy,
    UnifiedAnalyticsReadinessState,
)
from app.identity_graph.fingerprint import identity_fingerprint
from app.identity_graph.ids import compilation_id_from_fingerprint, new_artifact_id, new_receipt_id
from app.identity_graph.resolution import CampaignIdentityResolver
from app.modeling.mta.contracts import GA4SettlementPolicy

INTRADAY_TABLE_KIND = "events_intraday"


class CompileContext:
    def __init__(
        self,
        *,
        selection: AnalyticalSourceSelection,
        topology: GA4SourceTopology | None,
        topology_receipt: GA4TopologyReadinessReceipt | None,
        sources: tuple[GA4PropertySourceBinding, ...],
        seeds: tuple[AnalyticalSessionSeed, ...],
        resolver: CampaignIdentityResolver,
        resolve_market,
        resolve_campaign,
        audience_bindings: tuple[AudienceExternalBinding, ...],
        adapter: InMemoryAnalyticalAdapter,
        identity_rules_fingerprint: str,
    ) -> None:
        self.selection = selection
        self.topology = topology
        self.topology_receipt = topology_receipt
        self.sources = sources
        self.seeds = seeds
        self.resolver = resolver
        self.resolve_market = resolve_market
        self.resolve_campaign = resolve_campaign
        self.audience_bindings = audience_bindings
        self.adapter = adapter
        self.identity_rules_fingerprint = identity_rules_fingerprint
        self.issues: list[str] = []
        self.phase = AnalyticalCompilationPhase.SOURCE_VALIDATE
        self.cross_location = CrossLocationCompileStatus.UNKNOWN_LOCATION
        self.overlap_status = OverlapCompileStatus.NOT_EVALUATED
        self.settlement_status = SettlementCompileStatus.UNKNOWN
        self.sessions: tuple[UnifiedSessionRow, ...] = ()
        self.touchpoints: tuple[MtaTouchpointRow, ...] = ()
        self.journeys: tuple[MtaJourneyRow, ...] = ()
        self.artifacts: tuple[AnalyticalArtifactRef, ...] = ()
        self.blocked = False
        self.journey_by_session: dict[str, str] = {}


def compile_unified_analytics(ctx: CompileContext) -> tuple[
    UnifiedAnalyticsCompilation,
    UnifiedAnalyticsReadinessReceipt,
    M5_03AnalyticalHandoff,
]:
    selected = _source_validate(ctx)
    if not ctx.blocked:
        _topology_validate(ctx)
    if not ctx.blocked:
        _location_validate(ctx, selected)
    if ctx.topology is not None:
        _overlap_validate(ctx)
    if not ctx.blocked:
        _settlement_validate(ctx)
    if not ctx.blocked:
        filtered = apply_overlap_filter(
            seeds=ctx.seeds,
            sources=selected,
            overlap_policy=ctx.topology.overlap_policy if ctx.topology else None,
        )
        ctx.phase = AnalyticalCompilationPhase.SESSION_COMPILE
        ctx.sessions = _compile_sessions(ctx, filtered)
        if (
            ctx.topology is not None
            and ctx.topology.overlap_policy == SourceOverlapPolicy.PARTITIONED_BY_MARKET
        ):
            source_by_id = {item.ga4_source_binding_id: item for item in selected}
            kept: list[UnifiedSessionRow] = []
            for row in ctx.sessions:
                source = source_by_id.get(row.ga4_source_binding_id)
                if source is not None and row.market_id in source.declared_market_ids:
                    kept.append(row)
            ctx.sessions = tuple(kept)
        ctx.phase = AnalyticalCompilationPhase.TOUCHPOINT_COMPILE
        ctx.touchpoints = _compile_touchpoints(ctx.sessions)
        ctx.phase = AnalyticalCompilationPhase.JOURNEY_COMPILE
        ctx.journeys = _compile_journeys(ctx)
        ctx.phase = AnalyticalCompilationPhase.SCHEMA_VALIDATE
        schema_issues = [
            *ctx.adapter.schema_validate_sessions(ctx.sessions),
            *ctx.adapter.schema_validate_touchpoints(ctx.touchpoints),
            *ctx.adapter.schema_validate_journeys(ctx.journeys),
        ]
        ctx.issues.extend(schema_issues)
        if schema_issues:
            ctx.blocked = True
    compilation_id, sql_fp, selection_fp = _ids(ctx)
    if not ctx.blocked:
        ctx.adapter.put_sessions(compilation_id, ctx.sessions)
        ctx.adapter.put_touchpoints(compilation_id, ctx.touchpoints)
        ctx.adapter.put_journeys(compilation_id, ctx.journeys)
        ctx.phase = AnalyticalCompilationPhase.READ_BACK_VERIFY
        if len(ctx.adapter.read_back_sessions(compilation_id)) != len(ctx.sessions):
            ctx.issues.append("READ_BACK_SESSION_MISMATCH")
            ctx.blocked = True
        if len(ctx.adapter.read_back_touchpoints(compilation_id)) != len(ctx.touchpoints):
            ctx.issues.append("READ_BACK_TOUCHPOINT_MISMATCH")
            ctx.blocked = True
        if len(ctx.adapter.read_back_journeys(compilation_id)) != len(ctx.journeys):
            ctx.issues.append("READ_BACK_JOURNEY_MISMATCH")
            ctx.blocked = True
    status = _compilation_status(ctx)
    if status == AnalyticalCompilationStatus.READY:
        ctx.phase = AnalyticalCompilationPhase.READY
    ctx.artifacts = _artifact_refs(
        compilation_id=compilation_id,
        selection=ctx.selection,
        sessions=ctx.sessions,
        touchpoints=ctx.touchpoints,
        journeys=ctx.journeys,
        ready=status == AnalyticalCompilationStatus.READY,
    )
    receipt = _receipt(ctx, compilation_id, status)
    compilation = UnifiedAnalyticsCompilation(
        compilation_id=compilation_id,
        tenant_id=ctx.selection.tenant_id,
        project_id=ctx.selection.project_id,
        topology_id=ctx.topology.topology_id if ctx.topology else None,
        topology_fingerprint=ctx.topology.fingerprint if ctx.topology else "",
        selection_fingerprint=selection_fp,
        sql_fingerprint=sql_fp,
        identity_rules_fingerprint=ctx.identity_rules_fingerprint,
        phase=ctx.phase,
        status=status,
        selected_source_binding_ids=ctx.selection.selected_source_binding_ids,
        destination_dataset=UNIFIED_ANALYTICS_DATASET,
        artifact_refs=ctx.artifacts,
        receipt_id=receipt.receipt_id,
        issues=tuple(dict.fromkeys(ctx.issues)),
    )
    compilation = compilation.model_copy(
        update={"fingerprint": identity_fingerprint(compilation)}
    )
    receipt = receipt.model_copy(
        update={
            "artifact_refs": ctx.artifacts,
            "fingerprint": identity_fingerprint(
                receipt.model_copy(update={"artifact_refs": ctx.artifacts})
            ),
        }
    )
    handoff = M5_03AnalyticalHandoff(
        compilation_id=compilation_id,
        topology_id=compilation.topology_id,
        topology_fingerprint=compilation.topology_fingerprint,
        identity_rules_fingerprint=ctx.identity_rules_fingerprint,
        sql_fingerprint=sql_fp,
        artifact_refs=ctx.artifacts,
        available_market_ids=tuple(
            sorted({row.market_id for row in ctx.sessions if row.market_id})
        ),
        available_channel_ids=tuple(
            sorted({row.channel_id for row in ctx.sessions if row.channel_id})
        ),
        available_campaign_ids=tuple(
            sorted({row.campaign_id for row in ctx.sessions if row.campaign_id})
        ),
        session_count=len(ctx.sessions),
        touchpoint_count=len(ctx.touchpoints),
        journey_count=len(ctx.journeys),
        issues=compilation.issues,
        mta_result_ready=False,
    )
    return compilation, receipt, handoff


def _source_validate(ctx: CompileContext) -> tuple[GA4PropertySourceBinding, ...]:
    ctx.phase = AnalyticalCompilationPhase.SOURCE_VALIDATE
    if not ctx.selection.selected_source_binding_ids:
        ctx.issues.append("SOURCE_SELECTION_REQUIRED")
        ctx.blocked = True
        return ()
    by_id = {item.ga4_source_binding_id: item for item in ctx.sources}
    selected: list[GA4PropertySourceBinding] = []
    for binding_id in ctx.selection.selected_source_binding_ids:
        source = by_id.get(binding_id)
        if source is None:
            ctx.issues.append("UNKNOWN_SOURCE_BINDING")
            ctx.blocked = True
            continue
        if source.project_id != ctx.selection.project_id:
            ctx.issues.append("SOURCE_PROJECT_MISMATCH")
            ctx.blocked = True
            continue
        if not source.bq_project_id or not source.bq_dataset_id:
            ctx.issues.append("BQ_REF_REQUIRED")
            ctx.blocked = True
        if not source.bq_location:
            ctx.issues.append("BQ_LOCATION_MISSING")
            ctx.blocked = True
        selected.append(source)
    return tuple(selected)


def _topology_validate(ctx: CompileContext) -> None:
    ctx.phase = AnalyticalCompilationPhase.TOPOLOGY_VALIDATE
    if ctx.topology is None or ctx.topology_receipt is None:
        ctx.issues.append("TOPOLOGY_NOT_CONFIGURED")
        ctx.blocked = True
        return
    if ctx.topology_receipt.state != GA4TopologyReadinessState.GA4_TOPOLOGY_READY:
        ctx.issues.append("GA4_TOPOLOGY_NOT_READY")
        ctx.issues.extend(ctx.topology_receipt.issues)
        ctx.blocked = True
    if ctx.topology.location_class == BqLocationClass.CROSS_LOCATION:
        ctx.issues.extend(("CROSS_LOCATION_REVIEW_REQUIRED", "BQ_LOCATION_INCOMPATIBLE"))
        ctx.blocked = True
        ctx.cross_location = CrossLocationCompileStatus.CROSS_LOCATION_REVIEW_REQUIRED
    elif ctx.topology.location_class == BqLocationClass.UNKNOWN_LOCATION:
        ctx.issues.append("BQ_LOCATION_INCOMPATIBLE")
        ctx.blocked = True
        ctx.cross_location = CrossLocationCompileStatus.UNKNOWN_LOCATION


def _location_validate(
    ctx: CompileContext, selected: tuple[GA4PropertySourceBinding, ...]
) -> None:
    ctx.phase = AnalyticalCompilationPhase.LOCATION_VALIDATE
    locations = {item.bq_location for item in selected if item.bq_location}
    if any(not item.bq_location for item in selected) or not locations:
        ctx.cross_location = CrossLocationCompileStatus.UNKNOWN_LOCATION
        ctx.issues.append("BQ_LOCATION_INCOMPATIBLE")
        ctx.blocked = True
        return
    if len(locations) > 1:
        ctx.cross_location = CrossLocationCompileStatus.CROSS_LOCATION_REVIEW_REQUIRED
        ctx.issues.extend(("CROSS_LOCATION_REVIEW_REQUIRED", "BQ_LOCATION_INCOMPATIBLE"))
        ctx.blocked = True
        return
    if ctx.topology and ctx.topology.location_class == BqLocationClass.CROSS_LOCATION:
        ctx.cross_location = CrossLocationCompileStatus.CROSS_LOCATION_REVIEW_REQUIRED
        ctx.issues.extend(("CROSS_LOCATION_REVIEW_REQUIRED", "BQ_LOCATION_INCOMPATIBLE"))
        ctx.blocked = True
        return
    if ctx.topology and ctx.topology.location_class == BqLocationClass.UNKNOWN_LOCATION:
        ctx.cross_location = CrossLocationCompileStatus.UNKNOWN_LOCATION
        ctx.issues.append("BQ_LOCATION_INCOMPATIBLE")
        ctx.blocked = True
        return
    ctx.cross_location = CrossLocationCompileStatus.SAME_LOCATION


def _overlap_validate(ctx: CompileContext) -> None:
    ctx.phase = AnalyticalCompilationPhase.OVERLAP_VALIDATE
    if ctx.topology is None:
        ctx.issues.append("OVERLAP_POLICY_REQUIRED")
        ctx.blocked = True
        return
    status, issues = overlap_compile_status(
        topology_kind=ctx.topology.topology_kind,
        overlap_policy=ctx.topology.overlap_policy,
    )
    ctx.overlap_status = status
    ctx.issues.extend(issues)
    if status in {
        OverlapCompileStatus.OVERLAP_POLICY_REQUIRED,
        OverlapCompileStatus.DEDUPE_POLICY_REQUIRED,
        OverlapCompileStatus.DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY,
        OverlapCompileStatus.REVIEW_REQUIRED,
    }:
        ctx.blocked = True


def _settlement_validate(ctx: CompileContext) -> None:
    policy = ctx.selection.settlement_policy
    has_intraday = any(item.table_kind == INTRADAY_TABLE_KIND for item in ctx.seeds)
    if policy == GA4SettlementPolicy.DAILY_SETTLED and has_intraday:
        ctx.settlement_status = SettlementCompileStatus.INTRADAY_MIXED
        ctx.issues.append("INTRADAY_MIXED_INTO_SETTLED")
        ctx.blocked = True
        return
    if policy == GA4SettlementPolicy.PREVIEW_INTRADAY:
        ctx.settlement_status = SettlementCompileStatus.PREVIEW_INTRADAY
        ctx.issues.append("PREVIEW_INTRADAY_NOT_FINAL")
        return
    ctx.settlement_status = SettlementCompileStatus.DAILY_SETTLED


def _compile_sessions(
    ctx: CompileContext, seeds: tuple[AnalyticalSessionSeed, ...]
) -> tuple[UnifiedSessionRow, ...]:
    ctx.phase = AnalyticalCompilationPhase.MARKET_RESOLVE
    source_by_id = {item.ga4_source_binding_id: item for item in ctx.sources}
    rows: list[UnifiedSessionRow] = []
    for seed in seeds:
        source = source_by_id.get(seed.ga4_source_binding_id)
        market = _market_for_seed(ctx, seed, source)
        ctx.phase = AnalyticalCompilationPhase.CHANNEL_RESOLVE
        channel = resolve_channel(
            source=seed.source,
            medium=seed.medium,
            campaign_name=seed.campaign_name,
            provider_id=seed.provider_id,
            approved_bindings=ctx.selection.approved_source_medium_bindings,
        )
        ctx.phase = AnalyticalCompilationPhase.CAMPAIGN_RESOLVE
        campaign, parent_id, campaign_source, campaign_status = _campaign_for_seed(ctx, seed)
        audience_id, audience_status = _audience_for_seed(ctx, seed)
        sid = session_id(
            ga4_property_id=seed.ga4_property_id,
            subject_key=seed.subject_key,
            ga_session_id=seed.ga_session_id,
        )
        ctx.journey_by_session[sid] = journey_id(
            project_id=ctx.selection.project_id,
            identity_strategy=ctx.selection.identity_strategy.value,
            subject_key=seed.subject_key,
        )
        issues = tuple(
            dict.fromkeys(
                [
                    *market.issues,
                    *channel.issues,
                    *(
                        ("CAMPAIGN_SLICE_REQUIRED",)
                        if _campaign_blocks(ctx, campaign_status)
                        else ()
                    ),
                ]
            )
        )
        rows.append(
            UnifiedSessionRow(
                session_id=sid,
                ga4_property_id=seed.ga4_property_id,
                ga4_source_binding_id=seed.ga4_source_binding_id,
                source=seed.source,
                medium=seed.medium,
                campaign_name=seed.campaign_name,
                market_id=market.market_id,
                market_status=market.status,
                market_method=market.method,
                channel_id=channel.channel_id,
                channel_family_id=channel.channel_family_id,
                channel_status=channel.status,
                channel_method=channel.method,
                campaign_id=campaign,
                campaign_status=campaign_status,
                campaign_identity_source=campaign_source,
                parent_campaign_id=parent_id,
                audience_id=audience_id,
                audience_status=audience_status,
                provider_id=seed.provider_id,
                session_start_ts=seed.session_start_ts,
                key_event=seed.key_event,
                issues=issues,
            )
        )
    if ctx.selection.campaign_slice_required and any(
        row.campaign_status != RowResolutionStatus.RESOLVED for row in rows
    ):
        ctx.issues.append("CAMPAIGN_SLICE_REQUIRED")
        ctx.blocked = True
    return tuple(rows)


def _market_for_seed(
    ctx: CompileContext,
    seed: AnalyticalSessionSeed,
    source: GA4PropertySourceBinding | None,
) -> MarketIdentityResolution:
    source_ref = seed.ga4_source_binding_id
    if source is not None and len(source.declared_market_ids) == 1:
        evidence = ctx.resolve_market(
            tenant_id=ctx.selection.tenant_id,
            project_id=ctx.selection.project_id,
            source_ref=source_ref,
            method=MarketResolutionMethod.PROPERTY_BOUND,
            market_id=source.declared_market_ids[0],
            policy_id=ctx.topology.market_resolution_policy_id if ctx.topology else None,
        )
        status = (
            RowResolutionStatus.RESOLVED
            if evidence.market_id
            else RowResolutionStatus.UNRESOLVED
        )
        return MarketIdentityResolution(
            market_id=evidence.market_id,
            method=evidence.method,
            status=status,
            source_ref=source_ref,
            geo_country=seed.geo_country,
            issues=evidence.issues,
            denominator=1,
            resolved_count=1 if evidence.market_id else 0,
            unresolved_count=0 if evidence.market_id else 1,
        )
    evidence = ctx.resolve_market(
        tenant_id=ctx.selection.tenant_id,
        project_id=ctx.selection.project_id,
        source_ref=source_ref,
        method=MarketResolutionMethod.GEO_MAPPING,
        market_id=None,
        policy_id=ctx.topology.market_resolution_policy_id if ctx.topology else None,
    )
    return MarketIdentityResolution(
        market_id=None,
        method=MarketResolutionMethod.UNRESOLVED,
        status=RowResolutionStatus.UNRESOLVED,
        source_ref=source_ref,
        geo_country=seed.geo_country,
        issues=tuple(dict.fromkeys([*evidence.issues, "GEO_COUNTRY_NOT_IMPLICIT_MARKET"])),
        denominator=1,
        unresolved_count=1,
    )


def _campaign_for_seed(
    ctx: CompileContext, seed: AnalyticalSessionSeed
) -> tuple[str | None, str | None, CampaignIdentitySource, RowResolutionStatus]:
    signals = ObservedCampaignSignals(
        utm_id=seed.utm_id,
        utm_campaign=seed.campaign_name,
        provider_id=seed.provider_id,
        external_account_id=seed.external_account_id,
        external_campaign_id=seed.external_campaign_id,
    )
    handoff: CampaignIdentityHandoff = ctx.resolve_campaign(signals)
    if handoff.resolution_status.value == "REVIEW_REQUIRED":
        status = RowResolutionStatus.REVIEW_REQUIRED
        campaign_id = None
    elif handoff.campaign_id:
        status = RowResolutionStatus.RESOLVED
        campaign_id = handoff.campaign_id
    else:
        status = RowResolutionStatus.UNRESOLVED
        campaign_id = None
    return campaign_id, handoff.parent_campaign_id, handoff.campaign_identity_source, status


def _audience_for_seed(
    ctx: CompileContext, seed: AnalyticalSessionSeed
) -> tuple[str | None, RowResolutionStatus]:
    if not seed.audience_provider_id or not seed.audience_external_id:
        return None, RowResolutionStatus.NOT_APPLICABLE
    matches = [
        item
        for item in ctx.audience_bindings
        if item.provider_id == seed.audience_provider_id
        and item.external_audience_id == seed.audience_external_id
    ]
    ids = {item.audience_id for item in matches}
    if len(ids) == 1:
        return next(iter(ids)), RowResolutionStatus.RESOLVED
    if len(ids) > 1:
        return None, RowResolutionStatus.REVIEW_REQUIRED
    return None, RowResolutionStatus.UNRESOLVED


def _campaign_blocks(ctx: CompileContext, status: RowResolutionStatus) -> bool:
    return ctx.selection.campaign_slice_required and status != RowResolutionStatus.RESOLVED


def _compile_touchpoints(sessions: tuple[UnifiedSessionRow, ...]) -> tuple[MtaTouchpointRow, ...]:
    ordered = sorted(sessions, key=lambda row: (row.session_start_ts, row.session_id))
    rows: list[MtaTouchpointRow] = []
    for index, session in enumerate(ordered, start=1):
        rows.append(
            MtaTouchpointRow(
                session_id=session.session_id,
                touchpoint_order=index,
                ga4_property_id=session.ga4_property_id,
                ga4_source_binding_id=session.ga4_source_binding_id,
                market_id=session.market_id,
                channel_id=session.channel_id,
                campaign_id=session.campaign_id,
                parent_campaign_id=session.parent_campaign_id,
                audience_id=session.audience_id,
                provider_id=session.provider_id,
                session_start_ts=session.session_start_ts,
                key_event=session.key_event,
                issues=session.issues,
            )
        )
    return tuple(rows)


def _compile_journeys(ctx: CompileContext) -> tuple[MtaJourneyRow, ...]:
    grouped: dict[str, list[UnifiedSessionRow]] = {}
    for session in ctx.sessions:
        key = ctx.journey_by_session.get(session.session_id, session.session_id)
        grouped.setdefault(key, []).append(session)
    rows: list[MtaJourneyRow] = []
    for jid, sessions in grouped.items():
        market_ids = tuple(sorted({row.market_id for row in sessions if row.market_id}))
        multi = len(market_ids) > 1
        issues = ("MULTI_MARKET_JOURNEY",) if multi else ()
        rows.append(
            MtaJourneyRow(
                journey_id=jid,
                session_ids=tuple(row.session_id for row in sessions),
                market_ids=market_ids,
                channel_ids=tuple(sorted({row.channel_id for row in sessions if row.channel_id})),
                campaign_ids=tuple(
                    sorted({row.campaign_id for row in sessions if row.campaign_id})
                ),
                multi_market=multi,
                key_event_count=sum(1 for row in sessions if row.key_event),
                touchpoint_count=len(sessions),
                issues=issues,
            )
        )
    return tuple(rows)


def _ids(ctx: CompileContext) -> tuple[str, str, str]:
    overlap_rel = None
    if ctx.topology is not None:
        overlap_rel = exclusion_template(ctx.topology.overlap_policy)
    sql_fp = sql_plan_fingerprint(
        session_policy=ctx.selection.session_traffic_source_policy,
        overlap_template=overlap_rel,
    )
    selection_fp = ctx.selection.fingerprint or identity_fingerprint(ctx.selection)
    payload = {
        "selection": selection_fp,
        "topology": ctx.topology.fingerprint if ctx.topology else "",
        "sql": sql_fp,
        "identity_rules": ctx.identity_rules_fingerprint,
        "overlap": ctx.overlap_status.value,
        "settlement": ctx.selection.settlement_policy.value,
        "identity_strategy": ctx.selection.identity_strategy.value,
    }
    compilation_id = compilation_id_from_fingerprint(identity_fingerprint(payload))
    return compilation_id, sql_fp, selection_fp


def _compilation_status(ctx: CompileContext) -> AnalyticalCompilationStatus:
    if ctx.blocked:
        if any(
            code in ctx.issues
            for code in (
                "CROSS_LOCATION_REVIEW_REQUIRED",
                "BQ_LOCATION_INCOMPATIBLE",
                "DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY",
                "DEDUPE_POLICY_REQUIRED",
                "OVERLAP_POLICY_REQUIRED",
                "GA4_TOPOLOGY_NOT_READY",
                "INTRADAY_MIXED_INTO_SETTLED",
                "CAMPAIGN_SLICE_REQUIRED",
            )
        ):
            if "OVERLAP_REVIEW_REQUIRED" in ctx.issues:
                return AnalyticalCompilationStatus.REVIEW_REQUIRED
            return AnalyticalCompilationStatus.BLOCKED
        if "PREVIEW_INTRADAY_NOT_FINAL" in ctx.issues and not any(
            item.startswith("CROSS_") or item.startswith("DEDUPE_") for item in ctx.issues
        ):
            return AnalyticalCompilationStatus.REVIEW_REQUIRED
        return AnalyticalCompilationStatus.BLOCKED
    if "PREVIEW_INTRADAY_NOT_FINAL" in ctx.issues:
        return AnalyticalCompilationStatus.REVIEW_REQUIRED
    if "OVERLAP_REVIEW_REQUIRED" in ctx.issues:
        return AnalyticalCompilationStatus.REVIEW_REQUIRED
    return AnalyticalCompilationStatus.READY


def _artifact_refs(
    *,
    compilation_id: str,
    selection: AnalyticalSourceSelection,
    sessions: tuple[UnifiedSessionRow, ...],
    touchpoints: tuple[MtaTouchpointRow, ...],
    journeys: tuple[MtaJourneyRow, ...],
    ready: bool,
) -> tuple[AnalyticalArtifactRef, ...]:
    now = utc_now()
    specs = (
        (
            AnalyticalArtifactKind.GA4_SESSIONS_UNIFIED,
            f"ga4_sessions_unified_{compilation_id}",
            len(sessions),
            identity_fingerprint({"schema": "UnifiedSessionRow", "n": len(sessions)}),
        ),
        (
            AnalyticalArtifactKind.MTA_SESSION_TOUCHPOINTS,
            f"mta_session_touchpoints_{compilation_id}",
            len(touchpoints),
            identity_fingerprint({"schema": "MtaTouchpointRow", "n": len(touchpoints)}),
        ),
        (
            AnalyticalArtifactKind.MTA_JOURNEYS,
            f"mta_journeys_{compilation_id}",
            len(journeys),
            identity_fingerprint({"schema": "MtaJourneyRow", "n": len(journeys)}),
        ),
    )
    refs: list[AnalyticalArtifactRef] = []
    for kind, table, count, schema_fp in specs:
        refs.append(
            AnalyticalArtifactRef(
                artifact_id=new_artifact_id(),
                compilation_id=compilation_id,
                tenant_id=selection.tenant_id,
                project_id=selection.project_id,
                kind=kind,
                dataset_id=UNIFIED_ANALYTICS_DATASET,
                table_name=table,
                schema_fingerprint=schema_fp,
                row_count=count,
                current_pointer=False,
                created_at=now,
            )
        )
    if ready:
        refs.append(
            AnalyticalArtifactRef(
                artifact_id=new_artifact_id(),
                compilation_id=compilation_id,
                tenant_id=selection.tenant_id,
                project_id=selection.project_id,
                kind=AnalyticalArtifactKind.CURRENT_POINTER,
                dataset_id=UNIFIED_ANALYTICS_DATASET,
                table_name=f"ga4_sessions_unified_{compilation_id}_current",
                schema_fingerprint=refs[0].schema_fingerprint,
                row_count=len(sessions),
                current_pointer=True,
                created_at=now,
            )
        )
    return tuple(
        item.model_copy(update={"fingerprint": identity_fingerprint(item)}) for item in refs
    )


def _receipt(
    ctx: CompileContext,
    compilation_id: str,
    status: AnalyticalCompilationStatus,
) -> UnifiedAnalyticsReadinessReceipt:
    sessions = ctx.sessions
    if status == AnalyticalCompilationStatus.READY:
        state = UnifiedAnalyticsReadinessState.READY
    elif status == AnalyticalCompilationStatus.REVIEW_REQUIRED:
        state = UnifiedAnalyticsReadinessState.REVIEW_REQUIRED
    elif status == AnalyticalCompilationStatus.BLOCKED:
        state = UnifiedAnalyticsReadinessState.BLOCKED
    elif sessions:
        state = UnifiedAnalyticsReadinessState.PARTIAL
    else:
        state = UnifiedAnalyticsReadinessState.BLOCKED
    return UnifiedAnalyticsReadinessReceipt(
        receipt_id=new_receipt_id(),
        tenant_id=ctx.selection.tenant_id,
        project_id=ctx.selection.project_id,
        compilation_id=compilation_id,
        state=state,
        session_count=len(sessions),
        session_denominator=len(ctx.seeds),
        touchpoint_count=len(ctx.touchpoints),
        journey_count=len(ctx.journeys),
        markets_resolved=sum(
            1 for row in sessions if row.market_status == RowResolutionStatus.RESOLVED
        ),
        markets_unresolved=sum(
            1 for row in sessions if row.market_status == RowResolutionStatus.UNRESOLVED
        ),
        channels_resolved=sum(
            1 for row in sessions if row.channel_status == RowResolutionStatus.RESOLVED
        ),
        channels_unresolved=sum(
            1 for row in sessions if row.channel_status == RowResolutionStatus.UNRESOLVED
        ),
        campaigns_resolved=sum(
            1 for row in sessions if row.campaign_status == RowResolutionStatus.RESOLVED
        ),
        campaigns_unresolved=sum(
            1 for row in sessions if row.campaign_status == RowResolutionStatus.UNRESOLVED
        ),
        campaigns_review_required=sum(
            1 for row in sessions if row.campaign_status == RowResolutionStatus.REVIEW_REQUIRED
        ),
        cross_location_status=ctx.cross_location,
        overlap_status=ctx.overlap_status,
        settlement_status=ctx.settlement_status,
        issues=tuple(dict.fromkeys(ctx.issues)),
    )
