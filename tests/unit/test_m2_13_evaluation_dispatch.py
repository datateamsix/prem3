"""M2-13 durable Evaluation dispatch, launch auth, claim, and read-model tests."""

from __future__ import annotations

import asyncio
import inspect
import json
from datetime import UTC, datetime, timedelta

from app.control_plane.dispatch_claims import utc_now
from app.control_plane.entitlements import PlanId
from app.control_plane.ids import (
    new_dispatch_id,
    new_run_id,
    new_upload_file_id,
    new_upload_id,
)
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.models import (
    DatasetEvaluationRef,
    DatasetUpload,
    DatasetUploadFile,
    DispatchStatus,
    EvaluationDispatch,
    EvaluationStatus,
    Feature,
    UploadStatus,
)
from app.publish_execution.contracts import ModelReadyEvidence
from app.publish_execution.model_ready import InMemoryModelReadyEvidenceResolver
from app.service.evaluation_dispatch import FakeEvaluationDispatcher
from app.service.evaluation_executor import EvaluationExecutionResult
from app.service.evaluation_jobs import FakeEvaluationJobLauncher
from app.service.evaluation_progress import compose_execution_view
from app.service.service_identity import FakeServiceIdentityVerifier, ServiceIdentity
from app.workers.evaluation_runtime import execute_claimed_dispatch
from app.workers.evaluation_worker import main as evaluation_worker_main
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.test_prem3_uploads_evaluations import _paid_client


def _verified_eval_client():
    client, repo, tenant, workspace, dataset, store, _signer = _paid_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/uploads",
        headers=auth_header(),
        json={
            "files": [
                {"filename": "geo.csv", "content_type": "text/csv", "size_bytes": 12}
            ]
        },
    ).json()
    upload = repo.get_upload(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace["workspace_id"],
        dataset_id=dataset["dataset_id"],
        upload_id=created["upload_id"],
    )
    assert upload is not None
    store.put_bytes(
        bucket="prem3-test-raw",
        object_name=upload.files[0].object_name,
        data=b"hello,world\n",
        content_type="text/csv",
    )
    assert (
        client.post(
            f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}"
            f"/uploads/{created['upload_id']}/complete",
            headers=auth_header(),
        ).status_code
        == 200
    )
    return client, repo, tenant, workspace, dataset, created["upload_id"]


def test_create_evaluation_creates_dispatch() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    response = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    dispatch = repo.get_evaluation_dispatch_for_run(tenant_id=tenant.tenant_id, run_id=run_id)
    assert dispatch is not None
    assert dispatch.run_id == run_id
    assert dispatch.tenant_id == tenant.tenant_id


def test_create_evaluation_enqueues_durable_task() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    dispatcher = client.app.state.evaluation_dispatcher
    assert isinstance(dispatcher, FakeEvaluationDispatcher)
    client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    assert dispatcher.calls
    payload = json.loads(dispatcher.calls[0]["payload"])
    assert set(payload) == {"dispatch_id"}


def test_202_only_after_enqueue_success() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    response = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    assert response.status_code == 202
    dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=response.json()["run_id"]
    )
    assert dispatch is not None
    assert dispatch.status is DispatchStatus.QUEUED


def test_enqueue_failure_not_202() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    dispatcher = client.app.state.evaluation_dispatcher
    assert isinstance(dispatcher, FakeEvaluationDispatcher)
    dispatcher.fail_next = True
    response = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "EVALUATION_DISPATCH_UNAVAILABLE"
    rows = repo.list_evaluations_for_dataset(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace["workspace_id"],
        dataset_id=dataset["dataset_id"],
    )
    assert len(rows) == 1
    dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=rows[0].run_id
    )
    assert dispatch is not None
    assert dispatch.status is DispatchStatus.FAILED_RETRYABLE


def test_idempotent_retry_reuses_evaluation_and_dispatch() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    headers = {**auth_header(), "Idempotency-Key": "eval-key-1"}
    first = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=headers,
        json={"upload_id": upload_id},
    )
    second = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=headers,
        json={"upload_id": upload_id},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["run_id"] == second.json()["run_id"]
    first_dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=first.json()["run_id"]
    )
    second_dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=second.json()["run_id"]
    )
    assert first_dispatch is not None and second_dispatch is not None
    assert first_dispatch.dispatch_id == second_dispatch.dispatch_id


