"""Mission 3 Meridian modeling runtime tests. No GitHub fetch. No generated Python."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.modeling.common.errors import (
    ExternalAssetDisabledError,
    FakeRuntimeAcceptanceError,
    FitApprovalRequiredError,
    FitRuntimeError,
    IllegalModelingTransitionError,
    InputContractMismatchError,
    ModelReviewFailedError,
    ModelSpecInvalidError,
    ModelVersionNotFoundError,
    StaleApprovalError,
)
from app.modeling.common.external_assets import (
    PINNED_RUNTIME_VERSION,
    PINNED_UPSTREAM_COMMIT,
    SNAPSHOT_ROOT,
    git_blob_sha,
    listed_assets,
    load_manifest,
    manifest_sha256,
    require_enabled_asset,
    verify_vendored_blob,
)
from app.modeling.mmm.compatibility import generate_compatibility_report
from app.modeling.mmm.compiler import compile_meridian_model_spec
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitPurpose,
    MeridianModelSpecProposal,
    MeridianRuntimeMode,
    OfficialCheckResult,
    OfficialHealthStatus,
    PriorSource,
)
from app.modeling.mmm.design import REQUIRED_DECISION_TYPES, proposed_model_plan
from app.modeling.mmm.doc_consultant import consult_topic
from app.modeling.mmm.ledger import BQ_MODEL_LEDGER_TABLES, InMemoryModelLedger
from app.modeling.mmm.meridian.builder import assert_not_eda_spec
from app.modeling.mmm.meridian.runner import (
    FakeMeridianRuntime,
    FitExecutionResult,
    OfficialMeridianRuntime,
    RecordingMeridianLibrary,
)
from app.modeling.mmm.provenance import AllowlistedSourceHistory
from app.modeling.mmm.receipts import receipt_cannot_mutate_plan, reproducibility_manifest
from app.modeling.mmm.repository import InMemoryModelingRepository
from app.modeling.mmm.service import MMMModelingService
from app.modeling.mmm.states import MMMModelingStage, assert_legal_modeling_transition
from app.tools.meridian_model_worker import execute_server_owned_request
from tests.unit.api_support import auth_header, make_client, seed_tenant

MUSIC_CENTER_FP = "mc-q3-2026-model-ready-fingerprint"
MUSIC_CENTER_WINDOW = ("2024-01-01", "2026-06-29")
MEDIA = ("paid_search", "paid_social", "video")
PASS_CHECKS = (
    OfficialCheckResult(
        check_name="ConvergenceCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
    OfficialCheckResult(
        check_name="BaselineCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
    OfficialCheckResult(
        check_name="BayesianPPPCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
    OfficialCheckResult(
        check_name="GoodnessOfFitCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
    OfficialCheckResult(
        check_name="PriorPosteriorShiftCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
    OfficialCheckResult(
        check_name="ROIConsistencyCheck",
        status=OfficialHealthStatus.PASS,
        summary="ok",
    ),
)


TEST_SOURCE_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TEST_WORKER_DIGEST = "sha256:committed-test-worker"
TEST_HISTORY = AllowlistedSourceHistory(frozenset({TEST_SOURCE_SHA}))


class ScriptedRuntime(FakeMeridianRuntime):
    def __init__(self, checks: tuple[OfficialCheckResult, ...]) -> None:
        self.checks = checks

    def sample_posterior(self, plan, fit_plan) -> FitExecutionResult:
        result = super().sample_posterior(plan, fit_plan)
        return FitExecutionResult(
            binary=result.binary,
            binary_sha256=result.binary_sha256,
            health_checks=self.checks,
            results_html=result.results_html,
            structured=result.structured,
            python_version=result.python_version,
            tensorflow_version=result.tensorflow_version,
            meridian_version=result.meridian_version,
            worker_image_digest=result.worker_image_digest,
            runtime_mode=result.runtime_mode,
            review_source=result.review_source,
            calls_made=result.calls_made,
            serde_readback_ok=result.serde_readback_ok,
            health_html=result.health_html,
            results_html_sha256=result.results_html_sha256,
        )


def _official_service(
    checks: tuple[OfficialCheckResult, ...] | None = None,
    *,
    mode: MeridianRuntimeMode = MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
) -> MMMModelingService:
    library = RecordingMeridianLibrary(checks=checks or PASS_CHECKS)
    return MMMModelingService(
        InMemoryModelingRepository(),
        runtime=OfficialMeridianRuntime(mode=mode, library=library),
        worker_image_digest=TEST_WORKER_DIGEST,
        source_commit_sha=TEST_SOURCE_SHA,
        worker_build_id="build-test",
        source_history=TEST_HISTORY,
    )


def _final_official_service(
    checks: tuple[OfficialCheckResult, ...] | None = None,
    *,
    mode: MeridianRuntimeMode = MeridianRuntimeMode.OFFICIAL_GPU,
) -> MMMModelingService:
    return _official_service(checks, mode=mode)


def _service(runtime=None) -> MMMModelingService:
    return MMMModelingService(InMemoryModelingRepository(), runtime=runtime)


def _start(service: MMMModelingService, **overrides):
    payload = {
        "tenant_id": "ten_a",
        "project_id": "prj_a",
        "cycle_id": "cyc_q3_2026",
        "track_id": "trk_mmm",
        "actor_id": "user_a",
        "model_ready_run_id": "run_mr",
        "model_ready_manifest_fingerprint": MUSIC_CENTER_FP,
        "model_ready_manifest_ref": "gs://prem3/model-ready.json",
        "business_profile_snapshot_id": "bprof_music",
        "model_window_start": MUSIC_CENTER_WINDOW[0],
        "model_window_end": MUSIC_CENTER_WINDOW[1],
        "scope": "GEO",
        "media_channels": MEDIA,
        "compute_profile": ComputeProfile.CPU_TEST,
    }
    payload.update(overrides)
    return service.start_design(**payload)


def _approve_required(service: MMMModelingService, version) -> None:
    required = set(item.value for item in REQUIRED_DECISION_TYPES)
    plan = service.repo.get_plan(version.model_version_id)
    if plan is not None and plan.rf_channels:
        required.add("RF_PRIOR_TYPE")
    for decision in service.repo.list_decisions(version.model_version_id):
        if decision.decision_type.value in required:
            service.approve_decision(
                tenant_id=version.tenant_id,
                project_id=version.project_id,
                decision_id=decision.decision_id,
                actor_id="user_a",
            )


def _fit_ready(service: MMMModelingService, version, *, fit_purpose=None):
    _approve_required(service, version)
    service.validate_prior(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        n_draws=8,
    )
    if fit_purpose is FitPurpose.FINAL_MODEL:
        service.validate_prefit(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
    service.approve_fit(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        fit_purpose=fit_purpose,
    )
    return service.start_fit(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )


def test_external_assets_are_pinned_and_licensed() -> None:
    manifest = load_manifest()
    assert manifest["upstream_commit_sha"] == PINNED_UPSTREAM_COMMIT
    assert manifest["runtime_meridian_version"] == PINNED_RUNTIME_VERSION
    assert manifest["license"] == "Apache-2.0"
    assert manifest["fetched_from_github_at_runtime"] is False
    license_path = SNAPSHOT_ROOT / "LICENSE"
    assert license_path.is_file()
    assert git_blob_sha(license_path.read_bytes()) == manifest["license_blob_sha"]
    assert manifest_sha256()
    skills = [item for item in listed_assets() if item.asset_type == "SKILL"]
    assert {item.asset_id for item in skills} == {
        "meridian.skill.doc_consultant",
        "meridian.skill.model_building",
        "meridian.skill.result_visualization",
        "meridian.skill.budget_optimization",
        "meridian.skill.scenario_planner",
    }
    for asset in listed_assets():
        if asset.asset_type == "DEMO_NOTEBOOK":
            continue
        verify_vendored_blob(asset.upstream_path, asset.upstream_blob_sha)


def test_vendored_skill_blob_sha_matches_snapshot() -> None:
    skill = require_enabled_asset("meridian.skill.model_building")
    verify_vendored_blob(skill.upstream_path, skill.upstream_blob_sha)


def test_disabled_asset_cannot_be_used() -> None:
    with pytest.raises(ExternalAssetDisabledError):
        require_enabled_asset("meridian.skill.budget_optimization")


def test_new_upstream_version_is_a_new_snapshot_directory() -> None:
    other = SNAPSHOT_ROOT.parent / ("0" * 40)
    assert SNAPSHOT_ROOT.name == PINNED_UPSTREAM_COMMIT
    assert not other.exists()


def test_compatibility_report_catches_media_effects_dist_roi() -> None:
    report = generate_compatibility_report()
    names = {item.name: item for item in report.checks}
    assert names["media_effects_dist_rejects_roi"].class_name == "INCOMPATIBLE"
    assert names["media_prior_type_values"].class_name == "COMPATIBLE"
    assert names["budget_optimizer_reference_only"].class_name == "REFERENCE_ONLY"
    assert names["doc_consultant_missing_public_docs_tree"].class_name == (
        "COMPATIBLE_WITH_ADAPTATION"
    )
    assert report.compatible is True
    assert report.runtime_meridian_version == "1.8.0"
    assert "UPSTREAM_UNRELEASED" in " ".join(report.warnings)


def test_compiler_rejects_roi_on_media_effects_dist() -> None:
    plan = proposed_model_plan(
        model_plan_id="mplan_x",
        model_version_id="mver_x",
        model_ready_run_id="run_x",
        model_ready_manifest_fingerprint=MUSIC_CENTER_FP,
        business_profile_snapshot_id=None,
        model_window_start=MUSIC_CENTER_WINDOW[0],
        model_window_end=MUSIC_CENTER_WINDOW[1],
        scope="NATIONAL",
        media_channels=MEDIA,
        rf_channels=(),
    )
    broken = plan.model_copy(
        update={"spec": MeridianModelSpecProposal(media_effects_dist="roi")}
    )
    with pytest.raises(ModelSpecInvalidError, match="media_effects_dist"):
        compile_meridian_model_spec(plan=broken)


def test_compiler_rejects_knots_with_aks() -> None:
    plan = proposed_model_plan(
        model_plan_id="mplan_x",
        model_version_id="mver_x",
        model_ready_run_id="run_x",
        model_ready_manifest_fingerprint=MUSIC_CENTER_FP,
        business_profile_snapshot_id=None,
        model_window_start=MUSIC_CENTER_WINDOW[0],
        model_window_end=MUSIC_CENTER_WINDOW[1],
        scope="GEO",
        media_channels=MEDIA,
        rf_channels=(),
    )
    broken = plan.model_copy(
        update={"spec": MeridianModelSpecProposal(knots=4, enable_aks=True)}
    )
    with pytest.raises(ModelSpecInvalidError, match="mutually exclusive"):
        compile_meridian_model_spec(plan=broken)


def test_eda_spec_cannot_be_promoted() -> None:
    with pytest.raises(InputContractMismatchError):
        assert_not_eda_spec({"purpose": "PRE_MODELING_EDA_ONLY"})
    service = _service()
    with pytest.raises(InputContractMismatchError):
        _start(service, eda_context={"approved_for_final_modeling": True})


def test_music_center_geo_design_and_national_and_rf() -> None:
    service = _service()
    geo = _start(service)
    assert geo.state is MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS
    brief = service.repo.get_brief(geo.model_version_id)
    assert brief is not None
    assert "2024-01-01/2026-06-29" == brief.final_model_window
    assert all(section.recommendation.requires_approval for section in brief.sections)
    national = _start(
        service, project_id="prj_nat", scope="NATIONAL", media_channels=("search",)
    )
    assert service.repo.get_plan(national.model_version_id).scope == "NATIONAL"
    rf = _start(
        service,
        project_id="prj_rf",
        rf_channels=("youtube_rf",),
        media_channels=("paid_search",),
    )
    types = {item.decision_type.value for item in service.repo.list_decisions(rf.model_version_id)}
    assert "RF_PRIOR_TYPE" in types


def test_experiment_and_ambiguous_and_insufficient_control_decisions() -> None:
    service = _service()
    version = _start(
        service,
        include_experiment_prior=True,
        include_ambiguous_promotion=True,
        include_insufficient_controls=True,
    )
    types = {
        item.decision_type.value: item
        for item in service.repo.list_decisions(version.model_version_id)
    }
    assert types["CUSTOM_PRIOR"].proposal["source"] == "EXPERIMENT"
    assert types["TREATMENT_CLASSIFICATION"].proposal["promotion"] == "UNRESOLVED"
    assert types["CONTROL_SELECTION"].proposal["status"] == "INSUFFICIENT_EVIDENCE"


def test_unapproved_fit_cannot_run() -> None:
    service = _service()
    version = _start(service)
    with pytest.raises(FitApprovalRequiredError):
        service.start_fit(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
        )


def test_stale_and_changed_plan_and_fingerprint_invalidate_approval() -> None:
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
    service.repo.put_plan(plan.model_copy(update={"fingerprint": "changed-plan"}))
    with pytest.raises(StaleApprovalError):
        service.start_fit(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
        )
    service.repo.put_plan(plan)
    with pytest.raises(StaleApprovalError):
        service.start_fit(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            expected_input_fingerprint="other-fp",
        )


def test_cross_project_and_wrong_version_rejected() -> None:
    service = _service()
    version = _start(service)
    with pytest.raises(ModelVersionNotFoundError):
        service.get_version(
            tenant_id="ten_a", project_id="prj_b", model_version_id=version.model_version_id
        )
    with pytest.raises(ModelVersionNotFoundError):
        service.approve_decision(
            tenant_id="ten_b",
            project_id="prj_a",
            decision_id="mdec_missing",
            actor_id="user_b",
        )


def test_duplicate_fit_approval_is_idempotent() -> None:
    service = _service()
    version = _start(service)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    first = service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    second = service.approve_fit(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    assert first.approval_id == second.approval_id
    run_a = service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    run_b = service.start_fit(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    assert run_a.fit_run_id == run_b.fit_run_id


def test_cpu_smoke_serde_and_artifact_integrity() -> None:
    service = _service()
    version = _start(service)
    run = _fit_ready(service, version)
    artifact = service.repo.get_artifact(version.model_version_id)
    assert artifact is not None
    stored = service.repo.get_binary(run.fit_run_id)
    assert stored is not None
    assert json.loads(stored.decode())["format"] == "prem3-fake-meridian-binpb"
    assert hashlib.sha256(stored).hexdigest() == artifact.binary_sha256
    current = service.get_version(
        tenant_id="ten_a", project_id="prj_a", model_version_id=version.model_version_id
    )
    assert current.state is MMMModelingStage.AWAITING_MODEL_REVIEW
    with pytest.raises(FakeRuntimeAcceptanceError):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def _failing(check: str, status: OfficialHealthStatus) -> ScriptedRuntime:
    checks = (
        OfficialCheckResult(
            check_name="ConvergenceCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
        OfficialCheckResult(
            check_name="BaselineCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
        OfficialCheckResult(
            check_name="BayesianPPPCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
        OfficialCheckResult(
            check_name="GoodnessOfFitCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
        OfficialCheckResult(
            check_name="PriorPosteriorShiftCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
        OfficialCheckResult(
            check_name="ROIConsistencyCheck",
            status=OfficialHealthStatus.PASS,
            summary="ok",
        ),
    )
    updated = tuple(
        OfficialCheckResult(check_name=item.check_name, status=status, summary="scripted")
        if item.check_name == check
        else item
        for item in checks
    )
    return ScriptedRuntime(updated)


def test_convergence_fail_blocks_acceptance() -> None:
    service = _final_official_service(
        _failing("ConvergenceCheck", OfficialHealthStatus.FAIL).checks
    )
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(ModelReviewFailedError, match="Convergence FAIL"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_official_fail_blocks_acceptance() -> None:
    service = _final_official_service(
        _failing("BaselineCheck", OfficialHealthStatus.FAIL).checks
    )
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(ModelReviewFailedError, match="Official FAIL"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_review_requires_acknowledgment() -> None:
    service = _final_official_service(
        _failing("ROIConsistencyCheck", OfficialHealthStatus.REVIEW).checks
    )
    version = _start(service, compute_profile=ComputeProfile.GPU_STANDARD)
    _fit_ready(service, version, fit_purpose=FitPurpose.FINAL_MODEL)
    with pytest.raises(ModelReviewFailedError, match="REVIEW"):
        service.accept(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )
    service.acknowledge_review(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        items=("ROIConsistencyCheck",),
    )
    approval = service.accept(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
    )
    assert approval.decision.value == "ACCEPT"


def test_iteration_creates_new_version_and_keeps_old_artifact() -> None:
    service = _service()
    version = _start(service)
    _fit_ready(service, version)
    old = service.repo.get_artifact(version.model_version_id)
    successor = service.iterate(
        tenant_id="ten_a",
        project_id="prj_a",
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="Review requested knot change.",
    )
    assert successor.model_version_id != version.model_version_id
    assert successor.supersedes_model_version_id == version.model_version_id
    assert successor.version == 2
    still = service.repo.get_artifact(version.model_version_id)
    assert still is not None and old is not None
    assert still.binary_sha256 == old.binary_sha256
    with pytest.raises(FitApprovalRequiredError):
        service.start_fit(
            tenant_id="ten_a",
            project_id="prj_a",
            model_version_id=successor.model_version_id,
        )


def test_tenancy_isolation_on_fit_plan_and_binary() -> None:
    service = _service()
    version = _start(service)
    _fit_ready(service, version)
    run = service.repo.list_fit_runs(version.model_version_id)[0]
    assert (
        service.repo.get_fit_run(
            tenant_id="ten_b", project_id="prj_a", fit_run_id=run.fit_run_id
        )
        is None
    )
    assert service.repo.get_version(
        tenant_id="ten_a", project_id="prj_b", model_version_id=version.model_version_id
    ) is None


def test_worker_rejects_generated_python_and_restores_server_plan() -> None:
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
    fit_plan = service.repo.get_fit_plan(version.model_version_id)
    assert plan is not None and fit_plan is not None
    with pytest.raises(FitRuntimeError, match="untrusted"):
        execute_server_owned_request({"python": "print(1)", "tenant_id": "ten_a"})
    with pytest.raises(FitRuntimeError, match="dispatch_id"):
        execute_server_owned_request(
            {
                "tenant_id": "ten_a",
                "project_id": "prj_a",
                "cycle_id": "cyc_q3_2026",
                "track_id": "trk_mmm",
                "model_version_id": version.model_version_id,
                "fit_run_id": "mfit_worker",
                "model_plan": plan.model_dump(mode="json"),
                "fit_plan": fit_plan.model_dump(mode="json"),
                "input_fingerprint": MUSIC_CENTER_FP,
                "compute_profile": "CPU_TEST",
            }
        )


def test_doc_consultant_does_not_invent_numeric_defaults() -> None:
    unknown = consult_topic("made-up-topic")
    assert unknown.available is False
    knots = consult_topic("knots")
    assert knots.source_kind.value == "PINNED_REPO_SOURCE"
    assert "do not invent" not in knots.recommendation.lower() or knots.available


def test_mel_receipt_cannot_mutate_plan() -> None:
    service = _service()
    version = _start(service)
    from app.modeling.mmm.receipts import design_receipt

    brief = service.repo.get_brief(version.model_version_id)
    assert brief is not None
    receipt = design_receipt(version, brief)
    assert receipt_cannot_mutate_plan(receipt) is True
    pack = reproducibility_manifest(
        version=version,
        decision_ids=tuple(
            item.decision_id
            for item in service.repo.list_decisions(version.model_version_id)
        ),
        fit_plan=None,
        artifact=None,
        review=None,
        acceptance=None,
    )
    assert pack.model_ready_manifest_fingerprint == MUSIC_CENTER_FP


def test_model_ledger_tables_are_versioned_and_not_binary_store() -> None:
    ledger = InMemoryModelLedger()
    row = ledger.write(
        table="mmm_model_versions",
        row={"model_version_id": "mver_1", "state": "MODEL_ACCEPTED"},
    )
    assert row["model_version_id"] == "mver_1"
    assert "mmm_model_versions" in BQ_MODEL_LEDGER_TABLES
    assert "meridian_model.binpb" not in BQ_MODEL_LEDGER_TABLES


def test_legal_transitions_include_iteration_and_acceptance() -> None:
    assert_legal_modeling_transition(
        MMMModelingStage.AWAITING_MODEL_REVIEW, MMMModelingStage.MODEL_ACCEPTED
    )
    assert_legal_modeling_transition(
        MMMModelingStage.AWAITING_MODEL_REVIEW, MMMModelingStage.ITERATING_MODEL
    )
    assert_legal_modeling_transition(
        MMMModelingStage.FITTING_MODEL, MMMModelingStage.ITERATION_REQUIRED
    )
    assert_legal_modeling_transition(
        MMMModelingStage.AWAITING_FIT_APPROVAL, MMMModelingStage.ITERATION_REQUIRED
    )
    with pytest.raises(IllegalModelingTransitionError):
        assert_legal_modeling_transition(
            MMMModelingStage.MODEL_ACCEPTED, MMMModelingStage.FITTING_MODEL
        )


def test_priors_are_serializable_not_python_objects() -> None:
    service = _service()
    version = _start(service)
    plan = service.repo.get_plan(version.model_version_id)
    assert plan is not None
    assert plan.priors[0].source is PriorSource.MERIDIAN_DEFAULT
    dumped = plan.priors[0].model_dump(mode="json")
    assert "distribution_family" in dumped
    assert not hasattr(plan.priors[0], "dist")


def test_mmm_api_music_center_design_requires_paid_feature() -> None:
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post(
        "/v1/projects",
        headers=auth_header(),
        json={"name": "Music Center", "scope_type": "BRAND"},
    ).json()
    project_id = created["project_id"]
    response = client.post(
        f"/v1/projects/{project_id}/cycles/cyc_q3_2026/mmm/model-design",
        headers=auth_header(),
        json={
            "model_ready_run_id": "run_mr",
            "model_ready_manifest_fingerprint": MUSIC_CENTER_FP,
            "model_window_start": MUSIC_CENTER_WINDOW[0],
            "model_window_end": MUSIC_CENTER_WINDOW[1],
            "scope": "GEO",
            "media_channels": list(MEDIA),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"]["state"] == "AWAITING_ASSUMPTION_DECISIONS"
    summary = client.get(
        f"/v1/projects/{project_id}/cycles/cyc_q3_2026/mmm",
        headers=auth_header(),
    )
    assert summary.status_code == 200
    assert summary.json()["model_version_id"] == body["version"]["model_version_id"]
