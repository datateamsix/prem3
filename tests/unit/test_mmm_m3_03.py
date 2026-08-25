"""M3-03: compute-agnostic official fit, provenance, and integrated dispatch."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.modeling.common.errors import (
    QualificationAcceptanceError,
    WorkerProvenanceError,
)
from app.modeling.mmm.contracts import (
    PRODUCTION_OFFICIAL_RUNTIME_MODES,
    ComputeProfile,
    FitDispatchStatus,
    FitPurpose,
    MeridianRuntimeMode,
)
from app.modeling.mmm.feasibility import (
    CpuFeasibility,
    music_center_cpu_final_feasibility,
)
from app.modeling.mmm.jobs import compute_profile_job_spec
from app.modeling.mmm.ledger import compile_fit_run_row
from app.modeling.mmm.provenance import (
    HISTORICAL_UNCOMMITTED_WORKER_DIGESTS,
    AllowlistedSourceHistory,
)
from app.modeling.mmm.service import MMMModelingService
from app.service.app import create_app
from app.service.evaluation_jobs import FakeEvaluationJobLauncher
from app.service.service_identity import ServiceIdentity
from tests.unit.test_mmm_modeling import (
    _final_official_service,
    _fit_ready,
    _official_service,
    _start,
)


def test_official_cpu_final_is_acceptance_eligible() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    approval = service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    run = next(iter(service.repo.list_fit_runs(version.model_version_id)))
    assert run.runtime_mode is MeridianRuntimeMode.OFFICIAL_CPU
    assert run.runtime_mode in PRODUCTION_OFFICIAL_RUNTIME_MODES
    assert approval.decision.value == "ACCEPT"


def test_cpu_smoke_is_not_acceptance_eligible() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(QualificationAcceptanceError, match="OFFICIAL_CPU_SMOKE"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_gpu_not_required_by_acceptance_gate() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    run = next(iter(service.repo.list_fit_runs(version.model_version_id)))
    assert run.runtime_mode is not MeridianRuntimeMode.OFFICIAL_GPU
    service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )


def test_fit_purpose_final_required() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.MODEL_ITERATION)
    with pytest.raises(QualificationAcceptanceError, match="cannot become MODEL_ACCEPTED"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_worker_source_commit_required_for_final_model() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    service.source_commit_sha = None
    service.source_history = AllowlistedSourceHistory(frozenset())
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    with pytest.raises(WorkerProvenanceError, match="source_commit_sha"):
        service.compile_fit_plan(version, fit_purpose=FitPurpose.FINAL_MODEL)


def test_uncommitted_worker_digest_ineligible_for_final_model() -> None:
    digest = next(iter(HISTORICAL_UNCOMMITTED_WORKER_DIGESTS))
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    service.worker_image_digest = digest
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    with pytest.raises(WorkerProvenanceError, match="Uncommitted worker digest"):
        service.compile_fit_plan(version, fit_purpose=FitPurpose.FINAL_MODEL)


def _dispatch_ready_service() -> tuple[MMMModelingService, object, object]:
    # Circularity: dispatch imports evaluation_dispatch which imports app.service.
    from app.modeling.mmm.dispatch import FakeFitDispatcher

    dispatcher = FakeFitDispatcher()
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    service.dispatcher = dispatcher
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    run = _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    assert run.dispatch_id
    dispatch = service.repo.get_dispatch(run.dispatch_id)
    assert dispatch is not None
    return service, dispatcher, dispatch


def test_live_api_dispatch_route() -> None:
    service, _dispatcher, dispatch = _dispatch_ready_service()
    launcher = FakeEvaluationJobLauncher()
    app = create_app(mmm_modeling=service, mmm_fit_launcher=launcher)
    client = TestClient(app, raise_server_exceptions=False)
    verifier = client.app.state.mmm_service_identity_verifier
    verifier.identities["svc-fit"] = ServiceIdentity(
        email=verifier.allowed_email,
        subject="sa-fit-dispatcher",
        audience=verifier.audience,
    )
    response = client.post(
        f"/internal/v1/mmm-fit-dispatches/{dispatch.dispatch_id}/launch",
        headers={"Authorization": "Bearer svc-fit"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["dispatch_id"] == dispatch.dispatch_id
    assert dispatch.dispatch_id in launcher.calls
    stored = service.repo.get_dispatch(dispatch.dispatch_id)
    assert stored is not None
    assert stored.cloud_run_execution_name
    assert stored.status is FitDispatchStatus.RUNNING


def test_cloud_task_launch_idempotency() -> None:
    service, dispatcher, dispatch = _dispatch_ready_service()
    launcher = FakeEvaluationJobLauncher()
    first = service.launch_dispatch(dispatch.dispatch_id, launcher=launcher)
    second = service.launch_dispatch(dispatch.dispatch_id, launcher=launcher)
    assert first.dispatch_id == second.dispatch_id
    assert first.cloud_run_execution_name == second.cloud_run_execution_name
    assert launcher.calls == [dispatch.dispatch_id]
    again = service.start_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=dispatch.model_version_id,
    )
    assert again.dispatch_id == dispatch.dispatch_id
    assert len(dispatcher.calls) == 1


def test_qualification_rows_distinct_from_final_rows() -> None:
    smoke = _official_service()
    smoke_version = _start(smoke)
    smoke_run = _fit_ready(smoke, smoke_version)
    final = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    final_version = _start(final, compute_profile=ComputeProfile.CPU_STANDARD)
    final_run = _fit_ready(final, final_version, fit_purpose=FitPurpose.FINAL_MODEL)
    smoke_row = compile_fit_run_row(
        smoke_run, cycle_id=smoke_version.cycle_id, track_id=smoke_version.track_id
    )
    final_row = compile_fit_run_row(
        final_run, cycle_id=final_version.cycle_id, track_id=final_version.track_id
    )
    assert smoke_row["runtime_mode"] == MeridianRuntimeMode.OFFICIAL_CPU_SMOKE.value
    assert smoke_row["fit_purpose"] == FitPurpose.RUNTIME_QUALIFICATION.value
    assert final_row["runtime_mode"] == MeridianRuntimeMode.OFFICIAL_CPU.value
    assert final_row["fit_purpose"] == FitPurpose.FINAL_MODEL.value
    assert smoke_row["fit_run_id"] != final_row["fit_run_id"]


def test_cpu_standard_is_server_owned_official_cpu() -> None:
    spec = compute_profile_job_spec(ComputeProfile.CPU_STANDARD, load_settings())
    assert spec["gpu"] is None
    assert spec["runtime_mode"] == "OFFICIAL_CPU"
    assert spec["cpu"] == "4"


def test_music_center_official_mcmc_on_cpu_is_not_feasible() -> None:
    status, rationale, scaled = music_center_cpu_final_feasibility(
        n_chains=7,
        n_adapt=1000,
        n_burnin=500,
        n_keep=1000,
        timeout_seconds=3600,
    )
    assert status is CpuFeasibility.NOT_FEASIBLE
    assert "not reduced" in rationale.lower() or "MCMC is not reduced" in rationale
    assert scaled > 3600