def test_idempotent_retry_reuses_evaluation() -> None:
    test_idempotent_retry_reuses_evaluation_and_dispatch()


def test_idempotent_retry_reuses_dispatch() -> None:
    test_idempotent_retry_reuses_evaluation_and_dispatch()


def test_client_cannot_supply_dispatch_id() -> None:
    test_client_cannot_supply_dispatch_id_or_run_id_or_tenant()


def test_client_cannot_supply_run_id() -> None:
    test_client_cannot_supply_dispatch_id_or_run_id_or_tenant()


def test_client_cannot_supply_tenant() -> None:
    test_client_cannot_supply_dispatch_id_or_run_id_or_tenant()


def test_orphan_enqueue_failure_retries_same_evaluation_and_dispatch() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    dispatcher = client.app.state.evaluation_dispatcher
    assert isinstance(dispatcher, FakeEvaluationDispatcher)
    headers = {**auth_header(), "Idempotency-Key": "eval-orphan-1"}
    dispatcher.fail_next = True
    first = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=headers,
        json={"upload_id": upload_id},
    )
    assert first.status_code == 503
    rows = repo.list_evaluations_for_dataset(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace["workspace_id"],
        dataset_id=dataset["dataset_id"],
    )
    assert len(rows) == 1
    failed = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=rows[0].run_id
    )
    assert failed is not None
    assert failed.status is DispatchStatus.FAILED_RETRYABLE
    second = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=headers,
        json={"upload_id": upload_id},
    )
    assert second.status_code == 202
    assert second.json()["run_id"] == rows[0].run_id
    recovered = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=rows[0].run_id
    )
    assert recovered is not None
    assert recovered.dispatch_id == failed.dispatch_id
    assert recovered.status is DispatchStatus.QUEUED
    assert len(dispatcher.calls) == 1


def test_task_payload_contains_only_dispatch_authority() -> None:
    test_create_evaluation_enqueues_durable_task()


def test_client_cannot_supply_dispatch_id_or_run_id_or_tenant() -> None:
    client, _repo, _tenant, workspace, dataset, upload_id = _verified_eval_client()
    response = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={
            "upload_id": upload_id,
            "run_id": "run_attacker000001",
            "dispatch_id": "dsp_attacker000001",
            "tenant_id": "ten_attacker000001",
        },
    )
    assert response.status_code == 422


def test_internal_launch_rejects_unauthenticated() -> None:
    client, _repo = make_client()
    response = client.post("/internal/v1/evaluation-dispatches/dsp_missing0000001/launch")
    assert response.status_code == 401
    assert response.json()["code"] == "SERVICE_IDENTITY_REQUIRED"


def test_internal_launch_rejects_clerk_customer() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=created.json()["run_id"]
    )
    assert dispatch is not None
    response = client.post(
        f"/internal/v1/evaluation-dispatches/{dispatch.dispatch_id}/launch",
        headers=auth_header(),
    )
    assert response.status_code == 401
    assert response.json()["code"] == "SERVICE_IDENTITY_REQUIRED"


