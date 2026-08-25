"""M3-03B: pre-fit Meridian failure taxonomy and lifecycle truthfulness."""

from __future__ import annotations

import pytest

from app.modeling.common.errors import (
    ExactRetryNotAllowedError,
    FitApprovalRequiredError,
    ModelSpecIdentifiabilityError,
    SerdeError,
)
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitDispatchOutcome,
    FitDispatchStatus,
    FitFailureClass,
    FitFailureStage,
    FitNextActionType,
    FitPurpose,
    FitRunStatus,
    MeridianRuntimeMode,
    RetrySemantics,
)
from app.modeling.mmm.dispatch import FakeFitDispatcher
from app.modeling.mmm.failures import classify_failure, classify_fit_failure, offers_exact_retry
from app.modeling.mmm.identifiability import (
    IDENTIFIABILITY_ALTERNATIVES,
    prem3_identifiability_summary,
)
from app.modeling.mmm.ledger import compile_fit_run_row
from app.modeling.mmm.meridian.runner import (
    OfficialMeridianRuntime,
    RecordingMeridianLibrary,
    execute_approved_fit,
)
from app.modeling.mmm.service import MMMModelingService
from app.modeling.mmm.states import MMMModelingStage
from app.service.evaluation_jobs import FakeEvaluationJobLauncher
from app.service.mmm_models import FitNextActionView, FitRunResponse, to_fit_run_response
from app.tools.meridian_model_worker import execute_fit_dispatch
from tests.unit.test_mmm_modeling import (
    PASS_CHECKS,
    TEST_WORKER_DIGEST,
    _approve_required,
    _final_official_service,
    _start,
)

MUSIC_CENTER_IDENTIFIABILITY = (
    "The following non_media_treatments variables do not vary across geos, "
    "making a model with n_knots=n_time unidentifiable: [b'music_center_promo']."
)


class IdentifiabilityLibrary(RecordingMeridianLibrary):
    def construct_model(self, plan, mapping):
        del plan, mapping
        raise ValueError(MUSIC_CENTER_IDENTIFIABILITY)


def _identifiability_runtime() -> OfficialMeridianRuntime:
    return OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU,
        library=IdentifiabilityLibrary(checks=PASS_CHECKS),
        worker_image_digest=TEST_WORKER_DIGEST,
    )


def _approved_version(service: MMMModelingService, *, fit_purpose: FitPurpose):
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        n_draws=8,
    )
    service.approve_fit(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        fit_purpose=fit_purpose,
    )
    return version


