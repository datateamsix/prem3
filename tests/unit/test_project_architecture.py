"""Project domain, Home read model, tracks, and entitlement compatibility."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import pytest

from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.ids import new_google_connection_id, new_run_id, new_track_id
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.models import (
    BigQueryWorkspaceBinding,
    DatasetEvaluationRef,
    DriveWorkspaceBinding,
    EntitlementSource,
    EvaluationStatus,
    Feature,
    MeasurementTrack,
    MeasurementTrackStatus,
    MeasurementTrackType,
    WorkspaceStatus,
)
from app.core.errors import (
    MeasurementHomeConflictError,
    ProviderMappingConflictError,
    TrackConfigurationImmutableError,
)
from app.data_foundation.contracts import (
    CoverageAssessment,
    CoverageSummary,
    DataFoundationReadyReceipt,
    EvidenceRequirement,
    EvidenceRequirementSet,
    MeasurementCycle,
    ResourceIdentity,
    SourceBinding,
    SourceContract,
    SourceFoundationReceipt,
)
from app.data_foundation.enums import (
    CoverageView,
    CycleCadence,
    DataFoundationReadyStatus,
    EvidenceRequirementType,
    LocationType,
    SourceFoundationStatus,
)
from app.project.capabilities import entitled_for_capability
from app.project.enums import CapabilityFamily
from app.project.measurement_home import require_usable_measurement_home
from app.project.tracks import (
    apply_track_mutation,
    ensure_tracks_for_cycle,
    resolve_track_config_for_run,
)
from app.publish_execution.contracts import ModelReadyEvidence
from app.publish_execution.model_ready import InMemoryModelReadyEvidenceResolver
from app.service.errors import APIError
from app.service.measurement_home_guard import deny_conflicted_measurement_home
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.business_iq.conftest import ready_payload


def _now() -> datetime:
    return datetime.now(UTC)


def _music_center_biq_payload() -> dict:
    payload = ready_payload()
    payload["business_identity"] = {
        "legal_name": "Music Center",
        "brand_name": "Music Center",
    }
    return payload


def test_workspace_endpoints_still_function() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/workspaces", headers=auth_header(), json={"name": "Music Center"})
    assert created.status_code == 201
    workspace_id = created.json()["workspace_id"]
    assert created.json()["project_id"] == workspace_id
    listed = client.get("/v1/workspaces", headers=auth_header())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["workspace_id"] == workspace_id
    fetched = client.get(f"/v1/workspaces/{workspace_id}", headers=auth_header())
    assert fetched.status_code == 200


def test_project_and_workspace_are_the_same_store() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post(
        "/v1/projects",
        headers=auth_header(),
        json={"name": "Music Center", "scope_type": "BRAND", "primary_market": "US"},
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]
    assert project_id == created.json()["workspace_id"]
    via_workspace = client.get(f"/v1/workspaces/{project_id}", headers=auth_header())
    via_project = client.get(f"/v1/projects/{project_id}", headers=auth_header())
    assert via_workspace.status_code == 200
    assert via_project.status_code == 200
    assert via_workspace.json()["workspace_id"] == via_project.json()["project_id"]
    assert via_project.json()["scope_type"] == "BRAND"


def test_project_capacity_enforced() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    first = client.post("/v1/projects", headers=auth_header(), json={"name": "One"})
    second = client.post("/v1/projects", headers=auth_header(), json={"name": "Two"})
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "PROJECT_LIMIT_REACHED"


def test_project_a_cannot_resolve_project_b() -> None:
    repo = InMemoryControlPlaneRepository()
    _a, identity_a = seed_tenant(
        repo, provider_org="org_a", provider_user="user_a", plan_id=PlanId.PROJECT
    )
    _b, identity_b = seed_tenant(
        repo,
        display_name="B",
        provider_org="org_b",
        provider_user="user_b",
        plan_id=PlanId.PROJECT,
    )
    client_b, _ = make_client(repo=repo, identity=identity_b)
    created = client_b.post("/v1/projects", headers=auth_header(), json={"name": "Only B"}).json()
    client_a, _ = make_client(repo=repo, identity=identity_a)
    missing = client_a.get(f"/v1/projects/{created['project_id']}", headers=auth_header())
    home = client_a.get(f"/v1/projects/{created['project_id']}/home", headers=auth_header())
    assert missing.status_code == 404
    assert home.status_code == 404


def test_archive_stops_counting_toward_capacity() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Live"}).json()
    archived = client.patch(
        f"/v1/projects/{created['project_id']}",
        headers=auth_header(),
        json={"status": "ARCHIVED"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"
    assert repo.get_tenant(tenant.tenant_id).active_workspace_count == 0
    second = client.post("/v1/projects", headers=auth_header(), json={"name": "Next"})
    assert second.status_code == 201


def test_track_uniqueness_and_isolation() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant_a, identity_a = seed_tenant(repo, plan_id=PlanId.PORTFOLIO)
    tenant_b, identity_b = seed_tenant(
        repo,
        display_name="B",
        provider_org="org_b",
        provider_user="user_b",
        plan_id=PlanId.PROJECT,
    )
    client_a, _ = make_client(repo=repo, identity=identity_a)
    project_a = client_a.post("/v1/projects", headers=auth_header(), json={"name": "A"}).json()
    listed = client_a.get(
        f"/v1/projects/{project_a['project_id']}/cycles/cyc_q3_2026/tracks",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    types = [item["track_type"] for item in listed.json()["items"]]
    assert types == ["MMM", "MTA", "FORECAST"]
    first_id = listed.json()["items"][0]["track_id"]
    listed_again = client_a.get(
        f"/v1/projects/{project_a['project_id']}/cycles/cyc_q3_2026/tracks",
        headers=auth_header(),
    )
    assert listed_again.json()["items"][0]["track_id"] == first_id
    client_b, _ = make_client(repo=repo, identity=identity_b)
    foreign = client_b.get(
        f"/v1/projects/{project_a['project_id']}/cycles/cyc_q3_2026/tracks",
        headers=auth_header(),
    )
    assert foreign.status_code == 404
    del tenant_a, tenant_b


def test_old_entitlement_snapshot_still_maps_paid_capabilities() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, _identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    old = entitlement_for_plan(
        tenant_id=tenant.tenant_id,
        plan_id=PlanId.PROJECT,
        source=EntitlementSource.MANUAL_GRANT,
    )
    legacy = old.model_copy(
        update={
            "features": frozenset(
                {
                    Feature.PROJECT_CREATE,
                    Feature.DATASET_ASSESSMENT,
                    Feature.MERIDIAN_INTEGRATION,
                }
            )
        }
    )
    assert entitled_for_capability(legacy, CapabilityFamily.MMM) is True
    assert entitled_for_capability(legacy, CapabilityFamily.MTA) is True
    planner = entitlement_for_plan(
        tenant_id=tenant.tenant_id,
        plan_id=PlanId.PLANNER,
        source=EntitlementSource.DEFAULT,
    )
    assert entitled_for_capability(planner, CapabilityFamily.MMM) is False


def test_me_exposes_project_and_entitlement_summaries() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post(
        "/v1/projects", headers=auth_header(), json={"name": "Music Center"}
    ).json()
    me = client.get("/v1/me", headers=auth_header()).json()
    assert set(me) >= {
        "user",
        "organization",
        "plan",
        "project_capacity",
        "organizations",
        "current_organization",
        "project_summaries",
        "entitlement_summary",
    }
    assert me["user"]["user_id"] == identity.provider_user_id
    assert me["organization"]["tenant_id"] == tenant.tenant_id
    assert me["organization"]["display_name"] == "Acme"
    assert me["current_organization"] == me["organization"]
    assert me["organizations"] == [me["organization"]]
    assert me["plan"]["plan_id"] == "project"
    assert me["project_capacity"] == {
        "active_projects": 1,
        "max_active_projects": 1,
        "remaining_projects": 0,
    }
    assert me["project_summaries"] == [
        {
            "project_id": created["project_id"],
            "name": "Music Center",
            "status": "ACTIVE",
        }
    ]
    assert me["entitlement_summary"]["plan_id"] == "project"
    assert "mmm" in me["entitlement_summary"]["capabilities"]
    assert "mta" in me["entitlement_summary"]["capabilities"]
    assert "forecasting" in me["entitlement_summary"]["capabilities"]
    org = client.get("/v1/organization", headers=auth_header())
    assert org.status_code == 200
    body = org.json()
    assert body["current_plan"] == "project"
    assert body["active_project_count"] == 1
    assert body["max_active_projects"] == 1
    assert "cus_" not in str(body)
    assert "org_" not in body.get("display_name", "")


HOME_SEAMS = {
    "project",
    "current_cycle",
    "selected_cycle",
    "is_current_cycle",
    "measurement_home",
    "business_iq_summary",
    "data_foundation_summary",
    "measurement_tracks",
    "planning_capabilities",
    "intelligence_summary",
    "attention_items",
    "recent_changes",
    "generated_at",
}


def _bind_measurement_home(
    repo: InMemoryControlPlaneRepository,
    *,
    tenant_id: str,
    workspace_id: str,
    gcp_project_id: str = "acme-analytics",
    connection_id: str | None = None,
) -> None:
    now = _now()
    connection_id = connection_id or new_google_connection_id()
    repo.put_bigquery_binding(
        BigQueryWorkspaceBinding(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            source_project_ids=(gcp_project_id,),
            source_dataset_ids=("src",),
            destination_project_id=gcp_project_id,
            destination_dataset_id="prem3_modeling",
            location="US",
            read_verified=True,
            write_verified=True,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            last_verified_at=now,
        )
    )
    repo.put_drive_binding(
        DriveWorkspaceBinding(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            root_folder_id="fld_root_music",
            imports_folder_id="fld_imports_music",
            exports_folder_id="fld_exports_music",
            reports_folder_id="fld_reports_music",
            status="ACTIVE",
            import_enabled=True,
            export_enabled=True,
            created_at=now,
            updated_at=now,
            last_verified_at=now,
        )
    )


def _seed_df_home_aggregate(client, workspace_id: str, tenant_id: str, cycle_id: str) -> None:
    store = client.app.state.data_foundation.store
    now = _now()
    store.put_requirements(
        EvidenceRequirementSet(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            snapshot_id="bps_music_fixture000001",
            snapshot_fingerprint="fp_music_fixture",
            compiled_at=now,
            requirements=(
                EvidenceRequirement(
                    requirement_id="req_media_music",
                    requirement_type=EvidenceRequirementType.MEDIA,
                    concept="paid_media",
                    business_role="spend",
                    expected_category="media",
                ),
                EvidenceRequirement(
                    requirement_id="req_kpi_music",
                    requirement_type=EvidenceRequirementType.KPI,
                    concept="revenue",
                    business_role="kpi",
                    expected_category="kpi",
                ),
            ),
        )
    )
    store.put_binding(
        SourceBinding(
            source_id="dfsrc_musicmedia00000001",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            requirement_id="req_media_music",
            provider_id="google_ads",
            location_type=LocationType.BIGQUERY,
            resource=ResourceIdentity(
                location_type=LocationType.BIGQUERY,
                project_id="acme-analytics",
                dataset_id="src",
                table_id="google_ads",
                logical_path="acme-analytics.src.google_ads",
            ),
            contract=SourceContract(grain="daily"),
            lifecycle_state="BOUND",
            created_at=now,
            updated_at=now,
        )
    )
    store.put_source_receipt(
        SourceFoundationReceipt(
            receipt_id="rcpt_src_music000000001",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_ids=("dfsrc_musicmedia00000001",),
            executed_at=now,
            executed_by="test",
            status=SourceFoundationStatus.FOUNDATION_SOURCE_READY.value,
            status_code=SourceFoundationStatus.FOUNDATION_SOURCE_READY,
            governance_import_ready=True,
            premodel_review_remaining=False,
        )
    )
    store.put_coverage(
        CoverageAssessment(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            cycle_id=cycle_id,
            view=CoverageView.REQUIRED_EVIDENCE,
            series=(),
            gaps=(),
            summary=CoverageSummary(
                required_sources_meeting_target=1,
                continuity_issue_count=0,
                shared_continuous_window="2023-07/2026-06",
                shared_continuous_window_start="2023-07",
                shared_continuous_window_end="2026-06",
                most_limiting_requirement="req_media_music",
            ),
            assessed_at=now,
        )
    )


def _seed_foundation_ready(
    client, workspace_id: str, tenant_id: str, *, snapshot_id: str = "snap_music"
) -> None:
    store = client.app.state.data_foundation.store
    store.put_foundation_receipt(
        DataFoundationReadyReceipt(
            receipt_id="rcpt_df_ready",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_ids=(),
            executed_at=_now(),
            executed_by="test",
            status="DATA_FOUNDATION_READY",
            status_code=DataFoundationReadyStatus.DATA_FOUNDATION_READY,
            required_sources_ready=1,
        )
    )
    store.put_cycle(
        MeasurementCycle(
            cycle_id="cyc_q3_2026",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name="Q3 2026",
            cadence=CycleCadence.QUARTERLY,
            data_cutoff="2026-09-30",
            business_profile_snapshot_id=snapshot_id,
            created_at=_now(),
            updated_at=_now(),
            created_by="test",
            state="OPEN",
        )
    )


def test_project_home_established_music_center() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post(
        "/v1/projects",
        headers=auth_header(),
        json={
            "name": "Music Center",
            "scope_type": "BRAND",
            "brand_name": "Music Center",
            "primary_market": "US",
            "markets": ["US"],
        },
    ).json()
    workspace_id = created["project_id"]
    profile = client.post(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json=_music_center_biq_payload(),
    )
    assert profile.status_code == 200
    snapshot_id = profile.json()["current_snapshot_id"]
    _seed_foundation_ready(
        client, workspace_id, tenant.tenant_id, snapshot_id=snapshot_id
    )
    _seed_df_home_aggregate(client, workspace_id, tenant.tenant_id, "cyc_q3_2026")
    _bind_measurement_home(
        repo, tenant_id=tenant.tenant_id, workspace_id=workspace_id
    )
    dataset = repo.create_dataset(
        tenant_id=tenant.tenant_id, workspace_id=workspace_id, name="Music"
    )
    run_id = new_run_id()
    repo.put_evaluation_ref(
        DatasetEvaluationRef(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset.dataset_id,
            upload_id="upl_music0000000000000",
            run_id=run_id,
            entitlement_snapshot_id=tenant.current_entitlement_snapshot_id or "ent_test",
            status=EvaluationStatus.ACCEPTED,
            package_uri="gs://example/package",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    resolver = InMemoryModelReadyEvidenceResolver()
    resolver.put(
        ModelReadyEvidence(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset.dataset_id,
            run_id=run_id,
            fingerprint="fp_music",
        )
    )
    client.app.state.model_ready_resolver = resolver
    home = client.get(f"/v1/projects/{workspace_id}/home", headers=auth_header())
    assert home.status_code == 200
    body = home.json()
    assert set(body) == HOME_SEAMS
    assert body["generated_at"]
    assert body["project"]["name"] == "Music Center"
    assert body["project"]["scope_type"] == "BRAND"
    assert body["project"]["brand_name"] == "Music Center"
    assert body["project"]["primary_market"] == "US"
    assert body["project"]["markets"] == ["US"]
    assert body["business_iq_summary"]["readiness"] == "BUSINESS_CONTEXT_READY"
    assert body["business_iq_summary"]["profile_snapshot_id"] == snapshot_id
    assert body["business_iq_summary"]["profile_version"] == 1
    assert body["business_iq_summary"]["channel_count"] == 2
    assert body["business_iq_summary"]["market_count"] == 1
    assert body["data_foundation_summary"]["readiness"] == "DATA_FOUNDATION_READY"
    assert body["data_foundation_summary"]["required_source_count"] == 2
    assert body["data_foundation_summary"]["healthy_source_count"] == 1
    assert body["data_foundation_summary"]["review_source_count"] == 0
    assert body["data_foundation_summary"]["blocked_source_count"] == 0
    assert body["data_foundation_summary"]["shared_continuous_window"] == "2023-07/2026-06"
    assert body["data_foundation_summary"]["most_limiting_source"] == "req_media_music"
    tracks = {item["track_type"]: item for item in body["measurement_tracks"]}
    assert tracks["MMM"]["domain_state"] == "MODEL_READY"
    assert tracks["MMM"]["engine"] == "Google Meridian"
    assert tracks["MTA"]["availability"] == "AVAILABLE_TO_CONFIGURE"
    assert tracks["FORECAST"]["availability"] == "AVAILABLE_TO_CONFIGURE"
    planning = {item["capability"]: item["availability"] for item in body["planning_capabilities"]}
    assert planning["SCENARIO_SIMULATION"] == "REQUIRES_SUPPORTED_BASELINE"
    assert planning["BUDGET_OPTIMIZATION"] == "REQUIRES_ACCEPTED_MMM_MODEL"
    assert body["current_cycle"]["name"] == "Q3 2026"
    assert body["selected_cycle"]["cycle_id"] == body["current_cycle"]["cycle_id"]
    assert body["is_current_cycle"] is True
    home_binding = body["measurement_home"]
    assert home_binding["project_id"] == workspace_id
    assert home_binding["gcp_project_id"] == "acme-analytics"
    assert home_binding["bigquery_dataset_id"] == "prem3_modeling"
    assert home_binding["drive_root_folder_id"] == "fld_root_music"
    assert home_binding["binding_status"] == "ACTIVE"
    assert home_binding["namespace_conflict"] is False
    dedicated = client.get(
        f"/v1/projects/{workspace_id}/measurement-home",
        headers=auth_header(),
    )
    assert dedicated.status_code == 200
    assert dedicated.json()["bigquery_dataset_id"] == "prem3_modeling"
    intelligence = body["intelligence_summary"]
    assert intelligence["items"] == []
    assert intelligence["opportunity_count"] == 0
    assert intelligence["risk_count"] == 0
    assert intelligence["decision_required_count"] == 0
    assert intelligence["generated_at"]
    assert body["generated_at"]
    biq_overview = client.get(
        f"/v1/projects/{workspace_id}/business-iq/overview",
        headers=auth_header(),
    )
    assert biq_overview.status_code == 200
    biq_body = biq_overview.json()
    assert biq_body["readiness"] == "BUSINESS_CONTEXT_READY"
    assert biq_body["profile_summary"]["brand_name"] == "Music Center"
    assert biq_body["profile_summary"]["brand_name"] == body["project"]["brand_name"]
    assert biq_body["profile_summary"]["version"] == 1
    assert biq_body["summary_counts"]["channels"] == 2
    assert biq_body["generated_at"]
    df_overview = client.get(
        f"/v1/projects/{workspace_id}/data-foundation/overview",
        headers=auth_header(),
    )
    assert df_overview.status_code == 200
    df_body = df_overview.json()
    assert df_body["readiness"] == "DATA_FOUNDATION_READY"
    assert df_body["source_summary"]["required"] == 2
    assert df_body["source_summary"]["healthy"] == 1
    assert df_body["coverage_summary"]["shared_continuous_window"] == "2023-07/2026-06"
    assert df_body["generated_at"]
    attention = {item["title"]: item for item in body["attention_items"]}
    assert "MTA key event not selected" in attention
    assert attention["MTA key event not selected"]["severity"] == "INFO"
    assert attention["MTA key event not selected"]["owning_capability"] == "MTA"
    event_types = {item["event_type"] for item in body["recent_changes"]}
    assert "PROJECT_UPDATED" in event_types
    assert "MEASUREMENT_CYCLE" in event_types
    assert "EVALUATION" in event_types
    assert all(item.get("resource_ref") for item in body["recent_changes"])


def test_project_home_foundation_in_progress() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Needs work"}).json()
    workspace_id = created["project_id"]
    client.post(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    home = client.get(f"/v1/workspaces/{workspace_id}/home", headers=auth_header()).json()
    assert home["business_iq_summary"]["readiness"] == "BUSINESS_CONTEXT_READY"
    assert home["data_foundation_summary"]["readiness"] in {"NOT_STARTED", "IN_PROGRESS"}
    tracks = {item["track_type"]: item for item in home["measurement_tracks"]}
    assert tracks == {}
    overview = client.get(
        f"/v1/projects/{workspace_id}/data-foundation/overview",
        headers=auth_header(),
    ).json()
    assert overview["readiness"] in {"NOT_STARTED", "IN_PROGRESS"}
    biq = client.get(
        f"/v1/projects/{workspace_id}/business-iq/overview",
        headers=auth_header(),
    ).json()
    assert biq["readiness"] == "BUSINESS_CONTEXT_READY"


def test_historical_cycle_does_not_rewrite_current_health() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Cycles"}).json()
    workspace_id = created["project_id"]
    first = client.post(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    ).json()
    snap_old = first["current_snapshot_id"]
    patched_profile = client.patch(
        f"/v1/workspaces/{workspace_id}/business-iq/profile",
        headers=auth_header(),
        json={"kpi": "Profit"},
    ).json()
    snap_new = patched_profile["current_snapshot_id"]
    assert snap_new != snap_old
    store = client.app.state.data_foundation.store
    older = MeasurementCycle(
        cycle_id="cyc_q2_2026",
        tenant_id=tenant.tenant_id,
        workspace_id=workspace_id,
        name="Q2 2026",
        cadence=CycleCadence.QUARTERLY,
        business_profile_snapshot_id=snap_old,
        created_at=_now(),
        updated_at=datetime(2026, 6, 30, tzinfo=UTC),
        created_by="test",
        state="CLOSED",
    )
    newer = MeasurementCycle(
        cycle_id="cyc_q3_2026",
        tenant_id=tenant.tenant_id,
        workspace_id=workspace_id,
        name="Q3 2026",
        cadence=CycleCadence.QUARTERLY,
        business_profile_snapshot_id=snap_new,
        created_at=_now(),
        updated_at=datetime(2026, 9, 1, tzinfo=UTC),
        created_by="test",
        state="OPEN",
    )
    store.put_cycle(older)
    store.put_cycle(newer)
    _seed_foundation_ready(client, workspace_id, tenant.tenant_id, snapshot_id=snap_new)
    home = client.get(f"/v1/projects/{workspace_id}/home", headers=auth_header()).json()
    assert home["current_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert home["selected_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert home["is_current_cycle"] is True
    assert home["current_cycle"]["business_profile_snapshot_id"] == snap_new
    assert home["data_foundation_summary"]["readiness"] == "DATA_FOUNDATION_READY"
    historical = client.get(
        f"/v1/projects/{workspace_id}/home",
        headers=auth_header(),
        params={"cycle_id": "cyc_q2_2026"},
    )
    assert historical.status_code == 200
    hist = historical.json()
    assert hist["current_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert hist["current_cycle"]["business_profile_snapshot_id"] == snap_new
    assert hist["selected_cycle"]["cycle_id"] == "cyc_q2_2026"
    assert hist["selected_cycle"]["business_profile_snapshot_id"] == snap_old
    assert hist["is_current_cycle"] is False
    assert hist["business_iq_summary"]["profile_snapshot_id"] == snap_old
    assert hist["business_iq_summary"]["profile_version"] == 1
    assert hist["data_foundation_summary"]["readiness"] != "DATA_FOUNDATION_READY"
    assert hist["data_foundation_summary"]["healthy_source_count"] == 0
    hist_tracks = {item["track_type"]: item for item in hist["measurement_tracks"]}
    hist_planning = {
        item["capability"]: item["availability"] for item in hist["planning_capabilities"]
    }
    assert hist_tracks["FORECAST"]["availability"] == "NEEDS_FOUNDATION"
    assert hist_planning["FORECASTING"] == "AVAILABLE_TO_CONFIGURE"
    missing = client.get(
        f"/v1/projects/{workspace_id}/home",
        headers=auth_header(),
        params={"cycle_id": "cyc_missing"},
    )
    assert missing.status_code == 404
    _b, identity_b = seed_tenant(
        repo,
        display_name="B",
        provider_org="org_hist_b",
        provider_user="user_hist_b",
        plan_id=PlanId.PROJECT,
    )
    client_b, _ = make_client(repo=repo, identity=identity_b)
    stolen = client_b.get(
        f"/v1/projects/{workspace_id}/home",
        headers=auth_header(),
        params={"cycle_id": "cyc_q2_2026"},
    )
    assert stolen.status_code == 404
    q2_tracks = client.get(
        f"/v1/projects/{workspace_id}/cycles/cyc_q2_2026/tracks",
        headers=auth_header(),
    ).json()["items"]
    q3_tracks = client.get(
        f"/v1/projects/{workspace_id}/cycles/cyc_q3_2026/tracks",
        headers=auth_header(),
    ).json()["items"]
    assert q2_tracks[0]["cycle_id"] == "cyc_q2_2026"
    assert q3_tracks[0]["cycle_id"] == "cyc_q3_2026"
    assert q2_tracks[0]["track_id"] != q3_tracks[0]["track_id"]
    q2_mta = next(item for item in q2_tracks if item["track_type"] == "MTA")
    q3_mta = next(item for item in q3_tracks if item["track_type"] == "MTA")
    patched = client.patch(
        f"/v1/projects/{workspace_id}/tracks/{q2_mta['track_id']}",
        headers=auth_header(),
        json={"config": {"ga4_dataset_id": "analytics_q2", "key_event_name": "purchase"}},
    )
    assert patched.status_code == 200
    home_after = client.get(f"/v1/projects/{workspace_id}/home", headers=auth_header()).json()
    assert home_after["current_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert home_after["selected_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert home_after["is_current_cycle"] is True
    assert home_after["current_cycle"]["business_profile_snapshot_id"] == snap_new
    hist_after = client.get(
        f"/v1/projects/{workspace_id}/home",
        headers=auth_header(),
        params={"cycle_id": "cyc_q2_2026"},
    ).json()
    assert hist_after["current_cycle"]["cycle_id"] == "cyc_q3_2026"
    assert hist_after["selected_cycle"]["cycle_id"] == "cyc_q2_2026"
    assert hist_after["is_current_cycle"] is False
    assert {item["track_type"] for item in hist_after["measurement_tracks"]} == {
        "MMM",
        "MTA",
        "FORECAST",
    }
    assert hist_after["data_foundation_summary"]["readiness"] != "DATA_FOUNDATION_READY"
    q2_reload = client.get(
        f"/v1/projects/{workspace_id}/cycles/cyc_q2_2026/tracks",
        headers=auth_header(),
    ).json()["items"]
    q3_reload = client.get(
        f"/v1/projects/{workspace_id}/cycles/cyc_q3_2026/tracks",
        headers=auth_header(),
    ).json()["items"]
    q2_mta_reload = next(item for item in q2_reload if item["track_type"] == "MTA")
    q3_mta_reload = next(item for item in q3_reload if item["track_type"] == "MTA")
    assert q2_mta_reload["config"]["ga4_dataset_id"] == "analytics_q2"
    assert q3_mta_reload["config"].get("ga4_dataset_id") in {None, ""}
    assert q2_mta_reload["track_id"] != q3_mta["track_id"]
    assert home_after["data_foundation_summary"]["readiness"] == "DATA_FOUNDATION_READY"


def test_measurement_home_namespace_conflict_is_deterministic() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PORTFOLIO)
    client, _ = make_client(repo=repo, identity=identity)
    first = client.post("/v1/projects", headers=auth_header(), json={"name": "A"}).json()
    second = client.post("/v1/projects", headers=auth_header(), json={"name": "B"}).json()
    _bind_measurement_home(
        repo,
        tenant_id=tenant.tenant_id,
        workspace_id=first["project_id"],
        gcp_project_id="shared-gcp",
    )
    _bind_measurement_home(
        repo,
        tenant_id=tenant.tenant_id,
        workspace_id=second["project_id"],
        gcp_project_id="shared-gcp",
    )
    home_a = client.get(
        f"/v1/projects/{first['project_id']}/measurement-home",
        headers=auth_header(),
    ).json()
    home_b = client.get(
        f"/v1/projects/{second['project_id']}/home",
        headers=auth_header(),
    ).json()
    assert home_a["namespace_conflict"] is True
    assert home_a["binding_status"] == "CONFLICT"
    assert home_b["measurement_home"]["namespace_conflict"] is True
    titles = [item["title"] for item in home_b["attention_items"]]
    assert "Measurement Home namespace conflict" in titles
    archived = client.patch(
        f"/v1/projects/{first['project_id']}",
        headers=auth_header(),
        json={"status": "ARCHIVED"},
    )
    assert archived.status_code == 200
    cleared = client.get(
        f"/v1/projects/{second['project_id']}/measurement-home",
        headers=auth_header(),
    ).json()
    assert cleared["namespace_conflict"] is False
    assert cleared["binding_status"] == "ACTIVE"


def test_archive_capacity_is_atomic_and_idempotent() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Live"}).json()
    workspace_id = created["project_id"]

    def _archive() -> WorkspaceStatus:
        return repo.update_workspace_status(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace_id,
            status=WorkspaceStatus.ARCHIVED,
        ).status

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_archive) for _ in range(8)]
        statuses = [future.result() for future in as_completed(futures)]
    assert set(statuses) == {WorkspaceStatus.ARCHIVED}
    assert repo.get_tenant(tenant.tenant_id).active_workspace_count == 0
    again = client.patch(
        f"/v1/projects/{workspace_id}",
        headers=auth_header(),
        json={"status": "ARCHIVED"},
    )
    assert again.status_code == 200
    assert again.json()["status"] == "ARCHIVED"
    assert repo.get_tenant(tenant.tenant_id).active_workspace_count == 0
    replacement = client.post("/v1/projects", headers=auth_header(), json={"name": "Next"})
    assert replacement.status_code == 201
    assert repo.get_tenant(tenant.tenant_id).active_workspace_count == 1


def test_measurement_track_uniqueness_is_atomic_and_idempotent() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Tracks"}).json()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=created["project_id"]
    )
    first = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id="cyc_q3_2026")
    again = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id="cyc_q3_2026")
    assert [item.track_id for item in first] == [item.track_id for item in again]
    mmm = next(item for item in first if item.track_type is MeasurementTrackType.MMM)
    rewritten = repo.put_measurement_track(
        mmm.model_copy(update={"configuration_version": mmm.configuration_version + 1})
    )
    assert rewritten.track_id == mmm.track_id
    assert rewritten.configuration_version == mmm.configuration_version + 1
    listed = repo.list_measurement_tracks(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        cycle_id="cyc_q3_2026",
    )
    assert len([item for item in listed if item.track_type is MeasurementTrackType.MMM]) == 1

    def _duplicate() -> str:
        try:
            repo.put_measurement_track(
                MeasurementTrack(
                    track_id=new_track_id(),
                    tenant_id=tenant.tenant_id,
                    workspace_id=workspace.workspace_id,
                    cycle_id="cyc_q3_2026",
                    track_type=MeasurementTrackType.MMM,
                    status=MeasurementTrackStatus.NOT_CONFIGURED,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            return "wrote"
        except ProviderMappingConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_duplicate) for _ in range(8)]
        outcomes = [future.result() for future in as_completed(futures)]
    assert outcomes.count("wrote") == 0
    assert outcomes.count("conflict") == 8
    assert (
        len(
            [
                item
                for item in repo.list_measurement_tracks(
                    tenant_id=tenant.tenant_id,
                    workspace_id=workspace.workspace_id,
                    cycle_id="cyc_q3_2026",
                )
                if item.track_type is MeasurementTrackType.MMM
            ]
        )
        == 1
    )


def test_conflicted_measurement_home_cannot_be_used_as_authority() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PORTFOLIO)
    client, _ = make_client(repo=repo, identity=identity)
    first = client.post("/v1/projects", headers=auth_header(), json={"name": "A"}).json()
    second = client.post("/v1/projects", headers=auth_header(), json={"name": "B"}).json()
    _bind_measurement_home(
        repo,
        tenant_id=tenant.tenant_id,
        workspace_id=first["project_id"],
        gcp_project_id="shared-gcp",
    )
    _bind_measurement_home(
        repo,
        tenant_id=tenant.tenant_id,
        workspace_id=second["project_id"],
        gcp_project_id="shared-gcp",
    )
    home = client.get(
        f"/v1/projects/{second['project_id']}/measurement-home",
        headers=auth_header(),
    )
    assert home.status_code == 200
    assert home.json()["binding_status"] == "CONFLICT"
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=second["project_id"]
    )
    with pytest.raises(MeasurementHomeConflictError):
        require_usable_measurement_home(repo, workspace)
    with pytest.raises(APIError) as denied:
        deny_conflicted_measurement_home(repo, workspace)
    assert denied.value.code == "MEASUREMENT_HOME_CONFLICT"
    df = client.get(
        f"/v1/workspaces/{second['project_id']}/data-foundation",
        headers=auth_header(),
    )
    assert df.status_code == 409
    assert df.json()["code"] == "MEASUREMENT_HOME_CONFLICT"


def test_measurement_track_consumed_config_is_versioned() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post("/v1/projects", headers=auth_header(), json={"name": "Tracks"}).json()
    workspace = repo.get_workspace_for_tenant(
        tenant_id=tenant.tenant_id, workspace_id=created["project_id"]
    )
    tracks = ensure_tracks_for_cycle(repo, workspace=workspace, cycle_id="cyc_q3_2026")
    mmm = next(item for item in tracks if item.track_type is MeasurementTrackType.MMM)
    replay = apply_track_mutation(mmm, config=dict(mmm.config))
    assert replay.configuration_version == mmm.configuration_version
    assert replay.config == mmm.config
    meta = apply_track_mutation(
        mmm, metadata={"status": MeasurementTrackStatus.CONFIGURING}
    )
    assert meta.configuration_version == mmm.configuration_version
    run_id = new_run_id()
    consumed = apply_track_mutation(meta, consume_run_id=run_id)
    consumed = repo.put_measurement_track(consumed)
    assert consumed.is_consumed()
    assert consumed.consumed_run_versions[run_id] == consumed.configuration_version
    with pytest.raises(TrackConfigurationImmutableError):
        repo.put_measurement_track(
            consumed.model_copy(update={"config": {"engine": "rewritten"}})
        )
    next_ver = apply_track_mutation(
        consumed, config={"engine": "Google Meridian", "model_window": "2023-2026"}
    )
    stored = repo.put_measurement_track(next_ver)
    assert stored.configuration_version == consumed.configuration_version + 1
    assert stored.config["model_window"] == "2023-2026"
    assert resolve_track_config_for_run(stored, run_id) == consumed.config
    listed = repo.list_measurement_tracks(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        cycle_id="cyc_q3_2026",
    )
    assert len([item for item in listed if item.track_type is MeasurementTrackType.MMM]) == 1
    del client