def test_internal_launch_rejects_wrong_service_identity() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=created.json()["run_id"]
    )
    assert dispatch is not None
    verifier = client.app.state.service_identity_verifier
    assert isinstance(verifier, FakeServiceIdentityVerifier)
    verifier.identities["wrong"] = ServiceIdentity(
        email="not-dispatcher@example.com",
        subject="sa-wrong",
        audience=verifier.audience,
    )
    response = client.post(
        f"/internal/v1/evaluation-dispatches/{dispatch.dispatch_id}/launch",
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_internal_launch_accepts_dispatch_service_identity() -> None:
    client, repo, tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    )
    dispatch = repo.get_evaluation_dispatch_for_run(
        tenant_id=tenant.tenant_id, run_id=created.json()["run_id"]
    )
    assert dispatch is not None
    verifier = client.app.state.service_identity_verifier
    assert isinstance(verifier, FakeServiceIdentityVerifier)
    verifier.identities["svc-ok"] = ServiceIdentity(
        email=verifier.allowed_email,
        subject="sa-dispatcher",
        audience=verifier.audience,
    )
    response = client.post(
        f"/internal/v1/evaluation-dispatches/{dispatch.dispatch_id}/launch",
        headers={"Authorization": "Bearer svc-ok"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["dispatch_id"] == dispatch.dispatch_id
    launcher = client.app.state.evaluation_job_launcher
    assert isinstance(launcher, FakeEvaluationJobLauncher)
    assert dispatch.dispatch_id in launcher.calls


def test_cloud_task_headers_not_identity_authority() -> None:
    client, _repo = make_client()
    response = client.post(
        "/internal/v1/evaluation-dispatches/dsp_missing0000001/launch",
        headers={"X-CloudTasks-TaskName": "prem3-eval-dsp_missing0000001"},
    )
    assert response.status_code == 401


def test_invalid_dispatch_not_found() -> None:
    client, _repo = make_client()
    verifier = client.app.state.service_identity_verifier
    assert isinstance(verifier, FakeServiceIdentityVerifier)
    verifier.identities["svc-ok"] = ServiceIdentity(
        email=verifier.allowed_email,
        subject="sa-dispatcher",
        audience=verifier.audience,
    )
    response = client.post(
        "/internal/v1/evaluation-dispatches/dsp_missing0000001/launch",
        headers={"Authorization": "Bearer svc-ok"},
    )
    assert response.status_code == 404


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute_evaluation(self, run_id: str, **_kwargs) -> EvaluationExecutionResult:
        self.calls.append(run_id)
        return EvaluationExecutionResult(run_id=run_id, event_count=1)


def _seed_dispatch(repo: InMemoryControlPlaneRepository) -> EvaluationDispatch:
    tenant, _identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    reloaded = repo.get_tenant(tenant.tenant_id)
    tenant = reloaded if reloaded is not None else tenant
    workspace = repo.create_workspace_with_capacity(
        tenant_id=tenant.tenant_id, name="Dispatch"
    )
    dataset = repo.create_dataset(
        tenant_id=tenant.tenant_id, workspace_id=workspace.workspace_id, name="A"
    )
    now = datetime.now(UTC)
    upload = DatasetUpload(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        dataset_id=dataset.dataset_id,
        upload_id=new_upload_id(),
        status=UploadStatus.VERIFIED,
        object_prefix="objects/demo/",
        files=[
            DatasetUploadFile(
                upload_file_id=new_upload_file_id(),
                original_filename="geo.csv",
                object_name="objects/demo/geo.csv",
                content_type="text/csv",
                declared_size_bytes=4,
                actual_size_bytes=4,
                generation="1",
                created_at=now,
                verified_at=now,
            )
        ],
        package_uri="gs://bucket/objects/demo/",
        package_fingerprint="abc",
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    repo.create_upload(upload)
    evaluation = DatasetEvaluationRef(
        tenant_id=tenant.tenant_id,
        workspace_id=workspace.workspace_id,
        dataset_id=dataset.dataset_id,
        upload_id=upload.upload_id,
        run_id=new_run_id(),
        entitlement_snapshot_id=tenant.current_entitlement_snapshot_id or "ent_missing000000001",
        status=EvaluationStatus.ACCEPTED,
        package_uri=upload.package_uri or "gs://bucket/objects/demo/",
        package_fingerprint=upload.package_fingerprint,
        created_at=now,
        updated_at=now,
    )
    repo.put_evaluation_ref(evaluation)
    dispatch = EvaluationDispatch(
        dispatch_id=new_dispatch_id(),
        tenant_id=evaluation.tenant_id,
        workspace_id=evaluation.workspace_id,
        dataset_id=evaluation.dataset_id,
        run_id=evaluation.run_id,
        evaluation_created_at=evaluation.created_at,
        status=DispatchStatus.QUEUED,
        cloud_run_job_name="prem3-evaluation-worker",
        created_at=now,
        updated_at=now,
    )
    return repo.put_evaluation_dispatch(dispatch)


def test_worker_loads_server_owned_dispatch_and_calls_executor() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    executor = _RecordingExecutor()
    code = execute_claimed_dispatch(
        repo=repo,
        executor=executor,  # type: ignore[arg-type]
        dispatch_id=dispatch.dispatch_id,
        owner="exec-1:0",
        execution_name="exec-1",
        run_async=asyncio.run,
    )
    assert code == 0
    assert executor.calls == [dispatch.run_id]
    stored = repo.get_evaluation_dispatch(dispatch.dispatch_id)
    assert stored is not None
    assert stored.status is DispatchStatus.SUCCEEDED


def test_worker_binds_service_tenant_and_frozen_snapshot() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    evaluation = repo.get_evaluation_ref(tenant_id=dispatch.tenant_id, run_id=dispatch.run_id)
    assert evaluation is not None
    snapshot = repo.get_entitlement_snapshot(
        tenant_id=evaluation.tenant_id, snapshot_id=evaluation.entitlement_snapshot_id
    )
    assert snapshot is not None
    assert Feature.DATASET_ASSESSMENT in snapshot.features


def test_worker_verifies_workspace_dataset_run_consistency() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    mutated = dispatch.model_copy(update={"workspace_id": "wsp_other00000000001"})
    repo._evaluation_dispatches[dispatch.dispatch_id] = mutated
    executor = _RecordingExecutor()
    code = execute_claimed_dispatch(
        repo=repo,
        executor=executor,  # type: ignore[arg-type]
        dispatch_id=dispatch.dispatch_id,
        owner="exec-2:0",
        execution_name="exec-2",
        run_async=asyncio.run,
    )
    assert code == 0
    assert executor.calls == []
    stored = repo.get_evaluation_dispatch(dispatch.dispatch_id)
    assert stored is not None
    assert stored.status is DispatchStatus.FAILED_TERMINAL


def test_worker_loads_server_owned_dispatch() -> None:
    test_worker_loads_server_owned_dispatch_and_calls_executor()


def test_worker_binds_service_tenant() -> None:
    test_worker_binds_service_tenant_and_frozen_snapshot()


def test_worker_uses_frozen_entitlement_snapshot() -> None:
    test_worker_binds_service_tenant_and_frozen_snapshot()


def test_worker_calls_existing_evaluation_executor() -> None:
    test_worker_loads_server_owned_dispatch_and_calls_executor()


def test_worker_uses_evaluation_package_uri_not_external_argument() -> None:
    test_worker_never_accepts_external_authority_args()


def test_worker_never_accepts_package_argument() -> None:
    test_worker_never_accepts_external_authority_args()


def test_worker_never_accepts_tenant_argument() -> None:
    test_worker_never_accepts_external_authority_args()


def test_worker_never_accepts_storage_destination() -> None:
    test_worker_never_accepts_external_authority_args()


def test_dispatch_claim_atomic() -> None:
    test_dispatch_claim_atomic_and_duplicate_denied()


def test_worker_never_accepts_external_authority_args() -> None:
    runtime_params = set(inspect.signature(execute_claimed_dispatch).parameters)
    worker_params = set(inspect.signature(evaluation_worker_main).parameters)
    forbidden = {
        "package_uri",
        "tenant_id",
        "workspace_id",
        "dataset_id",
        "upload_id",
        "destination",
        "storage_destination",
        "gcs_path",
    }
    assert runtime_params.isdisjoint(forbidden)
    assert worker_params.isdisjoint(forbidden)
    assert inspect.signature(evaluation_worker_main).parameters == {}


def test_dispatch_claim_atomic_and_duplicate_denied() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    now = utc_now()
    first, claimed = repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-a:0",
        execution_name="exec-a",
        now=now,
    )
    second, denied = repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-b:0",
        execution_name="exec-b",
        now=now,
    )
    assert first == "claimed"
    assert second == "denied"
    assert claimed is not None
    assert denied is not None
    assert denied.claim_owner == "exec-a:0"


def test_same_cloud_run_execution_retry_can_resume() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    now = utc_now()
    repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-a:0",
        execution_name="exec-a",
        now=now,
    )
    outcome, again = repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-a:1",
        execution_name="exec-a",
        now=now + timedelta(seconds=1),
    )
    assert outcome == "reclaimed"
    assert again is not None
    assert again.claim_owner == "exec-a:1"


