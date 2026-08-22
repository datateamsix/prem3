"""M2-12 input materialization: gates, copy, reuse, and dual-gate tests."""

from __future__ import annotations

from app.governance.codes import GovernanceCheckCode
from app.integrations.google.adapters import BigQueryTableInfo, DriveFile
from app.materialization.foundation_compat import (
    FOUNDATION_SOURCE_NOT_READY,
    FOUNDATION_SOURCE_READY,
    FoundationSourceEvidence,
    InMemoryFoundationSourceGate,
)
from app.service.object_store import FakeObjectStore
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.google_support import connect_google, google_harness
from tests.unit.test_prem3_gcs_import_governance import _verified_upload


def _bind_gcs(harness, upload) -> None:
    file_id = upload.files[0].upload_file_id
    put = harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GCS_UPLOAD",
            "upload_id": upload.upload_id,
            "selected_object_ids": [file_id],
            "role_assignments": [
                {"object_id": file_id, "role": "paid_media", "provider": "google_ads"}
            ],
        },
    )
    assert put.status_code == 200, put.text
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-readiness",
        headers=auth_header(),
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "IMPORT_READY"


def _setup_drive(harness):
    connection_id = connect_google(harness, capabilities=["GOOGLE_DRIVE"])
    response = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/drive/setup",
        headers=auth_header(),
        json={"connection_id": connection_id, "import_enabled": True, "export_enabled": True},
    )
    assert response.status_code == 200, response.text
    return connection_id, response.json()


def _setup_bq(harness, *, write_ok: bool = True):
    connection_id = connect_google(harness, capabilities=["BIGQUERY_WRITE"])
    harness["bigquery"].projects = [{"project_id": "cust-proj"}]
    harness["bigquery"].seed_dataset(
        project_id="cust-proj",
        dataset_id="prem3_modeling",
        location="US",
        write_ok=write_ok,
        friendly_name="prem3-modeling",
    )
    setup = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/bigquery/setup",
        headers=auth_header(),
        json={
            "connection_id": connection_id,
            "destination_project_id": "cust-proj",
            "location": "US",
            "create_if_missing": False,
        },
    )
    assert setup.status_code == 200, setup.text
    return connection_id, setup.json()


def test_write_bytes_is_create_only() -> None:
    store = FakeObjectStore()
    store.write_bytes(bucket="b", object_name="a.csv", data=b"one")
    try:
        store.write_bytes(bucket="b", object_name="a.csv", data=b"two")
    except FileExistsError:
        return
    raise AssertionError("write_bytes must not overwrite")


def test_gcs_upload_reuses_verified_upload() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    first = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["result_kind"] == "REUSED_EXISTING_UPLOAD"
    assert body["upload_id"] == upload.upload_id
    assert body["upload_status"] == "VERIFIED"
    assert body["materialization_state"] == "COMPLETE"
    second = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={"idempotency_key": "mat-1"},
    )
    assert second.json()["upload_id"] == body["upload_id"]
    listed = harness["client"].get(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
    )
    assert listed.status_code == 200
    assert listed.json()["items"]


def test_import_not_ready_cannot_materialize() -> None:
    harness = google_harness()
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "IMPORT_NOT_READY"


def test_stale_drive_revision_fails_closed() -> None:
    harness = google_harness()
    connection_id, binding = _setup_drive(harness)
    harness["drive"].seed(
        DriveFile(
            file_id="csv_file_0001",
            name="geo.csv",
            mime_type="text/csv",
            parents=(binding["root_folder_id"],),
            md5="rev-a",
            head_revision_id="rev-a",
            version="1",
            size_bytes=12,
        ),
        payload=b"date,spend\n",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["csv_file_0001"],
            "role_assignments": [
                {"object_id": "csv_file_0001", "role": "paid_media", "provider": "google_ads"}
            ],
        },
    )
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-readiness",
        headers=auth_header(),
    )
    assert ready.json()["status"] == "IMPORT_READY"
    harness["drive"].seed(
        DriveFile(
            file_id="csv_file_0001",
            name="geo.csv",
            mime_type="text/csv",
            parents=(binding["root_folder_id"],),
            md5="rev-b",
            head_revision_id="rev-b",
            version="2",
            size_bytes=12,
        ),
        payload=b"date,spend\n",
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "SOURCE_CHANGED_SINCE_IMPORT_READY"


def test_drive_csv_json_parquet_copy_and_sheets_rejected() -> None:
    harness = google_harness()
    connection_id, binding = _setup_drive(harness)
    root = binding["root_folder_id"]
    sources = harness["drive"].create_folder(
        access_token="t", name="sources", parent_id=root
    )
    harness["drive"].seed(
        DriveFile(
            file_id="csv_file_ready",
            name="ads.csv",
            mime_type="text/csv",
            parents=(sources.file_id,),
            md5="c1",
            head_revision_id="c1",
            version="1",
            size_bytes=11,
        ),
        payload=b"date,spend\n",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["csv_file_ready"],
            "role_assignments": [
                {"object_id": "csv_file_ready", "role": "paid_media", "provider": "meta"}
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
    copied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    body = copied.json()
    assert body["result_kind"] == "CREATED_NEW_UPLOAD"
    assert body["upload_status"] == "VERIFIED"
    assert body["upload_id"]
    assert "package_uri" not in body
    assert body["source_objects"][0]["source_identity"] == "csv_file_ready"
    evaluation = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": body["upload_id"]},
    )
    assert evaluation.status_code == 202, evaluation.text
    assert evaluation.json()["upload_id"] == body["upload_id"]

    harness["drive"].seed(
        DriveFile(
            file_id="sheet_file_0001",
            name="budget.gsheet",
            mime_type="application/vnd.google-apps.spreadsheet",
            parents=(root,),
            md5="s1",
            head_revision_id="s1",
            version="1",
            size_bytes=12,
        )
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["sheet_file_0001"],
            "role_assignments": [
                {"object_id": "sheet_file_0001", "role": "controls", "provider": "sheets"}
            ],
        },
    )
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-readiness",
        headers=auth_header(),
    ).json()
    assert ready["status"] == "NOT_IMPORT_READY"