def _run_identifiability_fit(service: MMMModelingService):
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    approval = service.repo.get_fit_approval(version.model_version_id)
    service.runtime = _identifiability_runtime()
    run = service.start_fit(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    current = service.get_version(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    return service, version, approval, run, current


def test_meridian_identifiability_value_error_classifies_pre_fit() -> None:
    classified = classify_fit_failure(ValueError(MUSIC_CENTER_IDENTIFIABILITY))
    assert classified.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR
    assert classified.status is FitRunStatus.FAILED_PRE_FIT
    assert classified.failure_stage is FitFailureStage.MODEL_INITIALIZATION
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    plan = service.repo.get_plan(version.model_version_id)
    fit_plan = service.repo.get_fit_plan(version.model_version_id)
    assert plan is not None and fit_plan is not None
    with pytest.raises(ModelSpecIdentifiabilityError) as raised:
        execute_approved_fit(
            _identifiability_runtime(),
            plan,
            fit_plan,
            expected_input_fingerprint=plan.model_ready_manifest_fingerprint,
        )
    assert raised.value.official_message == MUSIC_CENTER_IDENTIFIABILITY
    assert raised.value.exception_type == "ValueError"


def test_pre_fit_failure_is_not_serde_error() -> None:
    exc = ValueError(MUSIC_CENTER_IDENTIFIABILITY)
    assert classify_failure(exc) != "SERDE_ERROR"
    assert classify_failure(SerdeError("bad")) == "SERDE_ERROR"
    classified = classify_fit_failure(exc)
    assert classified.failure_class is not FitFailureClass.SERIALIZATION_ERROR
    assert not isinstance(classified.to_exception(), SerdeError)


def test_pre_fit_failure_marks_sampling_not_started() -> None:
    classified = classify_fit_failure(ValueError(MUSIC_CENTER_IDENTIFIABILITY))
    assert classified.sampling_started is False
    _service, _version, _approval, run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert run.sampling_started is False
    row = compile_fit_run_row(run, cycle_id="cyc_q3_2026", track_id="trk_mmm")
    assert row["sampling_started"] is False
    assert row["fit_status"] == FitRunStatus.FAILED_PRE_FIT.value
    assert row["failure_class"] == FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value


def test_pre_fit_failure_terminalizes_fit_run() -> None:
    _service, _version, _approval, run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert run.status is FitRunStatus.FAILED_PRE_FIT
    assert run.completed_at is not None
    assert run.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR
    assert run.library == "google-meridian"
    assert run.library_version == "1.8.0"
    assert run.exception_type == "ValueError"
    assert run.official_message == MUSIC_CENTER_IDENTIFIABILITY


def test_pre_fit_failure_routes_model_to_iteration_required() -> None:
    service, version, _approval, _run, current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert current.state is MMMModelingStage.ITERATION_REQUIRED
    decisions = service.repo.list_decisions(version.model_version_id)
    ident = [
        item
        for item in decisions
        if isinstance(item.proposal, dict) and item.proposal.get("kind") == "IDENTIFIABILITY"
    ]
    assert ident
    assert ident[0].chosen_value is None
    assert ident[0].status.value == "PENDING"
    alternatives = ident[0].proposal["alternatives"]
    assert [item["id"] for item in alternatives] == ["A", "B", "C"]
    assert alternatives == list(IDENTIFIABILITY_ALTERNATIVES)


def test_pre_fit_failure_does_not_offer_exact_retry() -> None:
    service, version, _approval, run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert run.retry_semantics is RetrySemantics.NEW_MODEL_DESIGN_REQUIRED
    assert FitNextActionType.REVIEW_MODEL_IDENTIFIABILITY.value in run.next_actions
    assert "RETRY_FIT" not in run.next_actions
    classified = classify_fit_failure(ValueError(MUSIC_CENTER_IDENTIFIABILITY))
    assert offers_exact_retry(classified) is False
    with pytest.raises(ExactRetryNotAllowedError):
        service.start_fit(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )


def test_changed_fit_plan_requires_new_approval() -> None:
    service, version, approval, _run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert approval is not None
    assert approval.superseded is False
    still = service.repo.get_fit_approval(version.model_version_id)
    assert still is not None
    assert still.approval_id == approval.approval_id
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="Resolve identifiability via a new Model Design decision.",
    )
    assert successor.model_version_id != version.model_version_id
    assert service.repo.get_fit_approval(successor.model_version_id) is None
    predecessor = service.repo.get_fit_approval(version.model_version_id)
    assert predecessor is not None
    assert predecessor.approval_id == approval.approval_id
    assert predecessor.superseded is False
    with pytest.raises(FitApprovalRequiredError):
        service.start_fit(
            tenant_id=successor.tenant_id,
            project_id=successor.project_id,
            model_version_id=successor.model_version_id,
        )


def test_failed_pre_fit_has_no_model_artifact() -> None:
    service, version, _approval, run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert service.repo.get_artifact(version.model_version_id) is None
    assert service.repo.get_binary(run.fit_run_id) is None


def test_failed_pre_fit_has_no_review_pack() -> None:
    service, version, _approval, _run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    assert service.repo.get_review(version.model_version_id) is None
    assert service.repo.get_health(version.model_version_id) is None
    assert service.repo.get_acceptance(version.model_version_id) is None


def test_dispatch_success_is_distinct_from_fit_failure() -> None:
    dispatcher = FakeFitDispatcher()
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    service.dispatcher = dispatcher
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    queued = service.start_fit(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    assert queued.status is FitRunStatus.QUEUED
    assert queued.dispatch_id
    dispatch = service.repo.get_dispatch(queued.dispatch_id)
    assert dispatch is not None
    launcher = FakeEvaluationJobLauncher()
    launched = service.launch_dispatch(dispatch.dispatch_id, launcher=launcher)
    assert launched.launch_outcome is FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
    assert launched.status is FitDispatchStatus.RUNNING
    runtime = _identifiability_runtime()
    payload = execute_fit_dispatch(
        dispatch_id=dispatch.dispatch_id,
        repo=service.repo,
        runtime=runtime,
        service=service,
    )
    assert payload["status"] == FitRunStatus.FAILED_PRE_FIT.value
    stored_dispatch = service.repo.get_dispatch(dispatch.dispatch_id)
    assert stored_dispatch is not None
    assert stored_dispatch.launch_outcome is FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
    assert stored_dispatch.status is FitDispatchStatus.COMPLETE
    assert stored_dispatch.status is not FitDispatchStatus.FAILED
    run = service.repo.get_fit_run(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        fit_run_id=queued.fit_run_id,
    )
    assert run is not None
    assert run.status is FitRunStatus.FAILED_PRE_FIT
    assert run.dispatch_outcome is FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
    current = service.get_version(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    assert current.state is MMMModelingStage.ITERATION_REQUIRED


def test_frontend_read_model_does_not_require_exception_parsing() -> None:
    body = FitRunResponse(
        fit_run_id="frun_x",
        model_version_id="mver_x",
        status=FitRunStatus.FAILED_PRE_FIT.value,
        fit_plan_fingerprint="fp",
        failure_class=FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value,
        failure_stage=FitFailureStage.MODEL_INITIALIZATION.value,
        sampling_started=False,
        retry_semantics=RetrySemantics.NEW_MODEL_DESIGN_REQUIRED.value,
        next_actions=[
            FitNextActionView(
                action_type=FitNextActionType.REVIEW_MODEL_IDENTIFIABILITY.value,
                statement="Review Model Design",
                owner="human",
                blocking=True,
            )
        ],
    )
    assert body.official_message is None
    assert body.failure_class == FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value
    assert body.sampling_started is False
    assert all(item.action_type != "RETRY_FIT" for item in body.next_actions)
    service, version, approval, run, _current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    read = to_fit_run_response(
        run,
        approval=approval,
        plan=service.repo.get_plan(version.model_version_id),
    )
    dumped = read.model_dump(mode="json")
    assert dumped["status"] == FitRunStatus.FAILED_PRE_FIT.value
    assert dumped["failure_class"] == FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value
    assert dumped["failure_stage"] == FitFailureStage.MODEL_INITIALIZATION.value
    assert dumped["sampling_started"] is False
    assert dumped["retry_semantics"] == RetrySemantics.NEW_MODEL_DESIGN_REQUIRED.value
    assert dumped["next_actions"][0]["action_type"] == (
        FitNextActionType.REVIEW_MODEL_IDENTIFIABILITY.value
    )
    assert "RETRY_FIT" not in {item["action_type"] for item in dumped["next_actions"]}
    assert dumped["prem3_summary"] == prem3_identifiability_summary(MUSIC_CENTER_IDENTIFIABILITY)
    assert dumped["evidence"]["fit_approval_id"] == approval.approval_id