def test_different_execution_cannot_steal_active_claim() -> None:
    test_dispatch_claim_atomic_and_duplicate_denied()


def test_expired_claim_can_recover() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    past = utc_now() - timedelta(hours=3)
    repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-old:0",
        execution_name="exec-old",
        now=past,
    )
    expired = repo.get_evaluation_dispatch(dispatch.dispatch_id)
    assert expired is not None
    expired = expired.model_copy(update={"claim_expires_at": past})
    repo.put_evaluation_dispatch(expired)
    outcome, recovered = repo.claim_evaluation_dispatch(
        dispatch_id=dispatch.dispatch_id,
        owner="exec-new:0",
        execution_name="exec-new",
        now=utc_now(),
    )
    assert outcome == "claimed"
    assert recovered is not None
    assert recovered.claim_owner == "exec-new:0"


def test_duplicate_job_execution_only_one_claims() -> None:
    test_dispatch_claim_atomic_and_duplicate_denied()


def test_retryable_failure_exits_nonzero() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)

    class Boom:
        async def execute_evaluation(self, run_id: str, **_kwargs):
            raise RuntimeError("temporary firestore")

    code = execute_claimed_dispatch(
        repo=repo,
        executor=Boom(),  # type: ignore[arg-type]
        dispatch_id=dispatch.dispatch_id,
        owner="exec-r:0",
        execution_name="exec-r",
        run_async=asyncio.run,
    )
    assert code == 1
    stored = repo.get_evaluation_dispatch(dispatch.dispatch_id)
    assert stored is not None
    assert stored.status is DispatchStatus.FAILED_RETRYABLE