def test_partial_logical_series_fails() -> None:
    harness = google_harness()
    connection_id, binding = _setup_drive(harness)
    root = binding["root_folder_id"]
    harness["drive"].seed(
        DriveFile(
            file_id="meta_jan",
            name="meta_jan.csv",
            mime_type="text/csv",
            parents=(root,),
            md5="j1",
            head_revision_id="j1",
            version="1",
            size_bytes=8,
        ),
        payload=b"jan,1\n",
    )
    harness["drive"].seed(
        DriveFile(
            file_id="meta_feb",
            name="meta_feb.csv",
            mime_type="text/csv",
            parents=(root,),
            md5="f1",
            head_revision_id="f1",
            version="1",
            size_bytes=8,
        ),
        payload=b"",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["meta_jan", "meta_feb"],
            "role_assignments": [
                {"object_id": "meta_jan", "role": "paid_media", "provider": "meta"},
                {"object_id": "meta_feb", "role": "paid_media", "provider": "meta"},
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
    assert denied.json()["code"] == "SOURCE_COPY_INCOMPLETE"


def test_file_outside_root_rejected() -> None:
    harness = google_harness()
    connection_id, _binding = _setup_drive(harness)
    harness["drive"].seed(
        DriveFile(
            file_id="outside_csv",
            name="leak.csv",
            mime_type="text/csv",
            parents=("foreign_root",),
            md5="x1",
            head_revision_id="x1",
            version="1",
            size_bytes=8,
        ),
        payload=b"leak,1\n",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["outside_csv"],
            "role_assignments": [
                {"object_id": "outside_csv", "role": "paid_media", "provider": "meta"}
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
    assert denied.json()["code"] == "SOURCE_MATERIALIZATION_FAILED"


def test_bigquery_materializes_nulls_without_sql() -> None:
    harness = google_harness()
    connection_id, _binding = _setup_bq(harness)
    harness["bigquery"].tables["cust-proj.analytics.google_ads"] = BigQueryTableInfo(
        project_id="cust-proj",
        dataset_id="analytics",
        table_id="google_ads",
        object_type="TABLE",
        schema_fingerprint="schema-ads",
        etag="etag-1",
        last_modified="2026-01-01",
        num_bytes=40,
        num_rows=2,
        location="US",
    )
    harness["bigquery"].seed_table_rows(
        project_id="cust-proj",
        dataset_id="analytics",
        table_id="google_ads",
        columns=["date", "spend"],
        rows=[{"date": "2024-01-01", "spend": 10}, {"date": "2024-01-08", "spend": None}],
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "BIGQUERY",
            "connection_id": connection_id,
            "selected_object_ids": ["cust-proj.analytics.google_ads"],
            "role_assignments": [
                {
                    "object_id": "cust-proj.analytics.google_ads",
                    "role": "paid_media",
                    "provider": "google_ads",
                }
            ],
        },
    )
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-readiness",
        headers=auth_header(),
    )
    assert ready.json()["status"] == "IMPORT_READY", ready.text
    copied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    upload = harness["repo"].get_upload(
        tenant_id=harness["tenant"].tenant_id,
        workspace_id=harness["workspace"]["workspace_id"],
        dataset_id=harness["dataset"]["dataset_id"],
        upload_id=copied.json()["upload_id"],
    )
    assert upload is not None
    raw = harness["store"].objects[("prem3-test-raw", upload.files[0].object_name)]["data"]
    assert b"null" in raw
    assert b"SELECT" not in raw


def test_df_dual_gate_and_premodel_review_survives() -> None:
    gate = InMemoryFoundationSourceGate()
    harness = google_harness(foundation_source_gate=gate)
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    binding_id = upload.upload_id
    gate.put(
        FoundationSourceEvidence(
            source_binding_id=binding_id,
            source_foundation_receipt_id="rcpt_foundation00000001",
            status_code=FOUNDATION_SOURCE_NOT_READY,
            governance_import_ready=True,
            tenant_id=harness["tenant"].tenant_id,
            workspace_id=harness["workspace"]["workspace_id"],
        )
    )
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "FOUNDATION_SOURCE_NOT_READY"
    gate.put(
        FoundationSourceEvidence(
            source_binding_id=binding_id,
            source_foundation_receipt_id="rcpt_foundation00000002",
            status_code=FOUNDATION_SOURCE_READY,
            governance_import_ready=True,
            premodel_review_remaining=True,
            premodel_review_findings=["six-week ambiguous interval remains UNKNOWN"],
            tenant_id=harness["tenant"].tenant_id,
            workspace_id=harness["workspace"]["workspace_id"],
            provider="meta",
            business_role="paid_social",
            history="43 months",
            refresh_cadence="Daily · T+1",
            grain="Day × campaign",
            geography="DMA",
            metrics=["spend", "impressions"],
        )
    )
    ok = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["premodel_review_remaining"] is True
    assert "UNKNOWN" in body["premodel_review_findings"][0]
    assert body["foundation_source_state"] == FOUNDATION_SOURCE_READY
    assert body["import_governance_state"] == "IMPORT_READY"


def test_superseded_receipt_cannot_materialize() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    current = harness["repo"].get_current_import_receipt(
        tenant_id=harness["tenant"].tenant_id,
        workspace_id=harness["workspace"]["workspace_id"],
        dataset_id=harness["dataset"]["dataset_id"],
    )
    assert current is not None
    harness["repo"].put_import_receipt(current.model_copy(update={"superseded": True}))
    denied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "IMPORT_RECEIPT_SUPERSEDED"


def test_json_and_parquet_drive_copy() -> None:
    harness = google_harness()
    connection_id, binding = _setup_drive(harness)
    root = binding["root_folder_id"]
    harness["drive"].seed(
        DriveFile(
            file_id="json_file_ready",
            name="kpi.json",
            mime_type="application/json",
            parents=(root,),
            md5="j1",
            head_revision_id="j1",
            version="1",
            size_bytes=2,
        ),
        payload=b"{}",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["json_file_ready"],
            "role_assignments": [
                {"object_id": "json_file_ready", "role": "kpi", "provider": "internal"}
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
    copied = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert copied.status_code == 200, copied.text
    harness["drive"].seed(
        DriveFile(
            file_id="parq_file_ready",
            name="media.parquet",
            mime_type="application/vnd.apache.parquet",
            parents=(root,),
            md5="p1",
            head_revision_id="p1",
            version="1",
            size_bytes=4,
        ),
        payload=b"PAR1",
    )
    harness["client"].put(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/import-binding",
        headers=auth_header(),
        json={
            "source_type": "GOOGLE_DRIVE",
            "connection_id": connection_id,
            "selected_object_ids": ["parq_file_ready"],
            "role_assignments": [
                {"object_id": "parq_file_ready", "role": "paid_media", "provider": "dv360"}
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
    parquet = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert parquet.status_code == 200, parquet.text


def test_cross_tenant_materialization_is_not_found() -> None:
    harness = google_harness()
    upload = _verified_upload(harness)
    _bind_gcs(harness, upload)
    _other_tenant, other_identity = seed_tenant(
        harness["repo"],
        provider_org="org_other_mat",
        provider_user="user_other_mat",
    )
    foreign, _ = make_client(repo=harness["repo"], identity=other_identity)
    denied = foreign.post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/materializations",
        headers=auth_header(),
        json={},
    )
    assert denied.status_code == 404
    assert "ya29" not in denied.text


def test_readiness_states_are_not_inferred() -> None:
    assert GovernanceCheckCode.IMPORT_NOT_READY.value != "FOUNDATION_SOURCE_READY"
    assert FOUNDATION_SOURCE_READY != "IMPORT_READY"
    assert FOUNDATION_SOURCE_READY != "DATA_FOUNDATION_READY"
    assert "MODEL_READY" != "PUBLISH_READY"
    assert "PUBLISH_READY" != "PUBLISHED"
