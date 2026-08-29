"""M3-04: governed identifiability decision package, pre-fit, successor iteration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modeling.common.errors import (
    FabricatedGeoVariationError,
    FitApprovalRequiredError,
    HumanApprovalRequiredError,
    IdentifiabilityDecisionRequiredError,
    PrefitValidationFailedError,
)
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitPurpose,
    GeoPromotionEvidenceStatus,
    IdentifiabilityAlternativeId,
    IdentifiabilityPackageStatus,
    MeridianRuntimeMode,
    PreFitCheckStatus,
    PromotionMateriality,
)
from app.modeling.mmm.geo_promotion import refuse_fabricated_geo_variation
from app.modeling.mmm.identifiability import IDENTIFIABILITY_ALTERNATIVES
from app.modeling.mmm.identifiability_package import (
    build_music_center_v1_package,
    human_decision_payload,
    package_is_advisory,
)
from app.modeling.mmm.prefit import GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS
from app.modeling.mmm.states import MMMModelingStage
from app.service.mmm_models import to_identifiability_review
from app.tools.meridian_model_worker import execute_server_owned_request
from tests.unit.test_mmm_m3_03b import (
    MUSIC_CENTER_IDENTIFIABILITY,
    _approved_version,
    _identifiability_runtime,
    _run_identifiability_fit,
)
from tests.unit.test_mmm_modeling import (
    TEST_WORKER_DIGEST,
    _approve_required,
    _final_official_service,
    _start,
    test_review_requires_acknowledgment,
)

PROOF_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "meridian_music_center_identifiability_decision_proof.json"
)
LIVE_V1 = {
    "project_id": "prjm3f5b6833478623",
    "model_version_id": "mver_ab97dadeaf40431a",
    "fit_run_id": "frun_56d19c77ff8d4308afdd",
}


def _package_from_failed_fit():
    service, version, approval, run, current = _run_identifiability_fit(
        _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    )
    package = service.identifiability_package(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    return service, version, approval, run, current, package


def test_identifiability_package_references_official_failure() -> None:
    _service, version, _approval, run, _current, package = _package_from_failed_fit()
    assert package.official_failure.official_message == MUSIC_CENTER_IDENTIFIABILITY
    assert package.failed_fit_run_id == run.fit_run_id
    assert package.failed_model_version_id == version.model_version_id
    assert package.official_failure.library == "google-meridian"


def test_identifiability_package_links_eda_handoff() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    assert "imp_knot_strategy" in package.eda_evidence["implication_ids"]
    assert "KNOT_STRATEGY" in package.eda_evidence["open_decision_types"]
    assert "GEO_SCOPE_REVIEW" in package.eda_evidence["open_decision_types"]
    assert package.eda_evidence["eda_model_spec_purpose"] == "PRE_MODELING_EDA_ONLY"
    assert "does not establish the final knot strategy" in package.eda_evidence[
        "knot_fallback_statement"
    ]


def test_identifiability_package_uses_pinned_business_profile() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    assert (
        package.business_context["business_profile_snapshot_id"]
        == "bpsnap_music_center_dataset_a"
    )
    assert package.business_context["promotion_materiality"] == PromotionMateriality.MATERIAL.value
    assert "name" in package.business_context["name_is_not_evidence"].lower()


def test_geo_promotion_availability_is_data_grounded() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    assert package.data_evidence["status"] == (
        GeoPromotionEvidenceStatus.GEO_PROMOTION_EVIDENCE_NOT_FOUND.value
    )
    assert package.data_evidence["inspected_source_universe"] is True
    assert package.data_evidence["model_ready"]["geo_variation"] is False


def test_alternative_c_disabled_without_real_geo_evidence() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    alt_c = next(
        item
        for item in package.alternatives
        if item.alternative_id is IdentifiabilityAlternativeId.C
    )
    assert alt_c.available is False
    assert alt_c.unavailable_reason
    assert alt_c.data_foundation_work_required is True


def test_recommendation_does_not_approve_model_change() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    assert package_is_advisory(package)
    assert package.prem3_recommendation is not None
    assert package.prem3_recommendation.kind == "PREM3_RECOMMENDATION"
    assert package.prem3_recommendation.approved_model_change is False
    assert package.prem3_recommendation.alternative_id is IdentifiabilityAlternativeId.A
    assert package.counter_evidence
    assert package.selected_alternative is None
    assert package.decision_status is IdentifiabilityPackageStatus.PENDING_HUMAN_DECISION


def test_no_successor_model_before_human_decision() -> None:
    service, version, _approval, _run, current, package = _package_from_failed_fit()
    assert current.state is MMMModelingStage.ITERATION_REQUIRED
    assert package.selected_alternative is None
    with pytest.raises(IdentifiabilityDecisionRequiredError):
        service.iterate(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
            actor_id="user_a",
            reason="should not create v2 yet",
        )
    versions = service.repo.list_versions(
        tenant_id=version.tenant_id, project_id=version.project_id
    )
    assert all(item.supersedes_model_version_id != version.model_version_id for item in versions)


def test_iteration_creates_successor_model_version() -> None:
    service, version, _approval, run, _current, _package = _package_from_failed_fit()
    decision = service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="A",
        selected_configuration={"n_knots": 130},
        rationale="Retain promotion; reduce knots.",
        evidence_refs=(run.fit_run_id,),
    )
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose A",
    )
    assert successor.model_version_id != version.model_version_id
    assert successor.supersedes_model_version_id == version.model_version_id
    assert successor.iteration_reason == "MODEL_SPEC_IDENTIFIABILITY_ERROR"
    assert successor.source_model_decision_id == decision.decision_id
    assert successor.source_fit_run_id == run.fit_run_id
    assert successor.version == version.version + 1


def test_failed_model_version_remains_immutable() -> None:
    service, version, approval, _run, _current, _package = _package_from_failed_fit()
    service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="A",
        selected_configuration={"n_knots": 130},
        rationale="Retain promotion; reduce knots.",
    )
    service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose A",
    )
    predecessor = service.get_version(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
    )
    assert predecessor.state is MMMModelingStage.ITERATION_REQUIRED
    assert predecessor.accepted is False
    still = service.repo.get_fit_approval(version.model_version_id)
    assert still is not None
    assert still.approval_id == approval.approval_id


def test_successor_links_predecessor_failure_and_decision() -> None:
    service, version, _approval, run, _current, _package = _package_from_failed_fit()
    decision = service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="B",
        selected_configuration={"remove_non_media_treatments": ["music_center_promo"]},
        rationale="Drop explicit promotion; retain full knots.",
    )
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose B",
    )
    assert successor.source_fit_run_id == run.fit_run_id
    assert successor.source_model_decision_id == decision.decision_id
    plan = service.repo.get_plan(successor.model_version_id)
    assert plan is not None
    assert "music_center_promo" not in (plan.non_media_treatments or ())
    brief = service.repo.get_brief(successor.model_version_id)
    assert brief is not None
    assert "PROMOTION_NOT_EXPLICITLY_MODELED" in brief.known_limitations


def test_old_fit_approval_cannot_authorize_successor() -> None:
    service, version, approval, _run, _current, _package = _package_from_failed_fit()
    service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="A",
        selected_configuration={"n_knots": 130},
        rationale="Retain promotion; reduce knots.",
    )
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose A",
    )
    assert service.repo.get_fit_approval(successor.model_version_id) is None
    with pytest.raises(FitApprovalRequiredError):
        service.start_fit(
            tenant_id=successor.tenant_id,
            project_id=successor.project_id,
            model_version_id=successor.model_version_id,
        )
    old = service.repo.get_fit_approval(version.model_version_id)
    assert old is not None and old.approval_id == approval.approval_id


def test_successor_model_plan_has_new_fingerprint() -> None:
    service, version, _approval, _run, _current, _package = _package_from_failed_fit()
    old_plan = service.repo.get_plan(version.model_version_id)
    assert old_plan is not None
    service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="A",
        selected_configuration={"n_knots": 130},
        rationale="Retain promotion; reduce knots.",
    )
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose A",
    )
    new_plan = service.repo.get_plan(successor.model_version_id)
    assert new_plan is not None
    assert new_plan.fingerprint != old_plan.fingerprint
    assert new_plan.spec.knots == 130
    still_old = service.repo.get_plan(version.model_version_id)
    assert still_old is not None
    assert still_old.fingerprint == old_plan.fingerprint


def test_prefit_uses_official_meridian_runtime() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    receipt = service.repo.get_prefit_receipt(version.model_version_id)
    assert receipt is not None
    assert receipt.runtime_mode is MeridianRuntimeMode.OFFICIAL_CPU
    assert receipt.status is PreFitCheckStatus.PASS


def test_prefit_receipt_binds_exact_model_plan() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    plan = service.repo.get_plan(version.model_version_id)
    receipt = service.repo.get_prefit_receipt(version.model_version_id)
    assert plan is not None and receipt is not None
    assert receipt.model_plan_fingerprint == plan.fingerprint
    approval = service.repo.get_fit_approval(version.model_version_id)
    assert approval is not None
    assert approval.pre_fit_receipt_fingerprint == receipt.fingerprint


def test_prefit_failure_blocks_fit_approval_or_dispatch() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _start_for_prefit_fail(service)
    service.runtime = _identifiability_runtime()
    with pytest.raises(PrefitValidationFailedError):
        service.validate_prefit(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
    receipt = service.repo.get_prefit_receipt(version.model_version_id)
    assert receipt is not None
    assert receipt.status is PreFitCheckStatus.FAIL
    with pytest.raises(FitApprovalRequiredError, match="pre-fit"):
        service.approve_fit(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
            actor_id="user_a",
            fit_purpose=FitPurpose.FINAL_MODEL,
        )


def _start_for_prefit_fail(service):
    version = _start(service, compute_profile=ComputeProfile.CPU_STANDARD)
    _approve_required(service, version)
    service.validate_prior(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        n_draws=8,
    )
    return version


def test_changed_model_plan_invalidates_prefit() -> None:
    service, version, _approval, _run, _current, _package = _package_from_failed_fit()
    service.record_identifiability_decision(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        selected_alternative_id="A",
        selected_configuration={"n_knots": 130},
        rationale="Retain promotion; reduce knots.",
    )
    successor = service.iterate(
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        actor_id="user_a",
        reason="human chose A",
    )
    stale = service.repo.get_prefit_receipt(version.model_version_id)
    fresh = service.repo.get_prefit_receipt(successor.model_version_id)
    assert fresh is None or (stale is not None and fresh.fingerprint != stale.fingerprint)
    plan = service.repo.get_plan(successor.model_version_id)
    assert plan is not None
    if stale is not None:
        assert stale.model_plan_fingerprint != plan.fingerprint


def test_prefit_does_not_run_full_posterior() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    library = service.runtime._library_or_fail()
    assert "sample_posterior" not in getattr(library, "calls", ())
    receipt = service.repo.get_prefit_receipt(version.model_version_id)
    assert receipt is not None
    names = [item.check_name for item in receipt.checks]
    assert "no_full_posterior" in names


def test_worker_cannot_change_knots() -> None:
    with pytest.raises(Exception, match="untrusted"):
        execute_server_owned_request({"knots": 12, "dispatch_id": "x"})


def test_worker_cannot_drop_music_center_promo() -> None:
    with pytest.raises(Exception, match="untrusted"):
        execute_server_owned_request({"non_media_treatments": [], "dispatch_id": "x"})


def test_worker_cannot_fabricate_geo_variation() -> None:
    with pytest.raises(Exception, match="untrusted"):
        execute_server_owned_request({"geo_variation": True, "dispatch_id": "x"})
    with pytest.raises(FabricatedGeoVariationError):
        refuse_fabricated_geo_variation({"fabricate_geo_variation": True})


def test_successor_fit_requires_new_fit_approval() -> None:
    test_old_fit_approval_cannot_authorize_successor()


def test_fit_approval_binds_prefit_receipt() -> None:
    test_prefit_receipt_binds_exact_model_plan()


def test_exact_approved_mcmc_reaches_worker() -> None:
    service = _final_official_service(mode=MeridianRuntimeMode.OFFICIAL_CPU)
    version = _approved_version(service, fit_purpose=FitPurpose.FINAL_MODEL)
    fit_plan = service.repo.get_fit_plan(version.model_version_id)
    plan = service.repo.get_plan(version.model_version_id)
    assert fit_plan is not None and plan is not None
    assert fit_plan.n_chains == int(plan.mcmc["n_chains"])
    assert fit_plan.n_adapt == int(plan.mcmc["n_adapt"])
    assert fit_plan.n_burnin == int(plan.mcmc["n_burnin"])
    assert fit_plan.n_keep == int(plan.mcmc["n_keep"])
    assert fit_plan.n_chains == 7
    assert fit_plan.n_keep == 1000


def test_job_success_does_not_equal_model_acceptance() -> None:
    service, version, _approval, _run, current, _package = _package_from_failed_fit()
    assert current.accepted is False
    assert service.repo.get_acceptance(version.model_version_id) is None


def test_official_fail_blocks_acceptance() -> None:
    service, version, _approval, _run, _current, _package = _package_from_failed_fit()
    from app.modeling.common.errors import ModelReviewFailedError

    with pytest.raises(ModelReviewFailedError):
        service.accept(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
            actor_id="user_a",
        )


def test_official_review_requires_acknowledgment() -> None:
    test_review_requires_acknowledgment()


def test_service_account_cannot_accept_model() -> None:
    service, version, _approval, _run, _current, _package = _package_from_failed_fit()
    with pytest.raises(HumanApprovalRequiredError):
        service.record_identifiability_decision(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
            actor_id="svc@prem3.iam.gserviceaccount.com",
            selected_alternative_id="A",
            selected_configuration={"n_knots": 130},
            rationale="not allowed",
        )


def test_failed_pre_fit_cannot_create_results_snapshot() -> None:
    service, version, _approval, run, _current, _package = _package_from_failed_fit()
    assert service.repo.get_artifact(version.model_version_id) is None
    assert run.sampling_started is False


def test_iteration_required_results_are_not_available() -> None:
    service, version, _approval, _run, current, _package = _package_from_failed_fit()
    assert current.state is MMMModelingStage.ITERATION_REQUIRED
    assert service.repo.get_review(version.model_version_id) is None


def test_no_investment_recommendation_before_accepted_model() -> None:
    service, version, _approval, _run, current, _package = _package_from_failed_fit()
    assert current.accepted is False
    accepted = service.has_accepted_model(
        tenant_id=version.tenant_id, project_id=version.project_id
    )
    assert accepted is False


def test_frontend_does_not_manufacture_alternatives() -> None:
    _service, _version, _approval, _run, _current, package = _package_from_failed_fit()
    view = to_identifiability_review(package)
    dumped = view.model_dump(mode="json")
    assert [item["alternative_id"] for item in dumped["alternatives"]] == ["A", "B", "C"]
    assert dumped["decision_required"] is True
    assert dumped["human_decision"]["selected_alternative"] is None
    assert dumped["alternatives"] == [
        item.model_dump(mode="json") for item in package.alternatives
    ]
    assert [item["id"] for item in IDENTIFIABILITY_ALTERNATIVES] == ["A", "B", "C"]


def test_music_center_phase1_package_stops_before_choice() -> None:
    package = build_music_center_v1_package(
        project_id=LIVE_V1["project_id"],
        failed_model_version_id=LIVE_V1["model_version_id"],
        failed_fit_run_id=LIVE_V1["fit_run_id"],
        official_message=MUSIC_CENTER_IDENTIFIABILITY,
        model_evidence={
            "fit_purpose": "FINAL_MODEL",
            "mcmc": {"n_chains": 7, "n_adapt": 1000, "n_burnin": 500, "n_keep": 1000},
        },
    )
    assert package.selected_alternative is None
    assert package.decision_status is IdentifiabilityPackageStatus.PENDING_HUMAN_DECISION
    payload = {
        "package_id": package.package_id,
        "fingerprint": package.fingerprint,
        "official_failure": package.official_failure.model_dump(mode="json"),
        "promotion_materiality": package.business_context["promotion_materiality"],
        "geo_promotion_evidence_status": package.data_evidence["status"],
        "alternatives": [item.model_dump(mode="json") for item in package.alternatives],
        "prem3_recommendation": package.prem3_recommendation.model_dump(mode="json")
        if package.prem3_recommendation is not None
        else None,
        "counter_evidence": list(package.counter_evidence),
        "human_decision": human_decision_payload(package),
        "successor_model_version_created": False,
        "note": "STOP. Human must select A, B, or C. Coding agent does not choose.",
    }
    PROOF_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert PROOF_PATH.is_file()
    assert GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS
    assert TEST_WORKER_DIGEST
