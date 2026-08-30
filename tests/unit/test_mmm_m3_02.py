"""M3-02 production-truth: FitPurpose, GPU extra, human actor, official smoke helpers."""

from __future__ import annotations

import pytest

from app.config import load_settings
from app.modeling.common.errors import (
    GpuNotVisibleError,
    HumanApprovalRequiredError,
    QualificationAcceptanceError,
    SerdeError,
)
from app.modeling.mmm.contracts import ComputeProfile, FitPurpose, MeridianRuntimeMode
from app.modeling.mmm.design import OFFICIAL_STANDARD_MCMC, QUALIFICATION_MCMC
from app.modeling.mmm.failures import classify_failure
from app.modeling.mmm.jobs import default_fit_launcher
from app.modeling.mmm.meridian.runner import (
    InstalledMeridianLibrary,
    RecordingMeridianLibrary,
    _map_official_review,
)
from app.modeling.mmm.smoke import tiny_smoke_fit_plan, tiny_smoke_plan
from app.service.evaluation_jobs import CloudRunEvaluationJobLauncher, FakeEvaluationJobLauncher
from tests.unit.test_mmm_modeling import (
    PASS_CHECKS,
    _final_official_service,
    _fit_ready,
    _official_service,
    _start,
)


def test_cpu_smoke_cannot_become_model_accepted() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version, fit_purpose=FitPurpose.RUNTIME_QUALIFICATION)
    with pytest.raises(QualificationAcceptanceError, match="MODEL_ACCEPTED"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_iteration_fit_cannot_become_model_accepted() -> None:
    service = _final_official_service()
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.MODEL_ITERATION)
    with pytest.raises(QualificationAcceptanceError, match="cannot become MODEL_ACCEPTED"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_service_account_cannot_accept_model() -> None:
    service = _final_official_service()
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(HumanApprovalRequiredError, match="service account"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="m3-runtime@modelready-m3.iam.gserviceaccount.com",
        )


def test_official_mcmc_recommendation_is_guidance() -> None:
    assert OFFICIAL_STANDARD_MCMC["n_chains"] == 7
    assert OFFICIAL_STANDARD_MCMC["n_adapt"] == 1000
    assert QUALIFICATION_MCMC["label"] == "QUALIFICATION / ITERATION"


def test_tiny_smoke_plan_is_qualification_only() -> None:
    plan = tiny_smoke_plan()
    fit = tiny_smoke_fit_plan(plan)
    assert fit.fit_purpose is FitPurpose.RUNTIME_QUALIFICATION
    assert fit.n_chains == QUALIFICATION_MCMC["n_chains"]
    assert plan.model_window_start == "2024-01-01"


def test_fit_launcher_sets_mmm_dispatch_env() -> None:
    launcher = default_fit_launcher(load_settings(), local=True)
    assert isinstance(launcher, FakeEvaluationJobLauncher)
    cloud = CloudRunEvaluationJobLauncher(
        project_id="modelready-m3",
        location="us-central1",
        job_name="prem3-meridian-model-worker",
        dispatch_env_var="PREM3_MMM_FIT_DISPATCH_ID",
    )
    assert cloud._dispatch_env_var == "PREM3_MMM_FIT_DISPATCH_ID"


def test_failure_classes_are_closed() -> None:

    assert classify_failure(GpuNotVisibleError("missing")) == "GPU_NOT_VISIBLE"
    assert classify_failure(SerdeError("bad")) == "SERDE_ERROR"


def test_official_reviewer_maps_case_status() -> None:

    class _Status:
        name = "FAIL"

    class _Case:
        status = _Status()
        recommendation = "Inspect R-hat."

    class ConvergenceCheckResult:
        case = _Case()
        recommendation = "Inspect R-hat."

    class _Summary:
        results = (ConvergenceCheckResult(),)

    mapped = _map_official_review(_Summary())
    assert mapped[0].check_name == "ConvergenceCheck"
    assert mapped[0].status.value == "FAIL"


def test_music_center_cycle_is_distinct_from_model_window() -> None:
    from app.modeling.mmm.coverage import (
        MUSIC_CENTER_MODEL_READY_COVERAGE,
        assert_cycle_does_not_define_window,
        candidate_window_from_coverage,
    )

    selected_cycle_name = "Q3 2026"
    start, end = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert selected_cycle_name == "Q3 2026"
    assert start == "2024-01-01"
    assert end == "2026-06-29"
    assert_cycle_does_not_define_window(
        cycle_start="2026-07-01",
        cycle_end="2026-09-30",
        model_window_start=start,
        model_window_end=end,
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )


def test_resolve_fit_input_mapping_uses_tiny_fixture() -> None:
    pytest.importorskip("pandas")
    from app.modeling.mmm.smoke import resolve_fit_input_mapping, tiny_smoke_plan

    mapping = resolve_fit_input_mapping(tiny_smoke_plan())
    assert mapping["fingerprint"] == "official-cpu-smoke-tiny"
    assert mapping["frame"] is not None


def test_live_firestore_already_exists_is_canonical() -> None:
    from app.modeling.mmm.firestore import _already_exists

    class AlreadyExists(Exception):
        pass

    assert _already_exists(FileExistsError("dup"))
    assert _already_exists(AlreadyExists())
    assert not _already_exists(RuntimeError("other"))


def test_ledger_ddl_does_not_hardcode_customer_project() -> None:
    from app.modeling.mmm.ledger import ledger_table_ddl

    sql = ledger_table_ddl(
        project_id="injected-project", dataset_id="injected_ds", table="mmm_fit_runs"
    )
    assert "injected-project.injected_ds.mmm_fit_runs" in sql
    assert "modelready-m3" not in sql
    assert "CREATE TABLE IF NOT EXISTS" in sql


def test_service_persists_versioned_gcs_artifacts() -> None:
    from app.service.object_store import FakeObjectStore

    store = FakeObjectStore()
    service = _official_service()
    service.object_store = store
    service.artifact_bucket = "artifacts"
    version = _start(service)
    _fit_ready(service, version)
    prefix = f"ten_a/prj_a/modeling/{version.model_version_id}/"
    assert ( "artifacts", f"{prefix}meridian_model.binpb") in store.objects
    assert ("artifacts", f"{prefix}model_artifact_manifest.json") in store.objects
    assert ("artifacts", f"{prefix}model_review_pack.json") in store.objects


def test_recording_library_is_not_installed_library() -> None:
    assert RecordingMeridianLibrary is not InstalledMeridianLibrary
    assert PASS_CHECKS
    assert MeridianRuntimeMode.OFFICIAL_CPU_SMOKE.value == "OFFICIAL_CPU_SMOKE"
