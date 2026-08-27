"""Server-owned Project Home and Foundation overview projections."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.business_iq.enums import BusinessContextReadyStatus
from app.business_iq.readiness import evaluate_business_context_ready
from app.business_iq.service import BusinessIqService
from app.control_plane.entitlements import PlanId
from app.control_plane.models import (
    EntitlementSnapshot,
    MeasurementTrack,
    MeasurementTrackType,
    ProjectScopeType,
    Workspace,
    WorkspaceStatus,
)
from app.control_plane.repository import ControlPlaneRepository
from app.data_foundation.context import DataFoundationContext, context_from_tenant
from app.data_foundation.enums import (
    ConnectionLifecycle,
    DataFoundationReadyStatus,
    SourceFoundationStatus,
)
from app.data_foundation.service import DataFoundationService
from app.modeling.mmm.states import projected_track_state
from app.project.capabilities import entitled_for_capability
from app.project.enums import (
    DEFAULT_MMM_ENGINE,
    AttentionSeverity,
    AttentionState,
    CapabilityAvailability,
    CapabilityFamily,
    NextActionType,
)
from app.project.measurement_home import measurement_home_conflict
from app.project.tracks import (
    apply_track_mutation,
    ensure_tracks_for_cycle,
    forecast_availability,
    mmm_adapter_state,
    mta_availability,
    planning_availability,
)
from app.publish_execution.model_ready import ModelReadyEvidenceResolver
from app.service.project_models import (
    AttentionItem,
    BusinessIqHomeSummary,
    BusinessIqOverviewReadModel,
    CoverageReadModel,
    DataFoundationHomeSummary,
    DataFoundationOverviewReadModel,
    IntelligenceHomeSummary,
    MeasurementCycleSummary,
    MeasurementTrackSummary,
    NextAction,
    PlanningCapabilitySummary,
    ProjectHomeReadModel,
    ProjectListItem,
    ProjectMeasurementHomeBinding,
    ProjectResponse,
    RecentChange,
)

NEXT_ACTION_LABELS: dict[NextActionType, str] = {
    NextActionType.START_BUSINESS_IQ: "Start Business IQ",
    NextActionType.CONTINUE_BUSINESS_IQ: "Continue Business IQ",
    NextActionType.OPEN_BUSINESS_IQ: "Open Business IQ",
    NextActionType.START_DATA_FOUNDATION: "Start Data Foundation",
    NextActionType.CONTINUE_DATA_FOUNDATION: "Continue Data Foundation",
    NextActionType.OPEN_DATA_FOUNDATION: "Open Data Foundation",
    NextActionType.CONTINUE_MMM: "Continue MMM",
    NextActionType.REVIEW_MMM: "Review MMM",
    NextActionType.SETUP_MTA: "Set up MTA",
    NextActionType.SELECT_MTA_KEY_EVENT: "Select MTA key event",
    NextActionType.OPEN_MTA: "Open MTA",
    NextActionType.SETUP_FORECAST: "Set up Forecast",
    NextActionType.START_INVESTMENT_PLAN: "Start Investment Plan",
    NextActionType.VIEW_SCENARIO_REQUIREMENTS: "View scenario requirements",
    NextActionType.VIEW_OPTIMIZATION_REQUIREMENTS: "View optimization requirements",
    NextActionType.REVIEW_SOURCE: "Review source",
    NextActionType.REAUTHORIZE_SOURCE: "Reauthorize source",
    NextActionType.OPEN_INSIGHT: "Open insight",
    NextActionType.REVIEW_DECISION: "Review decision",
    NextActionType.RETURN_PROJECT_HOME: "Return to Project Home",
}

TRACK_DISPLAY: dict[MeasurementTrackType, str] = {
    MeasurementTrackType.MMM: "MMM",
    MeasurementTrackType.MTA: "MTA",
    MeasurementTrackType.FORECAST: "Forecast",
}


def project_response(workspace: Workspace) -> ProjectResponse:
    return ProjectResponse(
        project_id=workspace.workspace_id,
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        scope_type=workspace.scope_type.value,
        brand_name=workspace.brand_name,
        business_unit=workspace.business_unit,
        primary_market=workspace.primary_market,
        markets=list(workspace.markets),
        default_currency=workspace.default_currency,
        default_timezone=workspace.default_timezone,
        logo_ref=workspace.logo_ref,
        status=workspace.status.value,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def apply_project_fields(workspace: Workspace, updates: dict[str, Any]) -> Workspace:
    payload = {key: value for key, value in updates.items() if value is not None or key in updates}
    if "scope_type" in payload and payload["scope_type"] is not None:
        payload["scope_type"] = ProjectScopeType(payload["scope_type"])
    if "markets" in payload and payload["markets"] is not None:
        payload["markets"] = tuple(payload["markets"])
    if "status" in payload and payload["status"] is not None:
        payload["status"] = WorkspaceStatus(payload["status"])
    return workspace.model_copy(update=payload)


def _modeling_stage(modeling, workspace: Workspace, track: MeasurementTrack) -> str | None:
    if modeling is None:
        return None
    current = modeling.current_for_cycle(
        tenant_id=workspace.tenant_id,
        project_id=workspace.workspace_id,
        cycle_id=track.cycle_id,
    )
    if current is None:
        return None
    return projected_track_state(current.state)


def next_action(
    action_type: NextActionType,
    *,
    capability: CapabilityFamily,
    resource_ref: str | None = None,
    route_hint: str | None = None,
    priority: int = 100,
) -> NextAction:
    return NextAction(
        action_type=action_type.value,
        label=NEXT_ACTION_LABELS[action_type],
        capability=capability.value,
        resource_ref=resource_ref,
        route_hint=route_hint,
        priority=priority,
    )


def _df_context(repo: ControlPlaneRepository, workspace: Workspace) -> DataFoundationContext:
    bq = repo.get_bigquery_binding(
        tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
    )
    drive = repo.get_drive_binding(
        tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
    )
    return context_from_tenant(
        workspace_id=workspace.workspace_id,
        destination_project_id=bq.destination_project_id if bq else None,
        destination_location=bq.location if bq else None,
        source_project_ids=bq.source_project_ids if bq else (),
        source_dataset_ids=bq.source_dataset_ids if bq else (),
        drive_root_folder_id=drive.root_folder_id if drive else None,
        google_connection_id=bq.connection_id if bq else (drive.connection_id if drive else None),
        bq_lifecycle=ConnectionLifecycle.AUTHORIZED if bq else ConnectionLifecycle.NOT_CONNECTED,
        drive_lifecycle=(
            ConnectionLifecycle.AUTHORIZED if drive else ConnectionLifecycle.NOT_CONNECTED
        ),
    )


def build_measurement_home(
    repo: ControlPlaneRepository, workspace: Workspace
) -> ProjectMeasurementHomeBinding:
    bq = repo.get_bigquery_binding(
        tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
    )
    drive = repo.get_drive_binding(
        tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
    )
    conflict = measurement_home_conflict(repo, workspace)
    if bq is None and drive is None:
        status = "UNBOUND"
    elif conflict:
        status = "CONFLICT"
    elif (bq is not None and bq.status == "ACTIVE") or (
        drive is not None and drive.status == "ACTIVE"
    ):
        status = "ACTIVE"
    else:
        status = (bq.status if bq is not None else drive.status) if drive or bq else "UNBOUND"
    created = None
    verified = None
    if bq is not None:
        created = bq.created_at
        verified = bq.last_verified_at
    elif drive is not None:
        created = drive.created_at
        verified = drive.last_verified_at
    return ProjectMeasurementHomeBinding(
        project_id=workspace.workspace_id,
        google_connection_id=(
            bq.connection_id if bq is not None else (drive.connection_id if drive else None)
        ),
        gcp_project_id=bq.destination_project_id if bq else None,
        bigquery_dataset_id=bq.destination_dataset_id if bq else None,
        drive_root_folder_id=drive.root_folder_id if drive else None,
        region=bq.location if bq else None,
        binding_status=status,
        namespace_conflict=conflict,
        created_at=created,
        verified_at=verified,
    )


class ProjectHomeAssembler:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        business_iq: BusinessIqService,
        data_foundation: DataFoundationService,
        model_ready: ModelReadyEvidenceResolver | None = None,
        modeling=None,
        optimization=None,
    ) -> None:
        self.repo = repo
        self.business_iq = business_iq
        self.data_foundation = data_foundation
        self.model_ready = model_ready
        self.modeling = modeling
        self.optimization = optimization

    def list_items(
        self, *, tenant_id: str, entitlement: EntitlementSnapshot
    ) -> list[ProjectListItem]:
        items: list[ProjectListItem] = []
        for workspace in self.repo.list_workspaces_for_tenant(tenant_id):
            home = self.build_home(workspace=workspace, entitlement=entitlement)
            items.append(
                ProjectListItem(
                    project=home.project,
                    foundation_state=home.data_foundation_summary.readiness,
                    active_tracks=[
                        track.track_type
                        for track in home.measurement_tracks
                        if track.availability
                        not in {
                            CapabilityAvailability.NOT_CONFIGURED.value,
                            CapabilityAvailability.UNAVAILABLE_ENTITLEMENT.value,
                        }
                    ],
                    attention_count=len(home.attention_items),
                    latest_activity_at=home.project.updated_at,
                    next_action=home.attention_items[0].next_action
                    if home.attention_items
                    else home.business_iq_summary.next_action,
                )
            )
        return items

    def build_home(
        self,
        *,
        workspace: Workspace,
        entitlement: EntitlementSnapshot,
        cycle_id: str | None = None,
    ) -> ProjectHomeReadModel | None:
        generated_at = datetime.now(UTC)
        selected, current, historical = self._select_cycle(workspace, cycle_id=cycle_id)
        if cycle_id is not None and selected is None:
            return None
        biq = self._business_iq_summary(workspace, cycle=selected, historical=historical)
        df = self._data_foundation_summary(workspace, cycle=selected, historical=historical)
        foundation_ready = df.readiness == DataFoundationReadyStatus.DATA_FOUNDATION_READY.value
        model_ready, latest_run_id = (
            (False, None) if historical else self._mmm_evidence(workspace)
        )
        tracks: list[MeasurementTrackSummary] = []
        if selected is not None:
            persisted = ensure_tracks_for_cycle(
                self.repo, workspace=workspace, cycle_id=selected.cycle_id
            )
            tracks = [
                self._track_summary(
                    track,
                    workspace=workspace,
                    entitlement=entitlement,
                    foundation_ready=foundation_ready,
                    model_ready=model_ready if not historical else bool(track.latest_run_id),
                    latest_run_id=latest_run_id if not historical else track.latest_run_id,
                )
                for track in persisted
            ]
        planning = self._planning(
            entitlement, False if historical else model_ready, workspace=workspace
        )
        attention = self._attention(workspace, biq, df, tracks, generated_at)
        return ProjectHomeReadModel(
            project=project_response(workspace),
            current_cycle=current,
            selected_cycle=selected,
            is_current_cycle=not historical,
            measurement_home=build_measurement_home(self.repo, workspace),
            business_iq_summary=biq,
            data_foundation_summary=df,
            measurement_tracks=tracks,
            planning_capabilities=planning,
            intelligence_summary=IntelligenceHomeSummary(generated_at=generated_at),
            attention_items=attention,
            recent_changes=self._recent_changes(workspace, selected, latest_run_id),
            generated_at=generated_at,
        )

    def business_iq_overview(
        self, *, workspace: Workspace, entitlement: EntitlementSnapshot
    ) -> BusinessIqOverviewReadModel:
        del entitlement
        generated_at = datetime.now(UTC)
        summary = self._business_iq_summary(workspace)
        profile = self.business_iq.store.get_profile(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        )
        considerations: list[str] = []
        if profile is not None:
            considerations = [item.statement for item in profile.measurement_objectives[:3]]
        return BusinessIqOverviewReadModel(
            project_id=workspace.workspace_id,
            readiness=summary.readiness,
            profile_summary={
                "brand_name": profile.business_identity.brand_name if profile else None,
                "kpi": profile.kpi if profile else None,
                "version": profile.version if profile else None,
            }
            if profile is not None
            else None,
            brief_summary=None,
            top_measurement_considerations=considerations,
            summary_counts={
                "channels": summary.channel_count,
                "markets": summary.market_count,
                "material_drivers": summary.material_driver_count,
                "open_questions": summary.high_priority_question_count,
            },
            evidence_summary={"facts": len(profile.facts) if profile else 0},
            open_question_summary={
                "count": summary.high_priority_question_count,
                "acknowledged_unknown": summary.acknowledged_unknown_count,
            },
            attention_items=[],
            next_actions=[summary.next_action] if summary.next_action else [],
            updated_at=summary.updated_at,
            generated_at=generated_at,
        )

    def data_foundation_overview(
        self, *, workspace: Workspace, entitlement: EntitlementSnapshot
    ) -> DataFoundationOverviewReadModel:
        generated_at = datetime.now(UTC)
        _selected, current_cycle, _historical = self._select_cycle(workspace, cycle_id=None)
        summary = self._data_foundation_summary(workspace, cycle=current_cycle)
        context = _df_context(self.repo, workspace)
        overview = self.data_foundation.get_overview(context)
        foundation_ready = (
            summary.readiness == DataFoundationReadyStatus.DATA_FOUNDATION_READY.value
        )
        model_ready, _ = self._mmm_evidence(workspace)
        actions = self._foundation_next_actions(
            entitlement=entitlement,
            foundation_ready=foundation_ready,
            model_ready=model_ready,
            df_action=summary.next_action,
        )
        return DataFoundationOverviewReadModel(
            project_id=workspace.workspace_id,
            readiness=summary.readiness,
            phase=overview.phase,
            connection_summary=[item.model_dump(mode="json") for item in overview.connections],
            source_summary={
                "required": summary.required_source_count,
                "healthy": summary.healthy_source_count,
                "review": summary.review_source_count,
                "blocked": summary.blocked_source_count,
            },
            quality_summary={"attention": summary.attention_count},
            coverage_summary={"shared_continuous_window": summary.shared_continuous_window},
            next_actions=actions,
            attention_items=[],
            last_refresh_at=summary.last_refresh_at,
            updated_at=summary.last_refresh_at,
            generated_at=generated_at,
        )

    def coverage(
        self, *, workspace: Workspace, cycle_id: str
    ) -> CoverageReadModel | None:
        assessment = self.data_foundation.store.get_coverage(cycle_id)
        if assessment is None:
            return None
        if (
            assessment.tenant_id != workspace.tenant_id
            or assessment.workspace_id != workspace.workspace_id
        ):
            return None
        generated_at = datetime.now(UTC)
        return CoverageReadModel(
            project_id=workspace.workspace_id,
            cycle_id=assessment.cycle_id,
            view=(
                assessment.view.value if hasattr(assessment.view, "value") else str(assessment.view)
            ),
            summary=assessment.summary.model_dump(mode="json"),
            series=[item.model_dump(mode="json") for item in assessment.series],
            gaps=[item.model_dump(mode="json") for item in assessment.gaps],
            assessed_at=assessment.assessed_at,
            generated_at=generated_at,
        )

    def _business_iq_summary(
        self,
        workspace: Workspace,
        *,
        cycle: MeasurementCycleSummary | None = None,
        historical: bool = False,
    ) -> BusinessIqHomeSummary:
        profile = self.business_iq.store.get_profile(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        )
        if profile is None:
            return BusinessIqHomeSummary(
                readiness="NOT_STARTED",
                next_action=next_action(
                    NextActionType.START_BUSINESS_IQ,
                    capability=CapabilityFamily.BUSINESS_IQ,
                    route_hint="business-iq",
                    priority=10,
                ),
            )
        source_profile = profile
        snapshot_id = profile.current_snapshot_id
        if historical and cycle is not None:
            snapshot = self.business_iq.store.get_snapshot(cycle.business_profile_snapshot_id)
            if (
                snapshot is None
                or snapshot.tenant_id != workspace.tenant_id
                or snapshot.workspace_id != workspace.workspace_id
            ):
                return BusinessIqHomeSummary(
                    readiness="NOT_READY",
                    profile_snapshot_id=cycle.business_profile_snapshot_id,
                    next_action=next_action(
                        NextActionType.OPEN_BUSINESS_IQ,
                        capability=CapabilityFamily.BUSINESS_IQ,
                        route_hint="business-iq",
                        priority=20,
                    ),
                )
            source_profile = snapshot.profile
            snapshot_id = snapshot.snapshot_id
            receipt = evaluate_business_context_ready(
                profile=source_profile,
                snapshot_id=snapshot_id,
                actor_id=source_profile.updated_by,
            )
        else:
            receipt = self.business_iq.evaluate_ready(
                tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
            )
        ready = receipt.status is BusinessContextReadyStatus.BUSINESS_CONTEXT_READY
        action = next_action(
            NextActionType.OPEN_BUSINESS_IQ if ready else NextActionType.CONTINUE_BUSINESS_IQ,
            capability=CapabilityFamily.BUSINESS_IQ,
            route_hint="business-iq",
            priority=20 if ready else 10,
        )
        return BusinessIqHomeSummary(
            readiness=receipt.status.value,
            profile_version=source_profile.version,
            profile_snapshot_id=snapshot_id,
            channel_count=len(source_profile.marketing_portfolio),
            market_count=len(source_profile.markets),
            material_driver_count=sum(
                1 for channel in source_profile.marketing_portfolio if channel.material
            ),
            acknowledged_unknown_count=sum(
                1 for gap in source_profile.knowledge_gaps if gap.acknowledged
            ),
            high_priority_question_count=sum(
                1 for gap in source_profile.knowledge_gaps if not gap.acknowledged
            ),
            updated_at=source_profile.updated_at,
            next_action=action,
        )

    def _data_foundation_summary(
        self,
        workspace: Workspace,
        *,
        cycle: MeasurementCycleSummary | None = None,
        historical: bool = False,
    ) -> DataFoundationHomeSummary:
        coverage = None
        if cycle is not None:
            coverage = self.data_foundation.store.get_coverage(cycle.cycle_id)
        if historical:
            return DataFoundationHomeSummary(
                readiness="NOT_STARTED",
                shared_continuous_window=(
                    coverage.summary.shared_continuous_window if coverage else None
                ),
                most_limiting_source=(
                    coverage.summary.most_limiting_requirement if coverage else None
                ),
                next_action=next_action(
                    NextActionType.OPEN_DATA_FOUNDATION,
                    capability=CapabilityFamily.DATA_FOUNDATION,
                    route_hint="data-foundation",
                    priority=30,
                ),
            )
        reqs = self.data_foundation.store.get_requirements(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        )
        required = len(reqs.requirements) if reqs else 0
        healthy = 0
        review = 0
        blocked = 0
        for binding in self.data_foundation.store.list_bindings(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        ):
            receipt = self.data_foundation.store.get_current_source_receipt(binding.source_id)
            if receipt is None:
                blocked += 1
                continue
            if receipt.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY:
                healthy += 1
            else:
                review += 1
        env = self.data_foundation.store.get_current_foundation_receipt(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        )
        if env and env.status_code is DataFoundationReadyStatus.DATA_FOUNDATION_READY:
            readiness = DataFoundationReadyStatus.DATA_FOUNDATION_READY.value
            action = next_action(
                NextActionType.OPEN_DATA_FOUNDATION,
                capability=CapabilityFamily.DATA_FOUNDATION,
                route_hint="data-foundation",
                priority=30,
            )
        elif required == 0:
            readiness = "NOT_STARTED"
            action = next_action(
                NextActionType.START_DATA_FOUNDATION,
                capability=CapabilityFamily.DATA_FOUNDATION,
                route_hint="data-foundation",
                priority=15,
            )
        else:
            readiness = "IN_PROGRESS"
            action = next_action(
                NextActionType.CONTINUE_DATA_FOUNDATION,
                capability=CapabilityFamily.DATA_FOUNDATION,
                route_hint="data-foundation",
                priority=15,
            )
        return DataFoundationHomeSummary(
            readiness=readiness,
            required_source_count=required,
            healthy_source_count=healthy,
            review_source_count=review,
            blocked_source_count=blocked,
            shared_continuous_window=(
                coverage.summary.shared_continuous_window if coverage else None
            ),
            last_refresh_at=env.executed_at if env is not None else None,
            most_limiting_source=coverage.summary.most_limiting_requirement if coverage else None,
            attention_count=review + blocked,
            next_action=action,
        )

    def _select_cycle(
        self, workspace: Workspace, *, cycle_id: str | None
    ) -> tuple[MeasurementCycleSummary | None, MeasurementCycleSummary | None, bool]:
        cycles = self.data_foundation.store.list_cycles(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        )
        if not cycles:
            return None, None, False
        latest = sorted(cycles, key=lambda item: item.updated_at, reverse=True)[0]
        current = self._cycle_summary(workspace, latest)
        if cycle_id is None:
            return current, current, False
        match = next((item for item in cycles if item.cycle_id == cycle_id), None)
        if match is None:
            return None, current, False
        if (
            match.tenant_id != workspace.tenant_id
            or match.workspace_id != workspace.workspace_id
        ):
            return None, current, False
        selected = self._cycle_summary(workspace, match)
        return selected, current, selected.cycle_id != current.cycle_id

    def _cycle_summary(self, workspace: Workspace, current) -> MeasurementCycleSummary:
        return MeasurementCycleSummary(
            cycle_id=current.cycle_id,
            project_id=workspace.workspace_id,
            name=current.name,
            cadence=(
                current.cadence.value if hasattr(current.cadence, "value") else str(current.cadence)
            ),
            data_cutoff=current.data_cutoff,
            data_cutoff_origin=(
                current.cutoff_origin.value
                if current.cutoff_origin is not None and hasattr(current.cutoff_origin, "value")
                else (str(current.cutoff_origin) if current.cutoff_origin else None)
            ),
            business_profile_snapshot_id=current.business_profile_snapshot_id,
            foundation_snapshot_ref=None,
            state=current.state,
            created_at=current.created_at,
            updated_at=current.updated_at,
        )

    def _mmm_evidence(self, workspace: Workspace) -> tuple[bool, str | None]:
        latest_run_id = None
        model_ready = False
        for dataset in self.repo.list_datasets_for_workspace(
            tenant_id=workspace.tenant_id, workspace_id=workspace.workspace_id
        ):
            for evaluation in self.repo.list_evaluations_for_dataset(
                tenant_id=workspace.tenant_id,
                workspace_id=workspace.workspace_id,
                dataset_id=dataset.dataset_id,
            ):
                latest_run_id = evaluation.run_id
                if self.model_ready is None:
                    continue
                evidence = self.model_ready.resolve(
                    tenant_id=evaluation.tenant_id,
                    workspace_id=evaluation.workspace_id,
                    dataset_id=evaluation.dataset_id,
                    run_id=evaluation.run_id,
                )
                if evidence is not None:
                    model_ready = True
                    latest_run_id = evaluation.run_id
        return model_ready, latest_run_id

    def _track_summary(
        self,
        track: MeasurementTrack,
        *,
        workspace: Workspace,
        entitlement: EntitlementSnapshot,
        foundation_ready: bool,
        model_ready: bool,
        latest_run_id: str | None,
    ) -> MeasurementTrackSummary:
        if track.track_type is MeasurementTrackType.MMM:
            status, availability, domain, action_type = mmm_adapter_state(
                foundation_ready=foundation_ready,
                model_ready=model_ready,
                latest_run_id=latest_run_id,
                entitled=entitled_for_capability(entitlement, CapabilityFamily.MMM),
                modeling_stage=_modeling_stage(self.modeling, workspace, track),
            )
            context: list[str] = []
            engine = DEFAULT_MMM_ENGINE
            run_id = latest_run_id
            domain_state = domain
        elif track.track_type is MeasurementTrackType.MTA:
            status, availability, context, action_type = mta_availability(
                entitled=entitled_for_capability(entitlement, CapabilityFamily.MTA),
                foundation_ready=foundation_ready,
                ga4_dataset_id=track.config.get("ga4_dataset_id"),
                key_event_name=track.config.get("key_event_name"),
                channel_grouping_version=track.config.get("channel_grouping_version"),
                mta_input_ready=str(track.input_readiness_state or "") == "MTA_INPUT_READY"
                or str(track.config.get("domain_stage") or "") == "MTA_INPUT_READY",
            )
            engine = None
            run_id = None
            domain_state = track.config.get("domain_stage")
        else:
            configured = bool(
                track.config.get("target_metric") or track.config.get("forecast_horizon")
            )
            status, availability, action_type = forecast_availability(
                entitled=entitled_for_capability(entitlement, CapabilityFamily.FORECASTING),
                foundation_ready=foundation_ready,
                configured=configured,
            )
            context = []
            engine = None
            run_id = None
            domain_state = None
        if track.status is not status:
            self.repo.put_measurement_track(
                apply_track_mutation(track, metadata={"status": status})
            )
        capability = {
            MeasurementTrackType.MMM: CapabilityFamily.MMM,
            MeasurementTrackType.MTA: CapabilityFamily.MTA,
            MeasurementTrackType.FORECAST: CapabilityFamily.FORECASTING,
        }[track.track_type]
        return MeasurementTrackSummary(
            track_id=track.track_id,
            track_type=track.track_type.value,
            display_name=TRACK_DISPLAY[track.track_type],
            engine=engine,
            availability=availability.value,
            domain_state=domain_state,
            latest_run_id=run_id,
            context_items=context,
            attention_count=0 if availability is CapabilityAvailability.READY else 1,
            next_action=next_action(action_type, capability=capability),
            updated_at=track.updated_at,
        )

    def _planning(
        self,
        entitlement: EntitlementSnapshot,
        model_ready: bool,
        *,
        workspace: Workspace,
    ) -> list[PlanningCapabilitySummary]:
        accepted = False
        if self.modeling is not None:
            accepted = self.modeling.has_accepted_model(
                tenant_id=workspace.tenant_id, project_id=workspace.workspace_id
            )
        rows: list[PlanningCapabilitySummary] = []
        for capability in (
            CapabilityFamily.INVESTMENT_PLAN,
            CapabilityFamily.FORECASTING,
            CapabilityFamily.SCENARIO_SIMULATION,
            CapabilityFamily.BUDGET_OPTIMIZATION,
        ):
            availability, action_type = planning_availability(
                capability=capability,
                entitled=entitled_for_capability(entitlement, capability),
                model_ready=model_ready,
                model_accepted=accepted,
            )
            reason = None
            availability_value = availability.value
            if availability is CapabilityAvailability.UNAVAILABLE_ENTITLEMENT:
                reason = "Not included in the current plan"
            elif (
                not accepted
                and capability is CapabilityFamily.SCENARIO_SIMULATION
            ):
                availability_value = "REQUIRES_SUPPORTED_BASELINE"
                reason = "Requires a supported measurement baseline"
            elif (
                not accepted
                and capability is CapabilityFamily.BUDGET_OPTIMIZATION
            ):
                availability_value = "REQUIRES_ACCEPTED_MMM_MODEL"
                reason = "Requires an accepted MMM model"
            elif accepted and capability is CapabilityFamily.BUDGET_OPTIMIZATION:
                generated = None
                if self.optimization is not None:
                    generated = self.optimization.latest_status(
                        tenant_id=workspace.tenant_id,
                        project_id=workspace.workspace_id,
                    )
                if generated in {
                    "OPTIMIZATION_READY",
                    "NOT_READY",
                    "REVIEW_REQUIRED",
                    "NOT_CONFIGURED",
                    "STALE",
                }:
                    availability_value = (
                        "NOT_READY" if generated == "STALE" else generated
                    )
                    if generated == "OPTIMIZATION_READY":
                        reason = "Optimization readiness is available"
                    elif generated == "STALE":
                        reason = "Optimization readiness is stale"
                    else:
                        reason = "Optimization is not ready"
            rows.append(
                PlanningCapabilitySummary(
                    capability=capability.value,
                    availability=availability_value,
                    dependency_reason=reason,
                    next_action=next_action(action_type, capability=capability),
                )
            )
        return rows

    def _foundation_next_actions(
        self,
        *,
        entitlement: EntitlementSnapshot,
        foundation_ready: bool,
        model_ready: bool,
        df_action: NextAction | None,
    ) -> list[NextAction]:
        actions: list[NextAction] = []
        if df_action is not None:
            actions.append(df_action)
        if not foundation_ready:
            return actions
        if entitled_for_capability(entitlement, CapabilityFamily.MMM):
            actions.append(
                next_action(
                    NextActionType.REVIEW_MMM if model_ready else NextActionType.CONTINUE_MMM,
                    capability=CapabilityFamily.MMM,
                )
            )
        if entitled_for_capability(entitlement, CapabilityFamily.MTA):
            actions.append(next_action(NextActionType.SETUP_MTA, capability=CapabilityFamily.MTA))
        if entitled_for_capability(entitlement, CapabilityFamily.FORECASTING):
            actions.append(
                next_action(NextActionType.SETUP_FORECAST, capability=CapabilityFamily.FORECASTING)
            )
        actions.append(
            next_action(NextActionType.RETURN_PROJECT_HOME, capability=CapabilityFamily.FOUNDATION)
        )
        return actions

    def _attention(
        self,
        workspace: Workspace,
        biq: BusinessIqHomeSummary,
        df: DataFoundationHomeSummary,
        tracks: list[MeasurementTrackSummary],
        generated_at: datetime,
    ) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        if biq.readiness != BusinessContextReadyStatus.BUSINESS_CONTEXT_READY.value:
            items.append(
                AttentionItem(
                    attention_id=f"att_biq_{workspace.workspace_id}",
                    severity=AttentionSeverity.REVIEW.value,
                    title="Business IQ is incomplete",
                    summary="Complete Business IQ before treating Foundation as ready.",
                    owning_capability=CapabilityFamily.BUSINESS_IQ.value,
                    next_action=biq.next_action,
                    created_at=generated_at,
                    state=AttentionState.OPEN.value,
                )
            )
        if df.readiness != DataFoundationReadyStatus.DATA_FOUNDATION_READY.value:
            items.append(
                AttentionItem(
                    attention_id=f"att_df_{workspace.workspace_id}",
                    severity=AttentionSeverity.REVIEW.value,
                    title="Data Foundation needs work",
                    summary="Foundation sources are not fully ready.",
                    owning_capability=CapabilityFamily.DATA_FOUNDATION.value,
                    next_action=df.next_action,
                    created_at=generated_at,
                    state=AttentionState.OPEN.value,
                )
            )
        for track in tracks:
            if track.track_type == "MTA" and "Key event not selected" in track.context_items:
                items.append(
                    AttentionItem(
                        attention_id=f"att_mta_{track.track_id}",
                        severity=AttentionSeverity.INFO.value,
                        title="MTA key event not selected",
                        summary="GA4 configuration can continue once a key event is chosen.",
                        owning_capability=CapabilityFamily.MTA.value,
                        next_action=track.next_action,
                        created_at=generated_at,
                        state=AttentionState.OPEN.value,
                    )
                )
        home = build_measurement_home(self.repo, workspace)
        if home.namespace_conflict:
            items.append(
                AttentionItem(
                    attention_id=f"att_home_{workspace.workspace_id}",
                    severity=AttentionSeverity.BLOCKER.value,
                    title="Measurement Home namespace conflict",
                    summary=(
                        "Another active Project already claims this GCP project "
                        "prem3_modeling dataset."
                    ),
                    owning_capability=CapabilityFamily.FOUNDATION.value,
                    created_at=generated_at,
                    state=AttentionState.OPEN.value,
                )
            )
        return items

    def _recent_changes(
        self,
        workspace: Workspace,
        cycle: MeasurementCycleSummary | None,
        latest_run_id: str | None,
    ) -> list[RecentChange]:
        events: list[RecentChange] = []
        events.append(
            RecentChange(
                event_id=f"evt_project_{workspace.workspace_id}",
                event_type="PROJECT_UPDATED",
                title="Project updated",
                occurred_at=workspace.updated_at,
                capability=CapabilityFamily.FOUNDATION.value,
                resource_ref=workspace.workspace_id,
            )
        )
        if cycle is not None:
            events.append(
                RecentChange(
                    event_id=f"evt_cycle_{cycle.cycle_id}",
                    event_type="MEASUREMENT_CYCLE",
                    title=f"Cycle {cycle.name}",
                    occurred_at=cycle.updated_at,
                    capability=CapabilityFamily.DATA_FOUNDATION.value,
                    resource_ref=cycle.cycle_id,
                )
            )
        if latest_run_id is not None:
            events.append(
                RecentChange(
                    event_id=f"evt_run_{latest_run_id}",
                    event_type="EVALUATION",
                    title="Evaluation accepted",
                    occurred_at=workspace.updated_at,
                    capability=CapabilityFamily.MMM.value,
                    resource_ref=latest_run_id,
                )
            )
        events.sort(key=lambda item: item.occurred_at, reverse=True)
        return events[:10]


def planner_allows_draft(plan_id: str) -> bool:
    return plan_id != PlanId.PLANNER
