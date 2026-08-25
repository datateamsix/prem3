"""MeasurementTrack persistence helpers and methodology adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.control_plane.ids import new_track_id
from app.control_plane.models import (
    MeasurementTrack,
    MeasurementTrackStatus,
    MeasurementTrackType,
    TrackConfigRevision,
    Workspace,
)
from app.control_plane.repository import ControlPlaneRepository
from app.core.errors import ProviderMappingConflictError, TrackConfigurationImmutableError
from app.project.enums import (
    DEFAULT_MMM_ENGINE,
    CapabilityAvailability,
    CapabilityFamily,
    NextActionType,
)

EMPTY_MTA_CONFIG: dict[str, Any] = {
    "ga4_property_id": None,
    "ga4_dataset_id": None,
    "key_event_name": None,
    "conversion_period_start": None,
    "conversion_period_end": None,
    "lookback_window_days": None,
    "identity_strategy": None,
    "sessionization_policy": None,
    "direct_treatment": None,
    "channel_grouping_version": None,
    "conversion_value_strategy": None,
    "include_nonconverting_paths": None,
    "attribution_models": [],
}

EMPTY_FORECAST_CONFIG: dict[str, Any] = {
    "target_metric": None,
    "frequency": None,
    "training_window": None,
    "forecast_horizon": None,
    "features": [],
    "known_future_events": [],
    "validation_strategy": None,
    "model_family": None,
}

_DEFAULT_CONFIG: dict[MeasurementTrackType, dict[str, Any]] = {
    MeasurementTrackType.MMM: {"engine": DEFAULT_MMM_ENGINE},
    MeasurementTrackType.MTA: EMPTY_MTA_CONFIG,
    MeasurementTrackType.FORECAST: EMPTY_FORECAST_CONFIG,
}


def default_config(track_type: MeasurementTrackType) -> dict[str, Any]:
    return dict(_DEFAULT_CONFIG[track_type])


def ensure_tracks_for_cycle(
    repo: ControlPlaneRepository,
    *,
    workspace: Workspace,
    cycle_id: str,
) -> list[MeasurementTrack]:
    existing = repo.list_measurement_tracks(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.workspace_id,
        cycle_id=cycle_id,
    )
    by_type = {track.track_type: track for track in existing}
    now = datetime.now(UTC)
    created: list[MeasurementTrack] = []
    for track_type in (
        MeasurementTrackType.MMM,
        MeasurementTrackType.MTA,
        MeasurementTrackType.FORECAST,
    ):
        current = by_type.get(track_type)
        if current is not None:
            created.append(current)
            continue
        track = MeasurementTrack(
            track_id=new_track_id(),
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.workspace_id,
            cycle_id=cycle_id,
            track_type=track_type,
            status=MeasurementTrackStatus.NOT_CONFIGURED,
            configuration_version=1,
            config=default_config(track_type),
            created_at=now,
            updated_at=now,
        )
        try:
            created.append(repo.put_measurement_track(track))
        except ProviderMappingConflictError:
            reloaded = {
                item.track_type: item
                for item in repo.list_measurement_tracks(
                    tenant_id=workspace.tenant_id,
                    workspace_id=workspace.workspace_id,
                    cycle_id=cycle_id,
                )
            }
            winner = reloaded.get(track_type)
            if winner is None:
                raise
            created.append(winner)
    return created


_METADATA_KEYS = frozenset(
    {
        "status",
        "updated_at",
        "input_readiness_state",
        "readiness_receipt_ref",
        "latest_run_id",
        "accepted_artifact_id",
        "consumed_run_versions",
        "config_revisions",
    }
)


def apply_track_mutation(
    track: MeasurementTrack,
    *,
    config: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    consume_run_id: str | None = None,
) -> MeasurementTrack:
    """Apply a Track update without silently rewriting a consumed configuration."""
    now = datetime.now(UTC)
    updates: dict[str, Any] = {"updated_at": now}
    if metadata:
        unexpected = set(metadata) - _METADATA_KEYS
        if unexpected:
            raise TrackConfigurationImmutableError(
                "Unsupported MeasurementTrack metadata update."
            )
        updates.update(metadata)
    next_config = dict(track.config) if config is None else dict(config)
    if next_config == track.config:
        if consume_run_id:
            versions = dict(track.consumed_run_versions)
            versions[consume_run_id] = track.configuration_version
            updates["consumed_run_versions"] = versions
            updates["latest_run_id"] = consume_run_id
        return track.model_copy(update=updates)
    if track.is_consumed() and "configuration_version" not in (metadata or {}):
        revisions = list(track.config_revisions)
        if not any(item.configuration_version == track.configuration_version for item in revisions):
            revisions.append(
                TrackConfigRevision(
                    configuration_version=track.configuration_version,
                    config=dict(track.config),
                    consumed_by_run_id=track.latest_run_id,
                    created_at=now,
                )
            )
        updates["config_revisions"] = tuple(revisions)
        updates["configuration_version"] = track.configuration_version + 1
        updates["config"] = next_config
        return track.model_copy(update=updates)
    updates["config"] = next_config
    updates["configuration_version"] = track.configuration_version + 1
    return track.model_copy(update=updates)


def resolve_track_config_for_run(track: MeasurementTrack, run_id: str) -> dict[str, Any]:
    version = track.consumed_run_versions.get(run_id)
    if version is None and track.latest_run_id == run_id:
        version = track.configuration_version
    if version is None:
        raise TrackConfigurationImmutableError(
            "Run is not bound to a consumed MeasurementTrack configuration."
        )
    if version == track.configuration_version:
        return dict(track.config)
    for revision in track.config_revisions:
        if revision.configuration_version == version:
            return dict(revision.config)
    raise TrackConfigurationImmutableError(
        "Consumed MeasurementTrack configuration revision is missing."
    )


def mmm_adapter_state(
    *,
    foundation_ready: bool,
    model_ready: bool,
    latest_run_id: str | None,
    entitled: bool,
    modeling_stage: str | None = None,
) -> tuple[MeasurementTrackStatus, CapabilityAvailability, str | None, NextActionType]:
    if not entitled:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.UNAVAILABLE_ENTITLEMENT,
            None,
            NextActionType.CONTINUE_MMM,
        )
    if modeling_stage == "MODEL_ACCEPTED":
        return (
            MeasurementTrackStatus.COMPLETE,
            CapabilityAvailability.READY,
            "MODEL_ACCEPTED",
            NextActionType.REVIEW_MMM,
        )
    if modeling_stage in {
        "DESIGNING_MODEL",
        "AWAITING_ASSUMPTION_DECISIONS",
        "READY_TO_FIT",
        "FITTING_MODEL",
        "AWAITING_MODEL_REVIEW",
    }:
        return (
            MeasurementTrackStatus.RUNNING,
            CapabilityAvailability.IN_PROGRESS,
            modeling_stage,
            NextActionType.CONTINUE_MMM,
        )
    if model_ready:
        return (
            MeasurementTrackStatus.COMPLETE,
            CapabilityAvailability.READY,
            "MODEL_READY",
            NextActionType.REVIEW_MMM,
        )
    if not foundation_ready:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.NEEDS_FOUNDATION,
            None,
            NextActionType.CONTINUE_DATA_FOUNDATION,
        )
    if latest_run_id:
        return (
            MeasurementTrackStatus.RUNNING,
            CapabilityAvailability.IN_PROGRESS,
            None,
            NextActionType.CONTINUE_MMM,
        )
    return (
        MeasurementTrackStatus.READY_TO_RUN,
        CapabilityAvailability.AVAILABLE_TO_CONFIGURE,
        None,
        NextActionType.CONTINUE_MMM,
    )


def mta_availability(
    *,
    entitled: bool,
    foundation_ready: bool,
    ga4_dataset_id: str | None,
    key_event_name: str | None,
    mta_input_ready: bool = False,
    channel_grouping_version: str | None = None,
) -> tuple[MeasurementTrackStatus, CapabilityAvailability, list[str], NextActionType]:
    context: list[str] = []
    if not entitled:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.UNAVAILABLE_ENTITLEMENT,
            context,
            NextActionType.SETUP_MTA,
        )
    if not foundation_ready:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.NEEDS_FOUNDATION,
            context,
            NextActionType.CONTINUE_DATA_FOUNDATION,
        )
    if ga4_dataset_id:
        context.append("GA4 dataset detected")
    else:
        context.append("GA4 dataset not selected")
    if key_event_name:
        context.append("Key event selected")
    else:
        context.append("Key event not selected")
    if channel_grouping_version:
        context.append(f"Channel grouping {channel_grouping_version}")
    else:
        context.append("Channel grouping not approved")
    if mta_input_ready:
        context.append("MTA_INPUT_READY")
        return (
            MeasurementTrackStatus.READY_TO_RUN,
            CapabilityAvailability.IN_PROGRESS,
            context,
            NextActionType.OPEN_MTA,
        )
    if not key_event_name:
        return (
            MeasurementTrackStatus.AVAILABLE_TO_CONFIGURE,
            CapabilityAvailability.AVAILABLE_TO_CONFIGURE,
            context,
            NextActionType.SELECT_MTA_KEY_EVENT if ga4_dataset_id else NextActionType.SETUP_MTA,
        )
    return (
        MeasurementTrackStatus.AVAILABLE_TO_CONFIGURE,
        CapabilityAvailability.AVAILABLE_TO_CONFIGURE,
        context,
        NextActionType.OPEN_MTA,
    )


def forecast_availability(
    *,
    entitled: bool,
    foundation_ready: bool,
    configured: bool,
) -> tuple[MeasurementTrackStatus, CapabilityAvailability, NextActionType]:
    if not entitled:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.UNAVAILABLE_ENTITLEMENT,
            NextActionType.SETUP_FORECAST,
        )
    if not foundation_ready:
        return (
            MeasurementTrackStatus.BLOCKED,
            CapabilityAvailability.NEEDS_FOUNDATION,
            NextActionType.CONTINUE_DATA_FOUNDATION,
        )
    if configured:
        return (
            MeasurementTrackStatus.READY_TO_RUN,
            CapabilityAvailability.IN_PROGRESS,
            NextActionType.SETUP_FORECAST,
        )
    return (
        MeasurementTrackStatus.AVAILABLE_TO_CONFIGURE,
        CapabilityAvailability.AVAILABLE_TO_CONFIGURE,
        NextActionType.SETUP_FORECAST,
    )


def planning_availability(
    *,
    capability: CapabilityFamily,
    entitled: bool,
    model_ready: bool,
    model_accepted: bool = False,
) -> tuple[CapabilityAvailability, NextActionType]:
    if not entitled:
        return (
            CapabilityAvailability.UNAVAILABLE_ENTITLEMENT,
            NextActionType.VIEW_SCENARIO_REQUIREMENTS,
        )
    if capability is CapabilityFamily.FORECASTING:
        return CapabilityAvailability.AVAILABLE_TO_CONFIGURE, NextActionType.SETUP_FORECAST
    del model_ready
    if model_accepted:
        return CapabilityAvailability.AVAILABLE_TO_CONFIGURE, NextActionType.RETURN_PROJECT_HOME
    if capability is CapabilityFamily.SCENARIO_SIMULATION:
        return (
            CapabilityAvailability.NEEDS_ACCEPTED_MODEL,
            NextActionType.VIEW_SCENARIO_REQUIREMENTS,
        )
    if capability is CapabilityFamily.BUDGET_OPTIMIZATION:
        return (
            CapabilityAvailability.NEEDS_ACCEPTED_MODEL,
            NextActionType.VIEW_OPTIMIZATION_REQUIREMENTS,
        )
    return CapabilityAvailability.NOT_CONFIGURED, NextActionType.RETURN_PROJECT_HOME