def test_terminal_authority_failure_not_retried() -> None:
    test_worker_verifies_workspace_dataset_run_consistency()


def test_success_terminal_idempotent() -> None:
    repo = InMemoryControlPlaneRepository()
    dispatch = _seed_dispatch(repo)
    executor = _RecordingExecutor()
    first = execute_claimed_dispatch(
        repo=repo,
        executor=executor,  # type: ignore[arg-type]
        dispatch_id=dispatch.dispatch_id,
        owner="exec-s:0",
        execution_name="exec-s",
        run_async=asyncio.run,
    )
    second = execute_claimed_dispatch(
        repo=repo,
        executor=executor,  # type: ignore[arg-type]
        dispatch_id=dispatch.dispatch_id,
        owner="exec-s2:0",
        execution_name="exec-s2",
        run_async=asyncio.run,
    )
    assert first == 0
    assert second == 0
    assert executor.calls == [dispatch.run_id]


def test_evaluation_status_remains_accepted() -> None:
    client, _repo, _tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    ).json()
    run = client.get(f"/v1/runs/{created['run_id']}", headers=auth_header())
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == EvaluationStatus.ACCEPTED.value
    assert body["execution"]["evaluation_status"] == EvaluationStatus.ACCEPTED.value


def test_dispatch_running_or_succeeded_does_not_imply_model_ready() -> None:
    now = utc_now()
    ev = DatasetEvaluationRef(
        tenant_id="ten_demo00000000000001",
        workspace_id="wsp_demo0000000000001",
        dataset_id="dset_demo000000000001",
        upload_id="upl_demo0000000000001",
        run_id="run_demo0000000000001",
        entitlement_snapshot_id="ent_demo0000000000001",
        status=EvaluationStatus.ACCEPTED,
        package_uri="gs://bucket/p/",
        created_at=now,
        updated_at=now,
    )
    running = EvaluationDispatch(
        dispatch_id="dsp_demo0000000000001",
        tenant_id=ev.tenant_id,
        workspace_id=ev.workspace_id,
        dataset_id=ev.dataset_id,
        run_id=ev.run_id,
        evaluation_created_at=now,
        status=DispatchStatus.RUNNING,
        cloud_run_job_name="prem3-evaluation-worker",
        created_at=now,
        updated_at=now,
    )
    view = compose_execution_view(ev, running)
    assert view.model_ready is False
    succeeded = running.model_copy(update={"status": DispatchStatus.SUCCEEDED})
    view2 = compose_execution_view(ev, succeeded)
    assert view2.model_ready is False
    assert view2.approval_required is True


