"""Canonical Data Foundation dual-gate, tenancy, lineage, and namespace tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.contracts import (
    EvidenceRequirement,
    EvidenceRequirementSet,
    ResourceIdentity,
    SourceBinding,
    SourceContract,
    SourceFoundationReceipt,
)
from app.data_foundation.enums import EvidenceRequirementType, LocationType, SourceFoundationStatus
from app.data_foundation.store import InMemoryDataFoundationStore
from app.integrations.google.adapters import BigQueryTableInfo
from app.materialization.canonical_gate import CanonicalFoundationSourceGate
from app.materialization.foundation_compat import (
    FOUNDATION_SOURCE_NOT_READY,
    FOUNDATION_SOURCE_READY,
    FoundationSourceAuthorityDenied,
    NullFoundationSourceGate,
)
from app.publish_execution.namespace import is_reserved_bigquery_table
from app.service.app import create_app
from tests.unit.api_support import auth_header, seed_tenant
from tests.unit.google_support import google_harness
from tests.unit.test_m2_12_materialization import _bind_gcs, _setup_bq
from tests.unit.test_prem3_gcs_import_governance import _verified_upload


def _now() -> datetime:
    return datetime.now(UTC)


def _store(harness) -> InMemoryDataFoundationStore:
    return harness["client"].app.state.data_foundation_store


def _binding(
    *,
    source_id: str,
    tenant_id: str,
    workspace_id: str,
    requirement_id: str | None = None,
    drive_file_id: str | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    table_id: str | None = None,
    logical_path: str | None = None,
    location_type: LocationType = LocationType.GOOGLE_DRIVE,
) -> SourceBinding:
    return SourceBinding(
        source_id=source_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requirement_id=requirement_id,
        provider_id="google_ads",
        location_type=location_type,
        resource=ResourceIdentity(
            location_type=location_type,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            drive_file_id=drive_file_id,
            logical_path=logical_path,
        ),
        contract=SourceContract(grain="daily"),
        lifecycle_state="BOUND",
        created_at=_now(),
        updated_at=_now(),
    )


def _receipt(
    *,
    source_id: str,
    tenant_id: str,
    workspace_id: str,
    status: SourceFoundationStatus = SourceFoundationStatus.FOUNDATION_SOURCE_READY,
    governance_import_ready: bool = True,
    receipt_id: str = "dfrct_ready000000000001",
    extra_source_ids: tuple[str, ...] = (),
    premodel_review_remaining: bool = False,
    premodel_review_findings: tuple[str, ...] = (),
) -> SourceFoundationReceipt:
    return SourceFoundationReceipt(
        receipt_id=receipt_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        source_ids=(source_id, *extra_source_ids),
        executed_at=_now(),
        executed_by="tester",
        status=status.value,
        status_code=status,
        governance_import_ready=governance_import_ready,
        premodel_review_remaining=premodel_review_remaining,
        premodel_review_findings=premodel_review_findings,
    )


def _requirements(
    *,
    tenant_id: str,
    workspace_id: str,
    requirement_id: str,
    business_role: str,
) -> EvidenceRequirementSet:
    return EvidenceRequirementSet(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        snapshot_id="bps_acme00000000000001",
        snapshot_fingerprint="a" * 64,
        compiled_at=_now(),
        requirements=(
            EvidenceRequirement(
                requirement_id=requirement_id,
                requirement_type=EvidenceRequirementType.MEDIA,
                concept="paid media",
                business_role=business_role,
                expected_category="media",
            ),
        ),
    )


def test_canonical_df_store_is_runtime_source() -> None:
    harness = google_harness()
    app = harness["client"].app
    assert app.state.data_foundation_store is app.state.data_foundation.store
    assert isinstance(app.state.materialization._foundation, CanonicalFoundationSourceGate)
    assert app.state.materialization._foundation._store is app.state.data_foundation_store


def test_null_foundation_gate_not_production_default() -> None:
    harness = google_harness()
    gate = harness["client"].app.state.materialization._foundation
    assert not isinstance(gate, NullFoundationSourceGate)
    repo = harness["repo"]
    tenant, identity = seed_tenant(repo, provider_org="org_default_gate")
    del tenant, identity
    app = create_app(control_plane_repository=repo)
    assert isinstance(app.state.materialization._foundation, CanonicalFoundationSourceGate)


def test_direct_non_df_import_still_supported() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    copied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["foundation_source_state"] is None


def test_df_binding_tenant_mismatch_denied() -> None:
    store = InMemoryDataFoundationStore()
    store.put_binding(
        _binding(
            source_id="dfsrc_foreign0000000001",
            tenant_id="foreign-tenant",
            workspace_id="wsp_test00000000000001",
        )
    )
    gate = CanonicalFoundationSourceGate(store)
    try:
        gate.get_source_materialization_evidence(
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_binding_id="dfsrc_foreign0000000001",
        )
    except FoundationSourceAuthorityDenied:
        return
    raise AssertionError("foreign binding must be denied")


def test_df_binding_workspace_mismatch_denied() -> None:
    store = InMemoryDataFoundationStore()
    store.put_binding(
        _binding(
            source_id="dfsrc_ws000000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_other000000000001",
        )
    )
    gate = CanonicalFoundationSourceGate(store)
    try:
        gate.get_source_materialization_evidence(
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_binding_id="dfsrc_ws000000000000001",
        )
    except FoundationSourceAuthorityDenied:
        return
    raise AssertionError("workspace mismatch must be denied")


def test_df_receipt_tenant_mismatch_denied() -> None:
    store = InMemoryDataFoundationStore()
    store.put_binding(
        _binding(
            source_id="dfsrc_rct00000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
        )
    )
    store.put_source_receipt(
        _receipt(
            source_id="dfsrc_rct00000000000001",
            tenant_id="foreign-tenant",
            workspace_id="wsp_test00000000000001",
        )
    )
    gate = CanonicalFoundationSourceGate(store)
    try:
        gate.get_source_materialization_evidence(
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_binding_id="dfsrc_rct00000000000001",
        )
    except FoundationSourceAuthorityDenied:
        return
    raise AssertionError("foreign receipt must be denied")


def test_df_receipt_workspace_mismatch_denied() -> None:
    store = InMemoryDataFoundationStore()
    store.put_binding(
        _binding(
            source_id="dfsrc_rws00000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
        )
    )
    store.put_source_receipt(
        _receipt(
            source_id="dfsrc_rws00000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_other000000000001",
        )
    )
    gate = CanonicalFoundationSourceGate(store)
    try:
        gate.get_source_materialization_evidence(
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_binding_id="dfsrc_rws00000000000001",
        )
    except FoundationSourceAuthorityDenied:
        return
    raise AssertionError("receipt workspace mismatch must be denied")


def test_df_receipt_source_ids_must_include_binding() -> None:
    store = InMemoryDataFoundationStore()
    store.put_binding(
        _binding(
            source_id="dfsrc_sid00000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
        )
    )
    store.put_source_receipt(
        SourceFoundationReceipt(
            receipt_id="dfrct_other000000000001",
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_ids=("dfsrc_unrelated00000001",),
            executed_at=_now(),
            executed_by="tester",
            status=SourceFoundationStatus.FOUNDATION_SOURCE_READY.value,
            status_code=SourceFoundationStatus.FOUNDATION_SOURCE_READY,
            governance_import_ready=True,
            premodel_review_remaining=False,
        )
    )
    store.source_receipts["dfsrc_sid00000000000001"] = store.source_receipts[
        "dfsrc_unrelated00000001"
    ]
    gate = CanonicalFoundationSourceGate(store)
    try:
        gate.get_source_materialization_evidence(
            tenant_id="tenant-local",
            workspace_id="wsp_test00000000000001",
            source_binding_id="dfsrc_sid00000000000001",
        )
    except FoundationSourceAuthorityDenied:
        return
    raise AssertionError("receipt source_ids must include the binding")


def test_df_requirement_resolved_with_tenant_workspace_scope() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_requirements(
        _requirements(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            requirement_id="req_media000000000001",
            business_role="paid_media",
        )
    )
    store.put_requirements(
        _requirements(
            tenant_id="foreign-tenant",
            workspace_id=workspace_id,
            requirement_id="req_media000000000001",
            business_role="kpi",
        )
    )
    store.put_binding(
        _binding(
            source_id=upload.upload_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            requirement_id="req_media000000000001",
            logical_path=upload.files[0].upload_file_id,
            location_type=LocationType.GOOGLE_DRIVE,
        )
    )
    store.put_source_receipt(
        _receipt(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    copied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    stored = harness["repo"].get_materialization(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        dataset_id=harness["dataset"]["dataset_id"],
        materialization_id=copied.json()["materialization_id"],
    )
    assert stored is not None
    assert stored.evidence_requirement_ids == ["req_media000000000001"]
    assert stored.business_profile_snapshot_id == "bps_acme00000000000001"
    assert stored.business_profile_snapshot_fingerprint == "a" * 64
    assert stored.business_role == "paid_media"


def test_df_requirement_business_role_lineage_matches_import_contract() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_requirements(
        _requirements(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            requirement_id="req_kpi00000000000001",
            business_role="kpi",
        )
    )
    store.put_binding(
        _binding(
            source_id=upload.upload_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            requirement_id="req_kpi00000000000001",
        )
    )
    store.put_source_receipt(
        _receipt(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "FOUNDATION_LINEAGE_MISMATCH"


def test_df_import_requires_import_ready() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "IMPORT_NOT_READY"


def test_df_import_requires_foundation_source_ready() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(
            source_id=upload.upload_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            status=SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY,
            governance_import_ready=False,
        )
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "FOUNDATION_SOURCE_NOT_READY"


def test_foundation_source_ready_does_not_imply_import_ready() -> None:
    assert FOUNDATION_SOURCE_READY != "IMPORT_READY"
    harness = google_harness()
    upload = _verified_upload(harness)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.json()["code"] == "IMPORT_NOT_READY"


def test_import_ready_does_not_imply_foundation_source_ready() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    evidence = CanonicalFoundationSourceGate(store).get_source_materialization_evidence(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        source_binding_id=upload.upload_id,
    )
    assert evidence is not None
    assert evidence.status_code == FOUNDATION_SOURCE_NOT_READY
    denied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.json()["code"] == "FOUNDATION_SOURCE_NOT_READY"


def test_data_foundation_ready_not_required_per_source() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    assert store.get_current_foundation_receipt(
        tenant_id=tenant_id, workspace_id=workspace_id
    ) is None
    copied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["foundation_source_state"] == FOUNDATION_SOURCE_READY


def test_premodel_review_preserved() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(
            source_id=upload.upload_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            premodel_review_remaining=True,
            premodel_review_findings=("six-week ambiguous interval remains UNKNOWN",),
        )
    )
    copied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["premodel_review_remaining"] is True
    assert "UNKNOWN" in copied.json()["premodel_review_findings"][0]


def test_unknown_remains_unknown() -> None:
    finding = "coverage for November is UNKNOWN, not zero"
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    tenant_id = harness["tenant"].tenant_id
    workspace_id = harness["workspace"]["workspace_id"]
    store.put_binding(
        _binding(source_id=upload.upload_id, tenant_id=tenant_id, workspace_id=workspace_id)
    )
    store.put_source_receipt(
        _receipt(
            source_id=upload.upload_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            premodel_review_remaining=True,
            premodel_review_findings=(finding,),
        )
    )
    copied = harness["client"].post(
        f"/v1/workspaces/{workspace_id}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.json()["premodel_review_findings"] == [finding]
    assert "UNKNOWN" in copied.json()["premodel_review_findings"][0]
    assert copied.json()["premodel_review_findings"][0] != "false"


def test_cross_tenant_binding_lookup_is_not_found() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    store = _store(harness)
    store.put_binding(
        _binding(
            source_id=upload.upload_id,
            tenant_id="foreign-tenant",
            workspace_id=harness["workspace"]["workspace_id"],
        )
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "RESOURCE_NOT_FOUND"


def test_publish_cannot_target_stg_namespace() -> None:
    assert is_reserved_bigquery_table("stg_drive_imports")
    assert is_reserved_bigquery_table("stg_dfsrc_abc")


def test_publish_cannot_target_canonical_namespace() -> None:
    assert is_reserved_bigquery_table("canonical_kpi")
    assert is_reserved_bigquery_table("canonical_media")
    assert is_reserved_bigquery_table("canonical_treatments")
    assert is_reserved_bigquery_table("canonical_controls")


def test_publish_cannot_target_source_registry() -> None:
    assert is_reserved_bigquery_table("source_registry")


def test_publish_cannot_target_source_health() -> None:
    assert is_reserved_bigquery_table("source_health")


def test_publish_cannot_target_model_input_mmm() -> None:
    assert is_reserved_bigquery_table("model_input_mmm")


def test_publish_can_target_model_ready_versioned_namespace() -> None:
    assert not is_reserved_bigquery_table("model_ready_dsetA_run1")
    assert not is_reserved_bigquery_table("model_ready_dsetA_current")


def test_publish_current_pointer_only_targets_verified_versioned_table() -> None:
    from app.governance.publish_evaluator import (
        customer_model_ready_current_view_id,
        customer_model_ready_table_id,
    )

    table_id = customer_model_ready_table_id("dset_a", "run_a")
    view_id = customer_model_ready_current_view_id("dset_a")
    assert table_id.startswith("model_ready_")
    assert view_id.endswith("_current")
    assert not is_reserved_bigquery_table(table_id)
    assert not is_reserved_bigquery_table(view_id)
    assert is_reserved_bigquery_table("model_input_mmm")


def test_bigquery_over_limit_fails_closed() -> None:
    harness = google_harness()
    connection_id, _binding = _setup_bq(harness)
    harness["bigquery"].tables["cust-proj.analytics.huge"] = BigQueryTableInfo(
        project_id="cust-proj",
        dataset_id="analytics",
        table_id="huge",
        object_type="TABLE",
        schema_fingerprint="schema-huge",
        etag="etag-huge",
        last_modified="2026-01-01",
        num_bytes=9_000_000,
        num_rows=100_001,
        location="US",
    )
    harness["bigquery"].seed_table_rows(
        project_id="cust-proj",
        dataset_id="analytics",
        table_id="huge",
        columns=["date"],
        rows=[{"date": "2024-01-01"}],
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "BIGQUERY",
            "connection_id": connection_id,
            "selected_object_ids": ["cust-proj.analytics.huge"],
            "role_assignments": [
                {
                    "object_id": "cust-proj.analytics.huge",
                    "role": "paid_media",
                    "provider": "google_ads",
                }
            ],
        },
    )
    assert (
        harness["client"]
        .post(
            f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
            f"{harness['dataset']['dataset_id']}/import-readiness",
            headers=auth_header(),
        )
        .json()["status"]
        == "IMPORT_READY"
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "MATERIALIZATION_LIMIT_EXCEEDED"
    listed = harness["client"].get(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert all(item.get("upload_status") != "VERIFIED" for item in listed.json()["items"])
