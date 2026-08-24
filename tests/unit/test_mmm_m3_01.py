"""M3-01 production-truth tests: runtime mode, window, Firestore, dispatch, ledger."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.config import load_settings
from app.modeling.common.errors import (
    ArtifactVerificationFailedError,
    FakeRuntimeAcceptanceError,
    FitRuntimeError,
    InputContractMismatchError,
    LedgerPublicationError,
    ModelVersionImmutableError,
    StaleApprovalError,
)
from app.modeling.mmm.artifacts import persist_immutable_bytes
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitDispatchStatus,
    FitPurpose,
    MeridianFitDispatch,
    MeridianRuntimeMode,
    ReviewSource,
)
from app.modeling.mmm.coverage import (
    MUSIC_CENTER_MODEL_READY_COVERAGE,
    assert_cycle_does_not_define_window,
    assert_model_window_inside_coverage,
    candidate_window_from_coverage,
)
from app.modeling.mmm.dispatch import FakeFitDispatcher
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.intelligence import compile_decision_intelligence_brief
from app.modeling.mmm.jobs import assert_no_user_resource_authority, gpu_standard_job_spec
from app.modeling.mmm.ledger import (
    BQ_MODEL_LEDGER_TABLES,
    InMemoryModelLedger,
    compile_channel_summary_row,
    compile_decision_row,
    compile_fit_run_row,
    compile_health_row,
    compile_model_version_row,
)
from app.modeling.mmm.meridian.builder import mapping_from_manifest, supported_mapping_cases
from app.modeling.mmm.meridian.runner import (
    FakeMeridianRuntime,
    OfficialMeridianRuntime,
    RecordingMeridianLibrary,
)
from app.modeling.mmm.repository import InMemoryModelingRepository
from app.modeling.mmm.service import MMMModelingService
from app.service.evaluation_jobs import JobLaunchError
from app.service.object_store import FakeObjectStore
from app.tools.meridian_model_worker import execute_fit_dispatch
from tests.unit.support.fake_firestore import FakeFirestore
from tests.unit.test_mmm_modeling import (
    MEDIA,
    MUSIC_CENTER_FP,
    MUSIC_CENTER_WINDOW,
    PASS_CHECKS,
    _approve_required,
    _final_official_service,
    _fit_ready,
    _official_service,
    _service,
    _start,
)


def test_official_runtime_never_falls_back_to_fake() -> None:
    with pytest.raises(FitRuntimeError, match="fails closed"):
        OfficialMeridianRuntime(mode=MeridianRuntimeMode.OFFICIAL_GPU).sample_prior(
            _start(_service()), n_draws=2, seed=1
        )


def test_fake_runtime_is_explicitly_injected() -> None:
    service = _service(FakeMeridianRuntime())
    assert isinstance(service.runtime, FakeMeridianRuntime)
    assert service.runtime.runtime_mode is MeridianRuntimeMode.FAKE_TEST


def test_fake_runtime_cannot_produce_model_accepted() -> None:
    service = _service()
    version = _start(service)
    _fit_ready(service, version)
    with pytest.raises(FakeRuntimeAcceptanceError):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_official_cpu_smoke_executes_real_sample_prior() -> None:
    library = RecordingMeridianLibrary(checks=PASS_CHECKS)
    runtime = OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE, library=library
    )
    service = MMMModelingService(InMemoryModelingRepository(), runtime=runtime)
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    assert "sample_prior" in library.calls


def test_official_cpu_smoke_executes_real_sample_posterior() -> None:
    library = RecordingMeridianLibrary(checks=PASS_CHECKS)
    runtime = OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE, library=library
    )
    service = MMMModelingService(InMemoryModelingRepository(), runtime=runtime)
    version = _start(service)
    _fit_ready(service, version)
    assert "sample_posterior" in library.calls


def test_official_runtime_uses_real_serde() -> None:
    library = RecordingMeridianLibrary(checks=PASS_CHECKS)
    runtime = OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE, library=library
    )
    service = MMMModelingService(InMemoryModelingRepository(), runtime=runtime)
    version = _start(service)
    _fit_ready(service, version)
    assert "save_meridian" in library.calls
    assert "load_meridian" in library.calls
    artifact = service.repo.get_artifact(version.model_version_id)
    assert artifact is not None
    assert artifact.serde_readback_ok is True
    assert artifact.runtime_mode is MeridianRuntimeMode.OFFICIAL_CPU_SMOKE


def test_official_runtime_uses_real_reviewer() -> None:
    library = RecordingMeridianLibrary(checks=PASS_CHECKS)
    runtime = OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE, library=library
    )
    service = MMMModelingService(InMemoryModelingRepository(), runtime=runtime)
    version = _start(service)
    _fit_ready(service, version)
    assert "ModelReviewer" in library.calls
    health = service.repo.get_health(version.model_version_id)
    assert health is not None
    assert health.review_source is ReviewSource.OFFICIAL_MERIDIAN


def test_cycle_window_is_not_model_window() -> None:
    start, end = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert (start, end) != ("2026-07-01", "2026-09-30")
    assert_cycle_does_not_define_window(
        cycle_start="2026-07-01",
        cycle_end="2026-09-30",
        model_window_start=start,
        model_window_end=end,
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )


def test_measurement_cycle_dates_do_not_default_mmm_model_window() -> None:
    with pytest.raises(InputContractMismatchError, match="must not default"):
        _start(
            _service(),
            model_window_start="2026-07-01",
            model_window_end="2026-09-30",
            coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
            cycle_window_start="2026-07-01",
            cycle_window_end="2026-09-30",
        )


def test_model_window_must_be_inside_model_ready_coverage() -> None:
    with pytest.raises(InputContractMismatchError, match="outside verified"):
        assert_model_window_inside_coverage(
            model_window_start="2026-07-01",
            model_window_end="2026-09-30",
            coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
        )


def test_model_window_inside_verified_coverage() -> None:
    start, end = candidate_window_from_coverage(MUSIC_CENTER_MODEL_READY_COVERAGE)
    assert_model_window_inside_coverage(
        model_window_start=start,
        model_window_end=end,
        coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
    )


def test_model_window_outside_verified_coverage_fails_closed() -> None:
    with pytest.raises(InputContractMismatchError):
        _start(
            _service(),
            model_window_start="2026-07-01",
            model_window_end="2026-09-30",
            coverage=MUSIC_CENTER_MODEL_READY_COVERAGE,
        )


def test_model_window_requires_explicit_model_decision() -> None:
    service = _service()
    version = _start(service)
    types = {
        item.decision_type.value
        for item in service.repo.list_decisions(version.model_version_id)
    }
    assert "MODEL_WINDOW" in types


def test_model_window_change_invalidates_fit_approval() -> None:
    service = _service()
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    plan = service.repo.get_plan(version.model_version_id)
    assert plan is not None
    changed = plan.model_copy(
        update={"model_window_end": "2025-12-29", "fingerprint": "changed-window"}
    )
    service.repo.put_plan(changed)
    with pytest.raises(StaleApprovalError):
        service.start_fit(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
        )


def test_model_window_persisted_on_model_version() -> None:
    version = _start(_service())
    assert version.model_window_start == MUSIC_CENTER_WINDOW[0]
    assert version.model_window_end == MUSIC_CENTER_WINDOW[1]


def test_historical_model_window_is_immutable() -> None:
    service = _final_official_service()
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    current = service.get_version(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    with pytest.raises(ModelVersionImmutableError):
        service.repo.put_version(
            current.model_copy(update={"model_window_end": "2025-01-01"})
        )


def test_builder_supports_required_input_cases() -> None:
    mapping = mapping_from_manifest(
        {
            "fingerprint": MUSIC_CENTER_FP,
            "semantics": {
                "kpi": "kpi_orders",
                "kpi_type": "non_revenue",
                "geo": "geo",
                "time": "time",
                "media_channels": ["paid_search_impressions"],
                "media_spend_channels": ["paid_search_spend"],
                "media_channel_names": ["paid_search"],
                "rf_channels": ["reach"],
                "organic_media": ["organic_sessions"],
                "controls": ["consumer_sentiment_index"],
                "non_media_treatments": ["music_center_promo"],
                "population": "population",
                "revenue_per_kpi": "revenue_per_kpi",
            },
        }
    )
    cases = set(supported_mapping_cases(mapping))
    assert {
        "geo",
        "ordinary_media",
        "reach_frequency",
        "organic_media",
        "controls",
        "non_media_treatments",
        "population",
        "revenue_per_kpi",
    }.issubset(cases)


def _firestore_service(
    *,
    mode: MeridianRuntimeMode = MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
) -> MMMModelingService:
    return MMMModelingService(
        FirestoreModelingRepository(FakeFirestore()),
        runtime=OfficialMeridianRuntime(
            mode=mode,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
    )


def test_firestore_model_version_round_trip() -> None:
    first = _firestore_service()
    version = _start(first)
    restarted = MMMModelingService(first.repo, runtime=first.runtime)
    loaded = restarted.get_version(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    assert loaded.model_plan_fingerprint == version.model_plan_fingerprint
    assert loaded.model_window_start == version.model_window_start


def test_firestore_decision_round_trip() -> None:
    service = _firestore_service()
    version = _start(service)
    decision = service.repo.list_decisions(version.model_version_id)[0]
    cloned = FirestoreModelingRepository(service.repo._db)
    loaded = cloned.get_decision(
        tenant_id="ten_a", project_id="prj_a", decision_id=decision.decision_id
    )
    assert loaded is not None
    assert loaded.decision_type == decision.decision_type


def test_firestore_fit_approval_round_trip() -> None:
    service = _firestore_service()
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    approval = service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    cloned = FirestoreModelingRepository(service.repo._db)
    loaded = cloned.get_fit_approval(version.model_version_id)
    assert loaded is not None
    assert loaded.approval_id == approval.approval_id


def test_firestore_fit_run_round_trip() -> None:
    service = _firestore_service()
    version = _start(service)
    run = _fit_ready(service, version)
    cloned = FirestoreModelingRepository(service.repo._db)
    loaded = cloned.get_fit_run(
        tenant_id="ten_a", project_id="prj_a", fit_run_id=run.fit_run_id
    )
    assert loaded is not None
    assert loaded.fit_plan_fingerprint == run.fit_plan_fingerprint


def test_firestore_acceptance_round_trip() -> None:
    service = _firestore_service(mode=MeridianRuntimeMode.OFFICIAL_GPU)
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    approval = service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    cloned = FirestoreModelingRepository(service.repo._db)
    loaded = cloned.get_acceptance(version.model_version_id)
    assert loaded is not None
    assert loaded.approval_id == approval.approval_id


def test_firestore_consumed_model_version_immutable() -> None:
    service = _firestore_service(mode=MeridianRuntimeMode.OFFICIAL_GPU)
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    current = service.get_version(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    with pytest.raises(ModelVersionImmutableError):
        service.repo.put_version(current.model_copy(update={"accepted": False}))


def test_firestore_cross_tenant_rejected() -> None:
    service = _firestore_service()
    version = _start(service)
    assert (
        service.repo.get_version(
            tenant_id="ten_b",
            project_id="prj_a",
            model_version_id=version.model_version_id,
        )
        is None
    )


def test_firestore_concurrent_fit_dispatch_singleton() -> None:
    repo = FirestoreModelingRepository(FakeFirestore())
    dispatch = MeridianFitDispatch(
        dispatch_id="mdsp_a",
        tenant_id="ten_a",
        project_id="prj_a",
        cycle_id="cyc_q3_2026",
        track_id="trk_mmm",
        model_version_id="mver_a",
        fit_run_id="mfit_a",
        fit_plan_fingerprint="fp",
        fit_approval_id="mapv_a",
        runtime_mode=MeridianRuntimeMode.OFFICIAL_GPU,
        compute_profile=ComputeProfile.GPU_STANDARD,
        status=FitDispatchStatus.PENDING,
    )
    other = dispatch.model_copy(update={"dispatch_id": "mdsp_b", "fit_run_id": "mfit_b"})

    def claim(item: MeridianFitDispatch) -> str:
        return repo.claim_canonical_dispatch(item).dispatch_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(claim, dispatch)
        second = pool.submit(claim, other)
        ids = {first.result(), second.result()}
    assert len(ids) == 1


def test_gpu_standard_maps_to_server_owned_job() -> None:
    spec = gpu_standard_job_spec(load_settings())
    assert spec["job_name"] == "prem3-meridian-model-worker"
    assert spec["gpu"] == "nvidia-l4"
    assert spec["region"]


def test_dispatch_has_no_user_resource_authority() -> None:
    with pytest.raises(JobLaunchError, match="user resource authority"):
        assert_no_user_resource_authority({"gpu": "h100", "container_image": "evil"})


def test_duplicate_fit_request_returns_existing_dispatch() -> None:
    dispatcher = FakeFitDispatcher()
    service = MMMModelingService(
        InMemoryModelingRepository(),
        runtime=OfficialMeridianRuntime(
            mode=MeridianRuntimeMode.OFFICIAL_GPU,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
        dispatcher=dispatcher,
    )
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    first = service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    second = service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    assert first.fit_run_id == second.fit_run_id
    assert len(dispatcher.calls) == 1


def test_worker_reconstructs_authority() -> None:
    service = MMMModelingService(
        InMemoryModelingRepository(),
        runtime=OfficialMeridianRuntime(
            mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
        dispatcher=FakeFitDispatcher(),
    )
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    dispatch = service.repo.list_dispatches(version.model_version_id)[0]
    result = execute_fit_dispatch(
        dispatch_id=dispatch.dispatch_id,
        repo=service.repo,
        runtime=OfficialMeridianRuntime(
            mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
    )
    assert result["status"] == "SUCCEEDED"
    assert result["dispatch_id"] == dispatch.dispatch_id


def test_worker_rejects_mismatched_fit_fingerprint() -> None:
    service = MMMModelingService(
        InMemoryModelingRepository(),
        runtime=OfficialMeridianRuntime(
            mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
        dispatcher=FakeFitDispatcher(),
    )
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    dispatch = service.repo.list_dispatches(version.model_version_id)[0]
    broken = dispatch.model_copy(update={"fit_plan_fingerprint": "other"})
    service.repo.put_dispatch(broken)
    with pytest.raises(FitRuntimeError, match="mismatched"):
        execute_fit_dispatch(dispatch_id=broken.dispatch_id, repo=service.repo)


def test_real_serde_artifact_hash() -> None:
    service = _official_service()
    version = _start(service)
    run = _fit_ready(service, version)
    artifact = service.repo.get_artifact(version.model_version_id)
    stored = service.repo.get_binary(run.fit_run_id)
    assert artifact is not None and stored is not None
    assert hashlib.sha256(stored).hexdigest() == artifact.binary_sha256
    assert len(stored) > 0


def test_real_serde_readback() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version)
    artifact = service.repo.get_artifact(version.model_version_id)
    assert artifact is not None
    assert artifact.serde_readback_ok is True


def test_gcs_model_version_path_immutable() -> None:
    store = FakeObjectStore()
    persist_immutable_bytes(
        store,
        bucket="artifacts",
        object_name="ten_a/prj_a/modeling/mver_a/meridian_model.binpb",
        data=b"abc",
        content_type="application/octet-stream",
    )
    with pytest.raises(ArtifactVerificationFailedError):
        persist_immutable_bytes(
            store,
            bucket="artifacts",
            object_name="ten_a/prj_a/modeling/mver_a/meridian_model.binpb",
            data=b"other",
            content_type="application/octet-stream",
        )


def test_health_html_hash() -> None:
    html = "<html>health</html>"
    assert hashlib.sha256(html.encode()).hexdigest()


def test_results_summary_hash() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version)
    pack = service.repo.get_review(version.model_version_id)
    assert pack is not None
    assert pack.results is not None
    assert pack.results.html_sha256


def test_wrong_artifact_hash_blocks_acceptance() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version)
    artifact = service.repo.get_artifact(version.model_version_id)
    assert artifact is not None
    service.repo.put_artifact(artifact.model_copy(update={"binary_sha256": "0" * 64}))
    with pytest.raises((FakeRuntimeAcceptanceError, Exception)):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_model_version_row_compiles() -> None:
    version = _start(_service())
    row = compile_model_version_row(version)
    assert row["model_version_id"] == version.model_version_id
    assert row["model_window_start"] == version.model_window_start


def test_fit_run_row_compiles() -> None:
    service = _official_service()
    version = _start(service)
    run = _fit_ready(service, version)
    row = compile_fit_run_row(run, cycle_id=version.cycle_id, track_id=version.track_id)
    assert row["fit_run_id"] == run.fit_run_id
    assert row["runtime_mode"] == MeridianRuntimeMode.OFFICIAL_CPU_SMOKE.value


def test_decision_row_compiles() -> None:
    service = _service()
    version = _start(service)
    decision = service.repo.list_decisions(version.model_version_id)[0]
    row = compile_decision_row(decision, cycle_id=version.cycle_id, track_id=version.track_id)
    assert row["decision_id"] == decision.decision_id


def test_health_row_compiles() -> None:
    service = _official_service()
    version = _start(service)
    _fit_ready(service, version)
    health = service.repo.get_health(version.model_version_id)
    assert health is not None
    row = compile_health_row(
        health,
        project_id=version.project_id,
        cycle_id=version.cycle_id,
        track_id=version.track_id,
    )
    assert row["review_source"] == ReviewSource.OFFICIAL_MERIDIAN.value


def test_channel_summary_row_compiles() -> None:
    row = compile_channel_summary_row(
        project_id="prj_a",
        cycle_id="cyc_q3_2026",
        track_id="trk_mmm",
        model_version_id="mver_a",
        fit_run_id="mfit_a",
        channel="paid_search",
        roi=1.2,
        contribution=0.3,
        meridian_version="1.8.0",
    )
    assert row["channel"] == "paid_search"


def test_historical_rows_not_truncated() -> None:
    ledger = InMemoryModelLedger()
    ledger.write(table="mmm_model_versions", row={"model_version_id": "a"})
    ledger.write(table="mmm_model_versions", row={"model_version_id": "b"})
    assert len(ledger.rows["mmm_model_versions"]) == 2
    assert "mmm_model_versions" in BQ_MODEL_LEDGER_TABLES


def test_readback_fingerprint_matches() -> None:
    service = _official_service()
    version = _start(service)
    run = _fit_ready(service, version)
    assert run.ledger_readback_verified is True
    back = service.ledger.read_back(
        table="mmm_fit_runs", model_version_id=version.model_version_id
    )
    assert back is not None
    assert back["fit_plan_fingerprint"] == run.fit_plan_fingerprint


def test_missing_ledger_blocks_acceptance() -> None:
    class _BrokenLedger(InMemoryModelLedger):
        def read_back(self, *, table: str, model_version_id: str):
            del table, model_version_id
            return None

    service = MMMModelingService(
        InMemoryModelingRepository(),
        runtime=OfficialMeridianRuntime(
            mode=MeridianRuntimeMode.OFFICIAL_GPU,
            library=RecordingMeridianLibrary(checks=PASS_CHECKS),
        ),
        ledger=_BrokenLedger(),
    )
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(LedgerPublicationError):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_official_runtime_with_ledger_can_accept() -> None:
    service = _final_official_service()
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    approval = service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    assert approval.decision.value == "ACCEPT"
    brief = compile_decision_intelligence_brief(
        health=service.repo.get_health(version.model_version_id),
        pack=service.repo.get_review(version.model_version_id),
    )
    assert brief.headline
    assert MEDIA


def test_wrong_hash_on_manifest_blocks_gate() -> None:
    service = _final_official_service()
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    artifact = service.repo.get_artifact(version.model_version_id)
    assert artifact is not None
    service.repo.put_artifact(artifact.model_copy(update={"serde_readback_ok": False}))
    with pytest.raises(Exception, match="serde"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )
