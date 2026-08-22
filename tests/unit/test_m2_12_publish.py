"""M2-12 customer publish: MODEL_READY resolver, destinations, namespace guard."""

from __future__ import annotations

from app.governance.codes import PUBLISH_DRIVE_ARTIFACTS
from app.governance.publish_evaluator import (
    customer_model_ready_current_view_id,
    customer_model_ready_table_id,
)
from app.publish_execution.contracts import ModelReadyEvidence
from app.publish_execution.model_ready import InMemoryModelReadyEvidenceResolver
from app.publish_execution.namespace import is_reserved_bigquery_table
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.google_support import connect_google, google_harness
from tests.unit.test_prem3_gcs_import_governance import _verified_upload


def _artifacts() -> dict[str, bytes]:
    return {name: f"{name}-bytes".encode("utf-8") for name in PUBLISH_DRIVE_ARTIFACTS}


def _create_evaluation(harness):
    upload = _verified_upload(harness)
    created = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload.upload_id},
    )
    assert created.status_code == 202, created.text
    return created.json()["run_id"], upload


def _bind_destinations(harness):
    connection_id = connect_google(
        harness, capabilities=["GOOGLE_DRIVE", "BIGQUERY_WRITE"]
    )
    drive = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/drive/setup",
        headers=auth_header(),
        json={"connection_id": connection_id, "import_enabled": True, "export_enabled": True},
    )
    assert drive.status_code == 200, drive.text
    harness["bigquery"].projects = [{"project_id": "cust-proj"}]
    harness["bigquery"].seed_dataset(
        project_id="cust-proj",
        dataset_id="prem3_modeling",
        location="US",
        write_ok=True,
        friendly_name="prem3-modeling",
    )
    bq = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/bigquery/setup",
        headers=auth_header(),
        json={
            "connection_id": connection_id,
            "destination_project_id": "cust-proj",
            "location": "US",
            "create_if_missing": False,
        },
    )
    assert bq.status_code == 200, bq.text
    assert bq.json()["write_verified"] is True
    return connection_id


def test_reserved_namespace_is_rejected() -> None:
    assert is_reserved_bigquery_table("canonical_kpi")
    assert is_reserved_bigquery_table("stg_media")
    assert is_reserved_bigquery_table("source_registry")
    assert is_reserved_bigquery_table("source_health")
    assert is_reserved_bigquery_table("model_input_mmm")
    assert not is_reserved_bigquery_table("model_ready_dset_run")


def test_evaluation_accepted_is_not_publish_ready() -> None:
    harness = google_harness()
    run_id, _upload = _create_evaluation(harness)
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publish-readiness",
        headers=auth_header(),
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "NOT_PUBLISH_READY"
    assert ready.json()["published"] is False
    publish = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes",
        headers=auth_header(),
    )
    assert publish.status_code == 409
    assert publish.json()["code"] == "PUBLISH_NOT_READY"


def test_model_ready_plus_destinations_publishes_and_is_idempotent() -> None:
    resolver = InMemoryModelReadyEvidenceResolver()
    harness = google_harness(model_ready_resolver=resolver)
    run_id, _upload = _create_evaluation(harness)
    _bind_destinations(harness)
    evidence = ModelReadyEvidence(
        tenant_id=harness["tenant"].tenant_id,
        workspace_id=harness["workspace"]["workspace_id"],
        dataset_id=harness["dataset"]["dataset_id"],
        run_id=run_id,
        fingerprint="fp-model-ready-1",
        artifacts=_artifacts(),
        schema_fingerprint="schema-mr",
        row_count=6,
    )
    resolver.put(evidence)
    ready = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publish-readiness",
        headers=auth_header(),
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "PUBLISH_READY"
    assert ready.json()["model_ready_fingerprint"] == "fp-model-ready-1"
    first = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes",
        headers=auth_header(),
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "COMPLETE"
    kinds = {item["kind"]: item for item in body["destination_results"]}
    assert kinds["GOOGLE_DRIVE"]["readback_verified"] is True
    assert kinds["BIGQUERY"]["readback_verified"] is True
    assert kinds["BIGQUERY"]["stable_pointer_identity"] == customer_model_ready_current_view_id(
        harness["dataset"]["dataset_id"]
    )
    assert kinds["BIGQUERY"]["versioned_resource_identity"] == customer_model_ready_table_id(
        harness["dataset"]["dataset_id"], run_id
    )
    assert "imports" not in kinds["GOOGLE_DRIVE"]["target_presentation_identity"]
    assert "sources" not in kinds["GOOGLE_DRIVE"]["target_presentation_identity"]
    second = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes",
        headers=auth_header(),
    )
    assert second.json()["publish_id"] == body["publish_id"]
    fetched = harness["client"].get(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes/{body['publish_id']}",
        headers=auth_header(),
    )
    assert fetched.status_code == 200
    assert "ya29" not in fetched.text
    assert "refresh_token" not in fetched.text


def test_partial_publish_when_drive_fails() -> None:
    resolver = InMemoryModelReadyEvidenceResolver()
    harness = google_harness(model_ready_resolver=resolver)
    run_id, _upload = _create_evaluation(harness)
    _bind_destinations(harness)
    resolver.put(
        ModelReadyEvidence(
            tenant_id=harness["tenant"].tenant_id,
            workspace_id=harness["workspace"]["workspace_id"],
            dataset_id=harness["dataset"]["dataset_id"],
            run_id=run_id,
            fingerprint="fp-partial",
            artifacts=_artifacts(),
        )
    )
    binding = harness["repo"].get_drive_binding(
        tenant_id=harness["tenant"].tenant_id,
        workspace_id=harness["workspace"]["workspace_id"],
    )
    assert binding is not None
    harness["drive"].trash(binding.exports_folder_id)
    published = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes",
        headers=auth_header(),
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "PARTIAL"
    kinds = {item["kind"]: item for item in body["destination_results"]}
    assert kinds["BIGQUERY"]["status"] in {"VERIFIED", "VERIFIED_EXISTING"}
    assert kinds["GOOGLE_DRIVE"]["status"] == "FAILED"
    table_id = customer_model_ready_table_id(harness["dataset"]["dataset_id"], run_id)
    assert (
        f"cust-proj.prem3_modeling.{table_id}"
        in harness["bigquery"].published_tables
        or any(table_id in key for key in harness["bigquery"].published_tables)
    )


def test_cross_tenant_publish_denied() -> None:
    resolver = InMemoryModelReadyEvidenceResolver()
    harness = google_harness(model_ready_resolver=resolver)
    run_id, _upload = _create_evaluation(harness)
    _other, other_identity = seed_tenant(
        harness["repo"],
        provider_org="org_pub_other",
        provider_user="user_pub_other",
    )
    foreign, _ = make_client(repo=harness["repo"], identity=other_identity)
    denied = foreign.post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/datasets/"
        f"{harness['dataset']['dataset_id']}/evaluations/{run_id}/publishes",
        headers=auth_header(),
    )
    assert denied.status_code == 404


def test_bq_namespace_collision_rejected_by_adapter() -> None:
    harness = google_harness()
    try:
        harness["bigquery"].write_versioned_table(
            access_token="t",
            project_id="cust-proj",
            dataset_id="prem3_modeling",
            table_id="canonical_media",
            columns=["a"],
            rows=[["1"]],
            location="US",
        )
    except PermissionError:
        return
    raise AssertionError("canonical_* must be rejected")