def test_dispatch_running_does_not_imply_model_ready() -> None:
    test_dispatch_running_or_succeeded_does_not_imply_model_ready()


def test_dispatch_succeeded_does_not_imply_model_ready() -> None:
    test_dispatch_running_or_succeeded_does_not_imply_model_ready()


def test_approval_required_rendered_separately() -> None:
    now = utc_now()
    ev = DatasetEvaluationRef(
        tenant_id="ten_demo00000000000003",
        workspace_id="wsp_demo0000000000003",
        dataset_id="dset_demo000000000003",
        upload_id="upl_demo0000000000003",
        run_id="run_demo0000000000003",
        entitlement_snapshot_id="ent_demo0000000000003",
        status=EvaluationStatus.ACCEPTED,
        package_uri="gs://bucket/p/",
        created_at=now,
        updated_at=now,
    )
    dispatch = EvaluationDispatch(
        dispatch_id="dsp_demo0000000000003",
        tenant_id=ev.tenant_id,
        workspace_id=ev.workspace_id,
        dataset_id=ev.dataset_id,
        run_id=ev.run_id,
        evaluation_created_at=now,
        status=DispatchStatus.SUCCEEDED,
        cloud_run_job_name="prem3-evaluation-worker",
        created_at=now,
        updated_at=now,
    )
    view = compose_execution_view(ev, dispatch)
    assert view.model_ready is False
    assert view.approval_required is True
    assert view.outcome == "WAITING_FOR_APPROVAL"


def test_model_ready_derived_from_run_evidence() -> None:
    now = utc_now()
    ev = DatasetEvaluationRef(
        tenant_id="ten_demo00000000000002",
        workspace_id="wsp_demo0000000000002",
        dataset_id="dset_demo000000000002",
        upload_id="upl_demo0000000000002",
        run_id="run_demo0000000000002",
        entitlement_snapshot_id="ent_demo0000000000002",
        status=EvaluationStatus.ACCEPTED,
        package_uri="gs://bucket/p/",
        created_at=now,
        updated_at=now,
    )
    resolver = InMemoryModelReadyEvidenceResolver()
    resolver.put(
        ModelReadyEvidence(
            tenant_id=ev.tenant_id,
            workspace_id=ev.workspace_id,
            dataset_id=ev.dataset_id,
            run_id=ev.run_id,
            fingerprint="7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f",
        )
    )
    dispatch = EvaluationDispatch(
        dispatch_id="dsp_demo0000000000002",
        tenant_id=ev.tenant_id,
        workspace_id=ev.workspace_id,
        dataset_id=ev.dataset_id,
        run_id=ev.run_id,
        evaluation_created_at=now,
        status=DispatchStatus.SUCCEEDED,
        cloud_run_job_name="prem3-evaluation-worker",
        created_at=now,
        updated_at=now,
    )
    view = compose_execution_view(ev, dispatch, model_ready_resolver=resolver)
    assert view.model_ready is True
    assert view.approval_required is False
    assert view.outcome == "MODEL_READY"


def test_public_run_view_hides_internal_cloud_identifiers() -> None:
    client, _repo, _tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    ).json()
    run = client.get(f"/v1/runs/{created['run_id']}", headers=auth_header()).json()
    blob = json.dumps(run)
    assert "cloud_task_name" not in blob
    assert "cloud_run_execution" not in blob
    assert "gs://" not in blob


def test_cross_tenant_run_read_denied() -> None:
    client, repo, _tenant, workspace, dataset, upload_id = _verified_eval_client()
    created = client.post(
        f"/v1/workspaces/{workspace['workspace_id']}/datasets/{dataset['dataset_id']}/evaluations",
        headers=auth_header(),
        json={"upload_id": upload_id},
    ).json()
    other, other_identity = seed_tenant(
        repo, display_name="Other", provider_org="org_other", provider_user="user_other"
    )
    del other
    other_client, _ = make_client(repo=repo, identity=other_identity)
    response = other_client.get(f"/v1/runs/{created['run_id']}", headers=auth_header())
    assert response.status_code == 404
