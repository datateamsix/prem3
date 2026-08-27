"""P6-04 accepted-model authority. MODEL_READY is not MODEL_ACCEPTED."""

from __future__ import annotations

from app.investment_optimization.accepted_model import (
    INELIGIBLE_STAGES,
    is_accepted_model,
    select_accepted_model,
)
from app.investment_optimization.consumption import (
    bind_projection_to_accepted_model,
    compile_model_consumption_contract,
    validate_consumption_contract,
)
from app.investment_optimization.enums import OptimizationIssueCode
from app.modeling.mmm.states import MMMModelingStage
from tests.unit.investment_optimization.p6_04_support import (
    MODEL_ID,
    PROJECT,
    TENANT,
    complete_contract,
    model_version,
)


def test_no_accepted_model_not_ready() -> None:
    selection = select_accepted_model(
        (), tenant_id=TENANT, project_id=PROJECT, requested_model_version_id=None
    )
    assert selection.version is None
    assert selection.issue_code is OptimizationIssueCode.NO_ACCEPTED_MODEL


def test_model_ready_not_equivalent_model_accepted() -> None:
    version = model_version(state=MMMModelingStage.MODEL_READY, accepted=False)
    assert is_accepted_model(version) is False
    selection = select_accepted_model(
        (version,), tenant_id=TENANT, project_id=PROJECT, requested_model_version_id=None
    )
    assert selection.issue_code is OptimizationIssueCode.NO_ACCEPTED_MODEL


def test_failed_model_not_eligible() -> None:
    version = model_version(state=MMMModelingStage.FAILED, accepted=False)
    assert version.state in INELIGIBLE_STAGES
    assert is_accepted_model(version) is False


def test_iteration_required_not_eligible() -> None:
    version = model_version(state=MMMModelingStage.ITERATION_REQUIRED, accepted=False)
    assert is_accepted_model(version) is False


def test_explicit_accepted_model_eligible_for_mapping() -> None:
    version = model_version()
    assert is_accepted_model(version) is True
    selection = select_accepted_model(
        (version,), tenant_id=TENANT, project_id=PROJECT, requested_model_version_id=MODEL_ID
    )
    assert selection.version is version
    assert selection.issue_code is None


def test_multiple_accepted_models_require_selection_or_policy() -> None:
    first = model_version()
    second = model_version(model_version_id="mver_bbbbbbbbbbbbbbbbbbbb")
    selection = select_accepted_model(
        (first, second), tenant_id=TENANT, project_id=PROJECT, requested_model_version_id=None
    )
    assert selection.issue_code is OptimizationIssueCode.MULTIPLE_ACCEPTED_MODELS
    chosen = select_accepted_model(
        (first, second),
        tenant_id=TENANT,
        project_id=PROJECT,
        requested_model_version_id=second.model_version_id,
    )
    assert chosen.version is second


def test_model_consumption_contract_required() -> None:
    incomplete = complete_contract(optimizer_artifact_ref=None, response_evidence_ref=None)
    incomplete = validate_consumption_contract(
        incomplete.model_copy(update={"currency": "", "complete": True})
    )
    assert incomplete.complete is False
    assert any(
        issue.code is OptimizationIssueCode.MODEL_CONSUMPTION_CONTRACT_INCOMPLETE
        for issue in incomplete.issues
    )


def test_optimizer_artifact_required() -> None:
    contract = complete_contract(optimizer_artifact_ref=None, response_evidence_ref=None)
    assert any(
        issue.code is OptimizationIssueCode.OPTIMIZER_INPUT_ARTIFACT_MISSING
        for issue in contract.issues
    )


def test_missing_response_evidence_not_ready() -> None:
    contract = complete_contract(optimizer_artifact_ref=None, response_evidence_ref=None)
    assert contract.complete is False


def test_runtime_version_pinned() -> None:
    contract = complete_contract(meridian_version="0.0.0")
    assert any(
        issue.code is OptimizationIssueCode.MODEL_RUNTIME_INCOMPATIBLE for issue in contract.issues
    )


def test_compile_does_not_infer_canonical_channel_from_names() -> None:
    version = model_version()
    from app.modeling.mmm.contracts import MeridianModelSpecProposal, ModelPlan

    plan = ModelPlan(
        model_plan_id="mplan_aaaaaaaaaaaaaaaaaaa",
        model_version_id=version.model_version_id,
        model_ready_run_id=version.model_ready_run_id,
        model_ready_manifest_fingerprint=version.model_ready_manifest_fingerprint,
        meridian_version=version.meridian_version,
        model_window_start="2024-01-01",
        model_window_end="2026-12-31",
        scope="NATIONAL",
        spec=MeridianModelSpecProposal(),
        fingerprint="fp_plan",
        media_channels=("google_search_spend",),
    )
    compiled = compile_model_consumption_contract(
        version=version,
        plan=plan,
        acceptance=None,
        artifact=None,
        response_evidence_ref=None,
        currency="USD",
        kpi="revenue",
        runtime_mode="OFFICIAL_MERIDIAN_RUNTIME",
    )
    assert compiled.variables[0].canonical_channel_id is None
    assert compiled.variables[0].model_variable_name == "google_search_spend"


def test_planning_projection_cannot_diverge_from_accepted_mmm() -> None:
    version = model_version()
    matching = bind_projection_to_accepted_model(complete_contract(), version)
    assert matching.complete is True
    diverged = complete_contract()
    diverged = diverged.model_copy(update={"model_plan_fingerprint": "fp_other_plan"})
    stale = bind_projection_to_accepted_model(diverged, version)
    assert stale.complete is False
    assert any(
        issue.code is OptimizationIssueCode.MODEL_CONSUMPTION_PROJECTION_STALE
        for issue in stale.issues
    )
    ineligible = bind_projection_to_accepted_model(
        complete_contract(),
        model_version(state=MMMModelingStage.MODEL_READY, accepted=False),
    )
    assert ineligible.complete is False
    assert any(
        issue.code is OptimizationIssueCode.NO_ACCEPTED_MODEL for issue in ineligible.issues
    )
