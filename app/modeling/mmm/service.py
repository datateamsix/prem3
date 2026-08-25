"""Governed MMM modeling service. Agent proposes; humans approve; worker executes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.control_plane.ids import (
    new_approval_id,
    new_fit_dispatch_id,
    new_fit_run_id,
    new_model_plan_id,
    new_model_version_id,
)
from app.core.contracts import utc_now
from app.eda.extended_contracts import EDAModelDesignHandoff
from app.modeling.common.errors import (
    ArtifactVerificationFailedError,
    ExactRetryNotAllowedError,
    FakeRuntimeAcceptanceError,
    FitApprovalRequiredError,
    GcsPersistenceError,
    HumanApprovalRequiredError,
    IdentifiabilityDecisionRequiredError,
    InputContractMismatchError,
    LedgerPublicationError,
    ModelReviewFailedError,
    ModelSpecInvalidError,
    ModelVersionImmutableError,
    ModelVersionNotFoundError,
    PrefitValidationFailedError,
    QualificationAcceptanceError,
    ResourceExhaustedError,
    StaleApprovalError,
)
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.artifacts import (
    ARTIFACT_MANIFEST_NAME,
    CANONICAL_MODEL_BINARY_NAME,
    HEALTH_HTML_NAME,
    REPRODUCIBILITY_NAME,
    RESULTS_HTML_NAME,
    REVIEW_PACK_NAME,
    modeling_prefix,
    persist_immutable_bytes,
)
from app.modeling.mmm.compiler import compile_fit_plan_payload, compile_meridian_model_spec
from app.modeling.mmm.contracts import (
    PRODUCTION_OFFICIAL_RUNTIME_MODES,
    AcceptanceDecision,
    ComputeProfile,
    DataFoundationWorkRequest,
    DecisionStatus,
    DecisionType,
    FitApproval,
    FitDispatchOutcome,
    FitDispatchStatus,
    FitFailureClass,
    FitFailureStage,
    FitPurpose,
    FitRun,
    FitRunStatus,
    IdentifiabilityAlternativeId,
    IdentifiabilityPackageStatus,
    LedgerPublicationStatus,
    MeridianFitDispatch,
    MeridianFitPlan,
    MeridianModelArtifactManifest,
    MeridianPriorValidationReceipt,
    MeridianRuntimeMode,
    MMMIdentifiabilityDecisionPackage,
    MMMModelVersion,
    ModelAcceptanceApproval,
    ModelDecision,
    ModelReadyCoverage,
    OfficialHealthStatus,
    PreFitCheckStatus,
    PriorValidationStatus,
    ReviewSource,
)
from app.modeling.mmm.coverage import (
    MUSIC_CENTER_MODEL_READY_COVERAGE,
    assert_cycle_does_not_define_window,
    assert_model_window_inside_coverage,
    assert_window_change_invalidates_approval,
)
from app.modeling.mmm.dataset_a import MUSIC_CENTER_FINAL_FINGERPRINTS
from app.modeling.mmm.design import (
    REQUIRED_DECISION_TYPES,
    build_design_brief,
    initial_decisions,
    proposed_model_plan,
)
from app.modeling.mmm.failures import (
    ACTIVE_FIT_STATUSES,
    TERMINAL_FIT_STATUSES,
    classify_fit_failure,
)
from app.modeling.mmm.geo_promotion import refuse_fabricated_geo_variation
from app.modeling.mmm.identifiability import identifiability_decision
from app.modeling.mmm.identifiability_package import (
    build_identifiability_package,
    build_music_center_v1_package,
    package_is_advisory,
)
from app.modeling.mmm.iteration import (
    ITERATION_REASON_IDENTIFIABILITY,
    PROMOTION_NOT_EXPLICITLY_MODELED,
    compile_successor_model_plan,
    selected_alternative,
)
from app.modeling.mmm.ledger import InMemoryModelLedger, ModelLedger, publish_fit_ledger
from app.modeling.mmm.meridian.reviewer import interpret_reviewer_results
from app.modeling.mmm.meridian.runner import (
    FakeMeridianRuntime,
    MeridianRuntime,
    execute_approved_fit,
    execute_prior_validation,
    runtime_mode_for_profile,
)
from app.modeling.mmm.meridian.summarizer import structured_results
from app.modeling.mmm.prefit import execute_prefit_validation, prefit_blocks_final_model
from app.modeling.mmm.provenance import (
    SourceHistory,
    assert_final_model_provenance,
    resolve_source_commit_sha,
    resolve_worker_build_id,
)
from app.modeling.mmm.repository import InMemoryModelingRepository, ModelingRepository
from app.modeling.mmm.review import assemble_review_pack
from app.modeling.mmm.states import (
    MMMModelingStage,
    assert_legal_modeling_transition,
)

MAX_CONCURRENT_FITS_PER_PROJECT = 1
MAX_CONCURRENT_FITS_PER_TENANT = 2


def _is_service_account_actor(actor_id: str) -> bool:
    value = actor_id.strip().lower()
    return value.endswith(".gserviceaccount.com") or value.startswith("serviceaccount:")


class MMMModelingService:
    def __init__(
        self,
        repo: ModelingRepository | None = None,
        *,
        runtime: MeridianRuntime | None = None,
        ledger: ModelLedger | None = None,
        dispatcher: object | None = None,
        object_store: object | None = None,
        artifact_bucket: str | None = None,
        worker_image_digest: str | None = None,
        source_commit_sha: str | None = None,
        worker_build_id: str | None = None,
        source_history: SourceHistory | None = None,
    ) -> None:
        self.repo = repo or InMemoryModelingRepository()
        self.runtime = runtime or FakeMeridianRuntime()
        self.ledger = ledger or InMemoryModelLedger()
        self.dispatcher = dispatcher
        self.object_store = object_store
        self.artifact_bucket = artifact_bucket
        self.worker_image_digest = worker_image_digest
        self.source_commit_sha = source_commit_sha
        self.worker_build_id = worker_build_id
        self.source_history = source_history
        self._lock = Lock()

    def start_design(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        actor_id: str,
        model_ready_run_id: str,
        model_ready_manifest_fingerprint: str,
        model_ready_manifest_ref: str | None = None,
        business_profile_snapshot_id: str | None = None,
        model_window_start: str,
        model_window_end: str,
        scope: str,
        kpi: str = "revenue",
        media_channels: tuple[str, ...] = (),
        rf_channels: tuple[str, ...] = (),
        compute_profile: ComputeProfile = ComputeProfile.CPU_TEST,
        include_ambiguous_promotion: bool = False,
        include_insufficient_controls: bool = False,
        include_experiment_prior: bool = False,
        eda_context: dict[str, Any] | None = None,
        coverage: ModelReadyCoverage | None = None,
        cycle_window_start: str | None = None,
        cycle_window_end: str | None = None,
        eda_handoff: EDAModelDesignHandoff | None = None,
    ) -> MMMModelVersion:
        if eda_context and eda_context.get("approved_for_final_modeling") is True:
            raise InputContractMismatchError("EDA spec cannot be approved for final modeling.")
        if not model_ready_manifest_fingerprint:
            raise InputContractMismatchError("MODEL_READY manifest fingerprint is required.")
        assert_cycle_does_not_define_window(
            cycle_start=cycle_window_start,
            cycle_end=cycle_window_end,
            model_window_start=model_window_start,
            model_window_end=model_window_end,
            coverage=coverage,
        )
        if coverage is not None:
            assert_model_window_inside_coverage(
                model_window_start=model_window_start,
                model_window_end=model_window_end,
                coverage=coverage,
            )
        version = MMMModelVersion(
            model_version_id=new_model_version_id(),
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            model_ready_run_id=model_ready_run_id,
            model_ready_manifest_ref=model_ready_manifest_ref,
            model_ready_manifest_fingerprint=model_ready_manifest_fingerprint,
            business_profile_snapshot_id=business_profile_snapshot_id,
            meridian_version=PINNED_RUNTIME_VERSION,
            state=MMMModelingStage.DESIGNING_MODEL,
            created_by=actor_id,
            model_window_start=model_window_start,
            model_window_end=model_window_end,
        )
        plan = proposed_model_plan(
            model_plan_id=new_model_plan_id(),
            model_version_id=version.model_version_id,
            model_ready_run_id=model_ready_run_id,
            model_ready_manifest_fingerprint=model_ready_manifest_fingerprint,
            business_profile_snapshot_id=business_profile_snapshot_id,
            model_window_start=model_window_start,
            model_window_end=model_window_end,
            scope=scope,
            media_channels=media_channels,
            rf_channels=rf_channels,
            compute_profile=compute_profile,
        )
        brief = build_design_brief(
            model_version_id=version.model_version_id,
            model_window_start=model_window_start,
            model_window_end=model_window_end,
            scope=scope,
            kpi=kpi,
            media_channels=media_channels,
            rf_channels=rf_channels,
            evidence_refs=(model_ready_run_id, model_ready_manifest_fingerprint),
            coverage=coverage,
            eda_handoff=eda_handoff,
        )
        version = version.model_copy(
            update={
                "model_plan_id": plan.model_plan_id,
                "model_plan_fingerprint": plan.fingerprint,
                "state": MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS,
            }
        )
        self.repo.put_version(version)
        self.repo.put_plan(plan)
        self.repo.put_brief(brief)
        for decision in initial_decisions(
            tenant_id=tenant_id,
            project_id=project_id,
            model_version_id=version.model_version_id,
            plan=plan,
            include_rf=bool(rf_channels),
            include_ambiguous_promotion=include_ambiguous_promotion,
            include_insufficient_controls=include_insufficient_controls,
            include_experiment_prior=include_experiment_prior,
        ):
            self.repo.put_decision(decision)
        return version

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion:
        version = self.repo.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if version is None:
            raise ModelVersionNotFoundError("Model version was not found.")
        return version

    def current_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> MMMModelVersion | None:
        items = self.repo.list_versions(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )
        return items[0] if items else None

    def has_accepted_model(self, *, tenant_id: str, project_id: str) -> bool:
        return any(
            item.accepted
            for item in self.repo.list_versions(tenant_id=tenant_id, project_id=project_id)
        )

    def _require_mutable(self, version: MMMModelVersion) -> None:
        if version.accepted or version.state is MMMModelingStage.MODEL_ACCEPTED:
            raise ModelVersionImmutableError("Accepted model versions cannot mutate.")
        if version.state is MMMModelingStage.ITERATION_REQUIRED:
            raise ModelVersionImmutableError(
                "Current specification cannot proceed. A model-design decision is required."
            )

    def _transition(self, version: MMMModelVersion, nxt: MMMModelingStage) -> MMMModelVersion:
        assert_legal_modeling_transition(version.state, nxt)
        updated = version.model_copy(update={"state": nxt})
        return self.repo.put_version(updated)

    def approve_decision(
        self,
        *,
        tenant_id: str,
        project_id: str,
        decision_id: str,
        actor_id: str,
        chosen_value: Any = None,
    ):
        decision = self.repo.get_decision(
            tenant_id=tenant_id, project_id=project_id, decision_id=decision_id
        )
        if decision is None:
            raise ModelVersionNotFoundError("Decision was not found.")
        version = self.get_version(
            tenant_id=tenant_id,
            project_id=project_id,
            model_version_id=decision.model_version_id,
        )
        self._require_mutable(version)
        plan = self.repo.get_plan(version.model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        if decision.plan_fingerprint and decision.plan_fingerprint != plan.fingerprint:
            raise StaleApprovalError("Decision is bound to a stale ModelPlan.")
        if decision.status is DecisionStatus.APPROVED and (
            chosen_value is None or chosen_value == decision.chosen_value
        ):
            return decision
        updated = decision.model_copy(
            update={
                "status": DecisionStatus.APPROVED,
                "chosen_value": decision.proposal if chosen_value is None else chosen_value,
                "approved_by": actor_id,
                "approved_at": utc_now(),
            }
        )
        stored = self.repo.put_decision(updated)
        self._maybe_configure(version)
        return stored

    def reject_decision(
        self, *, tenant_id: str, project_id: str, decision_id: str, actor_id: str
    ):
        decision = self.repo.get_decision(
            tenant_id=tenant_id, project_id=project_id, decision_id=decision_id
        )
        if decision is None:
            raise ModelVersionNotFoundError("Decision was not found.")
        version = self.get_version(
            tenant_id=tenant_id,
            project_id=project_id,
            model_version_id=decision.model_version_id,
        )
        self._require_mutable(version)
        updated = decision.model_copy(
            update={
                "status": DecisionStatus.REJECTED,
                "approved_by": actor_id,
                "approved_at": utc_now(),
            }
        )
        return self.repo.put_decision(updated)

    def _required_types(self, version: MMMModelVersion) -> tuple[DecisionType, ...]:
        plan = self.repo.get_plan(version.model_version_id)
        types = list(REQUIRED_DECISION_TYPES)
        if plan is not None and plan.rf_channels:
            types.append(DecisionType.RF_PRIOR_TYPE)
        return tuple(types)

    def _maybe_configure(self, version: MMMModelVersion) -> None:
        decisions = self.repo.list_decisions(version.model_version_id)
        required = self._required_types(version)
        by_type = {item.decision_type: item for item in decisions}
        if any(
            by_type.get(item) is None or by_type[item].status is not DecisionStatus.APPROVED
            for item in required
        ):
            return
        if version.state is MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS:
            self._transition(version, MMMModelingStage.CONFIGURING_MODEL)

    def validate_prior(
        self, *, tenant_id: str, project_id: str, model_version_id: str, n_draws: int = 32
    ) -> MeridianPriorValidationReceipt:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self._require_mutable(version)
        if version.state is MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS:
            self._maybe_configure(version)
            version = self.get_version(
                tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
            )
        if version.state is MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS:
            raise ModelSpecInvalidError(
                "Required model decisions must be approved before prior validation."
            )
        if version.state is MMMModelingStage.CONFIGURING_MODEL:
            version = self._transition(version, MMMModelingStage.PRIOR_VALIDATION)
        plan = self.repo.get_plan(model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        compile_meridian_model_spec(plan=plan)
        result = execute_prior_validation(
            self.runtime, plan, n_draws=n_draws, seed=int(plan.mcmc.get("seed", 1))
        )
        receipt = MeridianPriorValidationReceipt(
            model_version_id=model_version_id,
            model_plan_fingerprint=plan.fingerprint,
            meridian_version=PINNED_RUNTIME_VERSION,
            prior_config_fingerprint=canonical_fingerprint(
                [item.model_dump(mode="json") for item in plan.priors]
            ),
            n_draws=result.n_draws,
            seed=result.seed,
            status=result.status,
            runtime_mode=getattr(self.runtime, "runtime_mode", MeridianRuntimeMode.FAKE_TEST),
            warnings=result.warnings,
        )
        self.repo.put_prior_receipt(receipt)
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if version.state is MMMModelingStage.PRIOR_VALIDATION:
            version = self._transition(version, MMMModelingStage.READY_TO_FIT)
            self._transition(version, MMMModelingStage.AWAITING_FIT_APPROVAL)
        return receipt

    def compile_fit_plan(
        self,
        version: MMMModelVersion,
        *,
        fit_purpose: FitPurpose | None = None,
    ) -> MeridianFitPlan:
        plan = self.repo.get_plan(version.model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        purpose = fit_purpose or (
            FitPurpose.RUNTIME_QUALIFICATION
            if plan.compute_profile is ComputeProfile.CPU_TEST
            else FitPurpose.MODEL_ITERATION
        )
        source_sha = resolve_source_commit_sha(configured=self.source_commit_sha)
        build_id = resolve_worker_build_id(configured=self.worker_build_id)
        if purpose is FitPurpose.FINAL_MODEL:
            assert_final_model_provenance(
                source_commit_sha=source_sha,
                worker_image_digest=self.worker_image_digest,
                history=self.source_history,
            )
        payload = compile_fit_plan_payload(
            plan,
            fit_purpose=purpose,
            container_image_digest=self.worker_image_digest,
            source_commit_sha=source_sha,
            worker_build_id=build_id,
        )
        prefit = self.repo.get_prefit_receipt(version.model_version_id)
        prefit_fp = None if prefit is None else prefit.fingerprint
        if prefit_fp is not None:
            payload["pre_fit_receipt_fingerprint"] = prefit_fp
        schedule = payload.get("n_chains_schedule")
        fit_plan = MeridianFitPlan(
            model_version_id=version.model_version_id,
            model_plan_fingerprint=plan.fingerprint,
            meridian_version=PINNED_RUNTIME_VERSION,
            container_image_digest=self.worker_image_digest,
            source_commit_sha=source_sha,
            worker_build_id=build_id,
            n_chains=payload["n_chains"],
            n_adapt=payload["n_adapt"],
            n_burnin=payload["n_burnin"],
            n_keep=payload["n_keep"],
            seed=payload["seed"],
            n_chains_schedule=None if schedule is None else tuple(schedule),
            compute_profile=plan.compute_profile,
            fit_purpose=purpose,
            input_fingerprint=plan.model_ready_manifest_fingerprint,
            pre_fit_receipt_fingerprint=prefit_fp,
            fingerprint=canonical_fingerprint(payload),
        )
        return self.repo.put_fit_plan(fit_plan)

    def approve_fit(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
        actor_id: str,
        fit_purpose: FitPurpose | None = None,
    ) -> FitApproval:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self._require_mutable(version)
        prior = self.repo.get_prior_receipt(model_version_id)
        if prior is None or prior.status is not PriorValidationStatus.PASS:
            raise FitApprovalRequiredError("Final prior validation must pass before fit approval.")
        plan = self.repo.get_plan(model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        purpose = fit_purpose or (
            FitPurpose.RUNTIME_QUALIFICATION
            if plan.compute_profile is ComputeProfile.CPU_TEST
            else FitPurpose.MODEL_ITERATION
        )
        prefit = self.repo.get_prefit_receipt(model_version_id)
        if purpose is FitPurpose.FINAL_MODEL:
            if prefit_blocks_final_model(prefit):
                raise FitApprovalRequiredError(
                    "Official pre-fit validation must PASS before FINAL_MODEL."
                )
            assert prefit is not None
            if prefit.model_plan_fingerprint != plan.fingerprint:
                raise StaleApprovalError("Changed ModelPlan invalidates pre-fit validation.")
        existing = self.repo.get_fit_approval(model_version_id)
        fit_plan = self.compile_fit_plan(version, fit_purpose=purpose)
        prior_fp = canonical_fingerprint(
            {
                "model_plan_fingerprint": prior.model_plan_fingerprint,
                "prior_config_fingerprint": prior.prior_config_fingerprint,
                "status": prior.status.value,
            }
        )
        prefit_fp = None if prefit is None else prefit.fingerprint
        if (
            existing is not None
            and not existing.superseded
            and existing.fit_plan_fingerprint == fit_plan.fingerprint
            and existing.model_plan_fingerprint == plan.fingerprint
            and existing.pre_fit_receipt_fingerprint == prefit_fp
        ):
            return existing
        approval = FitApproval(
            approval_id=new_approval_id(),
            model_version_id=model_version_id,
            tenant_id=tenant_id,
            project_id=project_id,
            fit_plan_fingerprint=fit_plan.fingerprint,
            model_plan_fingerprint=plan.fingerprint,
            prior_validation_fingerprint=prior_fp,
            pre_fit_receipt_fingerprint=prefit_fp,
            approved_by=actor_id,
            approved_at=utc_now(),
        )
        return self.repo.put_fit_approval(approval)

    def _count_running(self, *, tenant_id: str, project_id: str | None = None) -> int:
        return len(self.repo.list_running_fits(tenant_id=tenant_id, project_id=project_id))

    def start_fit(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
        expected_input_fingerprint: str | None = None,
    ) -> FitRun:
        with self._lock:
            version = self.get_version(
                tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
            )
            plan = self.repo.get_plan(model_version_id)
            fit_plan = self.repo.get_fit_plan(model_version_id)
            approval = self.repo.get_fit_approval(model_version_id)
            if version.state is MMMModelingStage.ITERATION_REQUIRED:
                raise ExactRetryNotAllowedError(
                    "This FitPlan cannot be retried. A new model-design decision is required."
                )
            if plan is None or fit_plan is None:
                raise FitApprovalRequiredError("Fit plan has not been compiled.")
            if any(
                item.fit_plan_fingerprint == fit_plan.fingerprint
                and item.status is FitRunStatus.FAILED_PRE_FIT
                for item in self.repo.list_fit_runs(model_version_id)
            ):
                raise ExactRetryNotAllowedError(
                    "This FitPlan cannot be retried. A new model-design decision is required."
                )
            self._require_mutable(version)
            if approval is None or approval.superseded:
                raise FitApprovalRequiredError("Fit cannot run without an exact human approval.")
            if (
                expected_input_fingerprint
                and expected_input_fingerprint != plan.model_ready_manifest_fingerprint
            ):
                raise StaleApprovalError(
                    "Changed model-ready fingerprint invalidates approval."
                )
            if approval.fit_plan_fingerprint != fit_plan.fingerprint:
                raise StaleApprovalError("Stale fit approval cannot run.")
            if approval.model_plan_fingerprint != plan.fingerprint:
                raise StaleApprovalError("Changed ModelPlan invalidates fit approval.")
            if fit_plan.fit_purpose is FitPurpose.FINAL_MODEL:
                prefit = self.repo.get_prefit_receipt(model_version_id)
                if prefit_blocks_final_model(prefit):
                    raise FitApprovalRequiredError(
                        "Official pre-fit validation must PASS before FINAL_MODEL."
                    )
                assert prefit is not None
                if prefit.model_plan_fingerprint != plan.fingerprint:
                    raise StaleApprovalError("Changed ModelPlan invalidates pre-fit validation.")
                if (
                    approval.pre_fit_receipt_fingerprint
                    and approval.pre_fit_receipt_fingerprint != prefit.fingerprint
                ):
                    raise StaleApprovalError(
                        "Fit approval is not bound to the current pre-fit receipt."
                    )
            assert_window_change_invalidates_approval(plan=plan, approval=approval)
            if approval.tenant_id != tenant_id or approval.project_id != project_id:
                raise StaleApprovalError("Cross-project fit approval rejected.")
            existing = [
                item
                for item in self.repo.list_fit_runs(model_version_id)
                if item.fit_plan_fingerprint == fit_plan.fingerprint
                and item.status in ACTIVE_FIT_STATUSES
            ]
            if existing:
                return existing[0]
            if (
                self._count_running(tenant_id=tenant_id, project_id=project_id)
                >= MAX_CONCURRENT_FITS_PER_PROJECT
            ):
                raise ResourceExhaustedError("Max concurrent fits for this Project.")
            if self._count_running(tenant_id=tenant_id) >= MAX_CONCURRENT_FITS_PER_TENANT:
                raise ResourceExhaustedError("Max concurrent fits for this tenant.")
            if self.dispatcher is not None:
                runtime_mode = runtime_mode_for_profile(
                    fit_plan.compute_profile.value, official=True
                )
            else:
                runtime_mode = getattr(
                    self.runtime, "runtime_mode", MeridianRuntimeMode.FAKE_TEST
                )
            run = FitRun(
                fit_run_id=new_fit_run_id(),
                model_version_id=model_version_id,
                tenant_id=tenant_id,
                project_id=project_id,
                fit_plan_fingerprint=fit_plan.fingerprint,
                status=FitRunStatus.RUNNING,
                compute_profile=fit_plan.compute_profile,
                runtime_mode=runtime_mode,
                fit_purpose=fit_plan.fit_purpose,
                meridian_version=PINNED_RUNTIME_VERSION,
                worker_image_digest=fit_plan.container_image_digest,
                source_commit_sha=fit_plan.source_commit_sha,
                worker_build_id=fit_plan.worker_build_id,
                started_at=utc_now(),
            )
            self.repo.put_fit_run(run)
            if version.state is MMMModelingStage.AWAITING_FIT_APPROVAL:
                version = self._transition(version, MMMModelingStage.FITTING_MODEL)
            if self.dispatcher is not None:
                return self._dispatch_fit(version, plan, fit_plan, run, approval)
        return self._execute_fit(version, plan, fit_plan, run)

    def _dispatch_fit(self, version, plan, fit_plan, run: FitRun, approval: FitApproval) -> FitRun:
        del plan
        mode = runtime_mode_for_profile(fit_plan.compute_profile.value, official=True)
        dispatch = MeridianFitDispatch(
            dispatch_id=new_fit_dispatch_id(),
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            cycle_id=version.cycle_id,
            track_id=version.track_id,
            model_version_id=version.model_version_id,
            fit_run_id=run.fit_run_id,
            fit_plan_fingerprint=fit_plan.fingerprint,
            fit_approval_id=approval.approval_id,
            runtime_mode=mode,
            compute_profile=fit_plan.compute_profile,
            status=FitDispatchStatus.QUEUED,
        )
        canonical = self.repo.claim_canonical_dispatch(dispatch)
        if canonical.dispatch_id != dispatch.dispatch_id:
            existing = self.repo.get_fit_run(
                tenant_id=version.tenant_id,
                project_id=version.project_id,
                fit_run_id=canonical.fit_run_id,
            )
            if existing is not None:
                return existing
        task_name = self.dispatcher.enqueue(canonical)
        stored = canonical.model_copy(
            update={
                "cloud_task_name": task_name,
                "status": FitDispatchStatus.QUEUED,
                "updated_at": utc_now(),
            }
        )
        self.repo.put_dispatch(stored)
        pending = run.model_copy(
            update={"dispatch_id": stored.dispatch_id, "status": FitRunStatus.QUEUED}
        )
        self.repo.put_fit_run(pending)
        return pending

    def launch_dispatch(self, dispatch_id: str, *, launcher) -> MeridianFitDispatch:
        dispatch = self.repo.get_dispatch(dispatch_id)
        if dispatch is None:
            raise ModelVersionNotFoundError("Fit dispatch was not found.")
        approval = self.repo.get_fit_approval(dispatch.model_version_id)
        fit_plan = self.repo.get_fit_plan(dispatch.model_version_id)
        if approval is None or approval.superseded:
            raise FitApprovalRequiredError(
                "Fit cannot launch without an exact human approval."
            )
        if fit_plan is None:
            raise FitApprovalRequiredError("Fit plan has not been compiled.")
        if fit_plan.fingerprint != dispatch.fit_plan_fingerprint:
            raise StaleApprovalError("Dispatch FitPlan fingerprint does not match.")
        if approval.fit_plan_fingerprint != dispatch.fit_plan_fingerprint:
            raise StaleApprovalError("Stale fit approval cannot launch.")
        if approval.approval_id != dispatch.fit_approval_id:
            raise StaleApprovalError("Dispatch is not bound to the current FitApproval.")
        if dispatch.compute_profile is not fit_plan.compute_profile:
            raise InputContractMismatchError(
                "Dispatch compute profile must match the approved FitPlan."
            )
        if dispatch.cloud_run_execution_name:
            return dispatch
        execution_name = launcher.launch(dispatch_id)
        updated = dispatch.model_copy(
            update={
                "cloud_run_execution_name": execution_name,
                "status": FitDispatchStatus.RUNNING,
                "launch_outcome": FitDispatchOutcome.SUCCESSFULLY_LAUNCHED,
                "updated_at": utc_now(),
            }
        )
        return self.repo.put_dispatch(updated)

    def _execute_fit(self, version, plan, fit_plan, run: FitRun) -> FitRun:
        if run.status in TERMINAL_FIT_STATUSES:
            return run
        running = run.model_copy(
            update={
                "status": FitRunStatus.RUNNING,
                "started_at": run.started_at or utc_now(),
            }
        )
        self.repo.put_fit_run(running)
        current = self.get_version(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
        if current.state is MMMModelingStage.AWAITING_FIT_APPROVAL:
            current = self._transition(current, MMMModelingStage.FITTING_MODEL)
        try:
            result = execute_approved_fit(
                self.runtime,
                plan,
                fit_plan,
                expected_input_fingerprint=plan.model_ready_manifest_fingerprint,
            )
        except Exception as exc:
            return self._record_fit_failure(current, plan, fit_plan, running, exc)
        version = current
        stored = result.binary
        try:
            loaded = self.repo.get_binary(run.fit_run_id)
            if loaded is None:
                self.repo.put_binary(fit_run_id=run.fit_run_id, payload=result.binary)
            stored = self.repo.get_binary(run.fit_run_id) or result.binary
        except ModelVersionImmutableError:
            stored = result.binary
        if hashlib.sha256(stored).hexdigest() != result.binary_sha256:
            raise ArtifactVerificationFailedError("Model binary read-back hash mismatch.")
        manifest = MeridianModelArtifactManifest(
            model_version_id=version.model_version_id,
            fit_run_id=run.fit_run_id,
            meridian_version=result.meridian_version,
            worker_image_digest=result.worker_image_digest,
            input_manifest_ref=version.model_ready_manifest_ref,
            input_fingerprint=plan.model_ready_manifest_fingerprint,
            model_plan_fingerprint=plan.fingerprint,
            fit_plan_fingerprint=fit_plan.fingerprint,
            binary_model_ref=f"modeling/{version.model_version_id}/meridian_model.binpb",
            binary_sha256=result.binary_sha256,
            runtime_mode=result.runtime_mode,
            serde_readback_ok=result.serde_readback_ok,
        )
        self.repo.put_artifact(manifest)
        health = interpret_reviewer_results(
            model_version_id=version.model_version_id,
            fit_run_id=run.fit_run_id,
            meridian_version=result.meridian_version,
            results=result.health_checks,
            runtime_mode=result.runtime_mode,
            review_source=result.review_source,
        )
        self.repo.put_health(health)
        results = structured_results(
            html_ref=f"modeling/{version.model_version_id}/results_summary.html",
            requested_date_range=f"{plan.model_window_start}/{plan.model_window_end}",
            effective_date_range=f"{plan.model_window_start}/{plan.model_window_end}",
            values=result.structured,
            html_sha256=result.results_html_sha256,
        )
        review_required = tuple(
            item.check_name
            for item in health.check_results
            if item.status is OfficialHealthStatus.REVIEW
        )
        pack = assemble_review_pack(
            model_version_id=version.model_version_id,
            fit_run_id=run.fit_run_id,
            model_spec_summary=plan.spec.model_dump(mode="json"),
            prior_summary={"count": len(plan.priors)},
            mcmc_summary=plan.mcmc,
            health=health,
            results=results,
            limitations=(
                "CPU smoke or worker execution is compatibility proof, "
                "not statistical adequacy.",
            ),
            review_required=review_required,
        )
        self.repo.put_review(pack)
        if self.object_store is not None and self.artifact_bucket:
            self._persist_fit_artifacts(
                version=version,
                run=run,
                result=result,
                manifest=manifest,
                pack=pack,
            )
        ledger_verified = False
        ledger_status = LedgerPublicationStatus.NOT_ATTEMPTED
        try:
            publish_fit_ledger(
                self.ledger,
                version=version,
                run=run,
                decisions=self.repo.list_decisions(version.model_version_id),
                health=health,
            )
            ledger_verified = True
            ledger_status = LedgerPublicationStatus.VERIFIED
        except LedgerPublicationError:
            ledger_status = LedgerPublicationStatus.PENDING_PUBLICATION
        completed = run.model_copy(
            update={
                "status": FitRunStatus.SUCCEEDED,
                "completed_at": utc_now(),
                "python_version": result.python_version,
                "tensorflow_version": result.tensorflow_version,
                "worker_image_digest": result.worker_image_digest,
                "runtime_mode": result.runtime_mode,
                "sampling_started": True,
                "ledger_readback_verified": ledger_verified,
                "ledger_status": ledger_status,
            }
        )
        self.repo.put_fit_run(completed)
        if run.dispatch_id:
            dispatch = self.repo.get_dispatch(run.dispatch_id)
            if dispatch is not None:
                self.repo.put_dispatch(
                    dispatch.model_copy(
                        update={
                            "status": FitDispatchStatus.COMPLETE,
                            "launch_outcome": (
                                dispatch.launch_outcome
                                or FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
                            ),
                            "updated_at": utc_now(),
                        }
                    )
                )
        current = self.get_version(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
        if current.state is MMMModelingStage.FITTING_MODEL:
            current = self._transition(current, MMMModelingStage.EVALUATING_MODEL)
            self._transition(current, MMMModelingStage.AWAITING_MODEL_REVIEW)
        return completed

    def _record_fit_failure(
        self,
        version: MMMModelVersion,
        plan,
        fit_plan,
        run: FitRun,
        exc: BaseException,
    ) -> FitRun:
        del fit_plan
        classified = classify_fit_failure(exc)
        dispatch_outcome = run.dispatch_outcome
        if run.dispatch_id:
            dispatch = self.repo.get_dispatch(run.dispatch_id)
            if dispatch is not None:
                if (
                    dispatch.cloud_run_execution_name
                    or dispatch.launch_outcome is FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
                    or dispatch.status in {FitDispatchStatus.QUEUED, FitDispatchStatus.RUNNING}
                ):
                    dispatch_outcome = FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
                self.repo.put_dispatch(
                    dispatch.model_copy(
                        update={
                            "status": FitDispatchStatus.COMPLETE,
                            "launch_outcome": (
                                dispatch_outcome or FitDispatchOutcome.SUCCESSFULLY_LAUNCHED
                            ),
                            "updated_at": utc_now(),
                        }
                    )
                )
        failed = run.model_copy(
            update={
                "status": classified.status,
                "completed_at": utc_now(),
                "error_code": classified.error_code,
                "failure_class": classified.failure_class,
                "failure_stage": classified.failure_stage,
                "sampling_started": classified.sampling_started,
                "retry_semantics": classified.retry_semantics,
                "library": classified.library,
                "library_version": classified.library_version,
                "exception_type": classified.exception_type,
                "official_message": classified.official_message,
                "prem3_summary": classified.prem3_summary,
                "next_actions": classified.next_actions,
                "dispatch_outcome": dispatch_outcome,
                "meridian_version": run.meridian_version or classified.library_version,
            }
        )
        self.repo.put_fit_run(failed)
        current = self.get_version(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
        if classified.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR:
            self.repo.put_decision(
                identifiability_decision(
                    tenant_id=current.tenant_id,
                    project_id=current.project_id,
                    model_version_id=current.model_version_id,
                    official_message=classified.official_message,
                    plan_fingerprint=None if plan is None else plan.fingerprint,
                    evidence_refs=(failed.fit_run_id, current.model_version_id),
                )
            )
            try:
                self.identifiability_package(
                    tenant_id=current.tenant_id,
                    project_id=current.project_id,
                    model_version_id=current.model_version_id,
                )
            except (KeyError, OSError, ValueError, TypeError):
                pass
            if current.state in {
                MMMModelingStage.AWAITING_FIT_APPROVAL,
                MMMModelingStage.FITTING_MODEL,
            }:
                current = self._transition(current, MMMModelingStage.ITERATION_REQUIRED)
        elif current.state in {
            MMMModelingStage.AWAITING_FIT_APPROVAL,
            MMMModelingStage.FITTING_MODEL,
        }:
            current = self._transition(current, MMMModelingStage.FAILED)
        try:
            publish_fit_ledger(
                self.ledger,
                version=current,
                run=failed,
                decisions=self.repo.list_decisions(current.model_version_id),
                health=None,
            )
            failed = failed.model_copy(
                update={
                    "ledger_readback_verified": True,
                    "ledger_status": LedgerPublicationStatus.VERIFIED,
                }
            )
            self.repo.put_fit_run(failed)
        except LedgerPublicationError:
            failed = failed.model_copy(
                update={"ledger_status": LedgerPublicationStatus.PENDING_PUBLICATION}
            )
            self.repo.put_fit_run(failed)
        return failed

    def acknowledge_review(
        self, *, tenant_id: str, project_id: str, model_version_id: str, items: tuple[str, ...]
    ):
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self._require_mutable(version)
        pack = self.repo.get_review(model_version_id)
        if pack is None:
            raise ModelReviewFailedError("Review pack is missing.")
        updated = pack.model_copy(
            update={
                "acknowledged_review_items": tuple(
                    sorted(set(pack.acknowledged_review_items) | set(items))
                )
            }
        )
        rebuilt = assemble_review_pack(
            model_version_id=pack.model_version_id,
            fit_run_id=pack.fit_run_id,
            model_spec_summary=pack.model_spec_summary,
            prior_summary=pack.prior_summary,
            mcmc_summary=pack.mcmc_summary,
            health=pack.official_health,
            results=pack.results,
            limitations=pack.known_limitations,
            review_required=pack.review_required_items,
            acknowledged=updated.acknowledged_review_items,
        )
        return self.repo.put_review(rebuilt)

    def accept(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> ModelAcceptanceApproval:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if version.accepted:
            existing = self.repo.get_acceptance(model_version_id)
            if existing is not None:
                return existing
        health = self.repo.get_health(model_version_id)
        pack = self.repo.get_review(model_version_id)
        artifact = self.repo.get_artifact(model_version_id)
        run = next(iter(self.repo.list_fit_runs(model_version_id)), None)
        if health is None or pack is None or artifact is None or run is None:
            raise ModelReviewFailedError("Fit, health, and review pack are required.")
        stored = self.repo.get_binary(run.fit_run_id)
        if stored is not None and hashlib.sha256(stored).hexdigest() != artifact.binary_sha256:
            raise ArtifactVerificationFailedError(
                "Stored model binary SHA-256 does not match the artifact manifest."
            )
        if run.runtime_mode is MeridianRuntimeMode.FAKE_TEST:
            raise FakeRuntimeAcceptanceError(
                "FAKE_TEST is permanently ineligible for production MODEL_ACCEPTED."
            )
        if run.runtime_mode is MeridianRuntimeMode.OFFICIAL_CPU_SMOKE:
            raise QualificationAcceptanceError(
                "OFFICIAL_CPU_SMOKE is ineligible for MODEL_ACCEPTED."
            )
        fit_plan = self.repo.get_fit_plan(model_version_id)
        if fit_plan is None or fit_plan.fit_purpose is not FitPurpose.FINAL_MODEL:
            raise QualificationAcceptanceError(
                "RUNTIME_QUALIFICATION and MODEL_ITERATION cannot become MODEL_ACCEPTED."
            )
        if run.runtime_mode not in PRODUCTION_OFFICIAL_RUNTIME_MODES:
            raise QualificationAcceptanceError(
                "MODEL_ACCEPTED requires OFFICIAL_MERIDIAN_RUNTIME "
                "(OFFICIAL_CPU or OFFICIAL_GPU) with an approved compute profile."
            )
        assert_final_model_provenance(
            source_commit_sha=fit_plan.source_commit_sha or run.source_commit_sha,
            worker_image_digest=fit_plan.container_image_digest or run.worker_image_digest,
            history=self.source_history,
        )
        if _is_service_account_actor(actor_id):
            raise HumanApprovalRequiredError(
                "A service account cannot be the human ModelAcceptance actor."
            )
        if health.review_source is not ReviewSource.OFFICIAL_MERIDIAN:
            raise FakeRuntimeAcceptanceError(
                "Production MODEL_ACCEPTED requires review_source=OFFICIAL_MERIDIAN."
            )
        if not artifact.serde_readback_ok:
            raise ModelReviewFailedError("Official serde read-back is required.")
        if not run.ledger_readback_verified:
            raise LedgerPublicationError(
                "MODEL_ACCEPTED requires durable BigQuery ledger write/read-back."
            )
        if any(
            item.check_name == "ConvergenceCheck" and item.status is OfficialHealthStatus.FAIL
            for item in health.check_results
        ):
            raise ModelReviewFailedError("Convergence FAIL blocks MODEL_ACCEPTED.")
        if health.blocking_fail_count:
            raise ModelReviewFailedError("Official FAIL blocks MODEL_ACCEPTED.")
        pending_review = set(pack.review_required_items) - set(pack.acknowledged_review_items)
        if pending_review:
            raise ModelReviewFailedError("Official REVIEW requires acknowledgment.")
        approval = ModelAcceptanceApproval(
            approval_id=new_approval_id(),
            model_version_id=model_version_id,
            fit_run_id=run.fit_run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            review_pack_fingerprint=pack.fingerprint,
            model_artifact_fingerprint=artifact.binary_sha256,
            approved_by=actor_id,
            approved_at=datetime.now(UTC),
            decision=AcceptanceDecision.ACCEPT,
            reason=reason,
        )
        self.repo.put_acceptance(approval)
        if version.state is MMMModelingStage.AWAITING_MODEL_REVIEW:
            self._transition(version, MMMModelingStage.MODEL_ACCEPTED)
        current = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self.repo.put_version(current.model_copy(update={"accepted": True}))
        return approval

    def _persist_fit_artifacts(
        self,
        *,
        version: MMMModelVersion,
        run: FitRun,
        result: Any,
        manifest: MeridianModelArtifactManifest,
        pack: Any,
    ) -> None:
        del run
        prefix = modeling_prefix(version.tenant_id, version.project_id, version.model_version_id)
        bucket = self.artifact_bucket or ""
        store = self.object_store
        try:
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{CANONICAL_MODEL_BINARY_NAME}",
                data=result.binary,
                content_type="application/octet-stream",
                expected_sha256=result.binary_sha256,
            )
            health_html = (result.health_html or "").encode("utf-8")
            results_html = (result.results_html or "").encode("utf-8")
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{HEALTH_HTML_NAME}",
                data=health_html,
                content_type="text/html; charset=utf-8",
            )
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{RESULTS_HTML_NAME}",
                data=results_html,
                content_type="text/html; charset=utf-8",
            )
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{ARTIFACT_MANIFEST_NAME}",
                data=json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode("utf-8"),
                content_type="application/json",
            )
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{REVIEW_PACK_NAME}",
                data=json.dumps(pack.model_dump(mode="json"), sort_keys=True).encode("utf-8"),
                content_type="application/json",
            )
            repro = {
                "model_version_id": version.model_version_id,
                "model_plan_fingerprint": version.model_plan_fingerprint,
                "fit_plan_fingerprint": manifest.fit_plan_fingerprint,
                "binary_sha256": manifest.binary_sha256,
                "worker_image_digest": manifest.worker_image_digest,
                "meridian_version": manifest.meridian_version,
                "runtime_mode": manifest.runtime_mode.value,
            }
            persist_immutable_bytes(
                store,
                bucket=bucket,
                object_name=f"{prefix}{REPRODUCIBILITY_NAME}",
                data=json.dumps(repro, sort_keys=True).encode("utf-8"),
                content_type="application/json",
            )
        except ArtifactVerificationFailedError as exc:
            raise GcsPersistenceError(str(exc)) from exc
        except FileExistsError as exc:
            raise GcsPersistenceError("Model-version artifact path already exists.") from exc

    def _identifiability_decision(self, model_version_id: str) -> ModelDecision | None:
        for item in self.repo.list_decisions(model_version_id):
            if isinstance(item.proposal, dict) and item.proposal.get("kind") == "IDENTIFIABILITY":
                return item
        return None

    def identifiability_package(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
    ) -> MMMIdentifiabilityDecisionPackage:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        existing = self.repo.get_identifiability_package_for_version(model_version_id)
        if existing is not None:
            return existing
        plan = self.repo.get_plan(model_version_id)
        runs = self.repo.list_fit_runs(model_version_id)
        run = next(
            (
                item
                for item in reversed(runs)
                if item.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR
            ),
            runs[-1] if runs else None,
        )
        if run is None or not run.official_message:
            raise IdentifiabilityDecisionRequiredError(
                "Identifiability package requires an official pre-fit failure."
            )
        approval = self.repo.get_fit_approval(model_version_id)
        fit_plan = self.repo.get_fit_plan(model_version_id)
        model_evidence = {
            "failed_model_plan_fingerprint": None if plan is None else plan.fingerprint,
            "failed_fit_plan_fingerprint": None if fit_plan is None else fit_plan.fingerprint,
            "failed_fit_approval_id": None if approval is None else approval.approval_id,
            "failed_fit_run_id": run.fit_run_id,
            "model_window": [
                None if plan is None else plan.model_window_start,
                None if plan is None else plan.model_window_end,
            ],
            "knots": None if plan is None else plan.spec.knots,
            "enable_aks": None if plan is None else plan.spec.enable_aks,
            "non_media_treatments": None if plan is None else plan.non_media_treatments,
            "fit_purpose": None if fit_plan is None else fit_plan.fit_purpose.value,
            "mcmc": None if fit_plan is None else {
                "n_chains": fit_plan.n_chains,
                "n_adapt": fit_plan.n_adapt,
                "n_burnin": fit_plan.n_burnin,
                "n_keep": fit_plan.n_keep,
            },
            "model_ready_fingerprint": version.model_ready_manifest_fingerprint,
            "business_profile_snapshot_id": version.business_profile_snapshot_id,
            "design_brief": None
            if self.repo.get_brief(model_version_id) is None
            else self.repo.get_brief(model_version_id).model_dump(mode="json"),
        }
        fingerprint = version.model_ready_manifest_fingerprint
        if fingerprint in MUSIC_CENTER_FINAL_FINGERPRINTS:
            package = build_music_center_v1_package(
                project_id=version.project_id,
                failed_model_version_id=version.model_version_id,
                failed_fit_run_id=run.fit_run_id,
                official_message=run.official_message,
                model_evidence=model_evidence,
            )
        else:
            package = build_identifiability_package(
                project_id=version.project_id,
                cycle_id=version.cycle_id,
                failed_model_version_id=version.model_version_id,
                failed_fit_run_id=run.fit_run_id,
                official_message=run.official_message,
                failure_class=run.failure_class or FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR,
                failure_stage=run.failure_stage or FitFailureStage.MODEL_INITIALIZATION,
                library=run.library or "google-meridian",
                library_version=run.library_version or PINNED_RUNTIME_VERSION,
                exception_type=run.exception_type,
                model_evidence=model_evidence,
            )
        assert package_is_advisory(package)
        return self.repo.put_identifiability_package(package)

    def record_identifiability_decision(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
        actor_id: str,
        selected_alternative_id: str,
        selected_configuration: dict[str, Any],
        rationale: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> ModelDecision:
        if _is_service_account_actor(actor_id):
            raise HumanApprovalRequiredError(
                "A service account cannot approve an identifiability ModelDecision."
            )
        refuse_fabricated_geo_variation(selected_configuration)
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if version.state is not MMMModelingStage.ITERATION_REQUIRED:
            raise IdentifiabilityDecisionRequiredError(
                "Identifiability decisions are recorded on ITERATION_REQUIRED versions."
            )
        decision = self._identifiability_decision(model_version_id)
        if decision is None:
            raise IdentifiabilityDecisionRequiredError(
                "No pending identifiability decision exists."
            )
        alternative = IdentifiabilityAlternativeId(selected_alternative_id)
        package = self.identifiability_package(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        alt = next(
            item for item in package.alternatives if item.alternative_id is alternative
        )
        if not alt.available:
            raise IdentifiabilityDecisionRequiredError(
                f"Alternative {alternative.value} is not eligible: {alt.unavailable_reason}"
            )
        chosen = {
            "selected_alternative": alternative.value,
            "selected_configuration": selected_configuration,
            "rationale": rationale,
            "evidence_refs": list(evidence_refs) or [
                package.package_id,
                version.model_version_id,
            ],
        }
        fingerprint = canonical_fingerprint(
            {
                "package_id": package.package_id,
                "chosen": chosen,
                "approved_by": actor_id,
            }
        )
        chosen["decision_fingerprint"] = fingerprint
        updated = decision.model_copy(
            update={
                "status": DecisionStatus.APPROVED,
                "chosen_value": chosen,
                "approved_by": actor_id,
                "approved_at": utc_now(),
                "reason": rationale,
            }
        )
        stored = self.repo.put_decision(updated)
        self.repo.put_identifiability_package(
            package.model_copy(
                update={
                    "decision_status": IdentifiabilityPackageStatus.DECIDED,
                    "selected_alternative": alternative,
                }
            )
        )
        predecessor = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        assert predecessor.state is MMMModelingStage.ITERATION_REQUIRED
        return stored

    def validate_prefit(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ):
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self._require_mutable(version)
        plan = self.repo.get_plan(model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        geo_invariant = plan.model_ready_manifest_fingerprint in MUSIC_CENTER_FINAL_FINGERPRINTS
        treatments = plan.non_media_treatments
        if treatments is not None and "music_center_promo" not in treatments:
            geo_invariant = False
        n_time = MUSIC_CENTER_MODEL_READY_COVERAGE.n_times if geo_invariant else None
        receipt = execute_prefit_validation(
            self.runtime,
            plan,
            model_version_id=model_version_id,
            geo_invariant_non_media=geo_invariant,
            n_time=n_time,
        )
        stored = self.repo.put_prefit_receipt(receipt)
        if stored.status is not PreFitCheckStatus.PASS:
            raise PrefitValidationFailedError(
                stored.official_message or "Official pre-fit validation failed."
            )
        return stored

    def iterate(
        self,
        *,
        tenant_id: str,
        project_id: str,
        model_version_id: str,
        actor_id: str,
        reason: str,
    ) -> MMMModelVersion:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if version.accepted:
            raise ModelVersionImmutableError("Accepted model versions cannot iterate in place.")
        ident = self._identifiability_decision(model_version_id)
        if version.state is MMMModelingStage.ITERATION_REQUIRED:
            if ident is None or ident.status is not DecisionStatus.APPROVED:
                raise IdentifiabilityDecisionRequiredError(
                    "A human identifiability ModelDecision is required before a successor model."
                )
            if ident.chosen_value is None:
                raise IdentifiabilityDecisionRequiredError(
                    "A human identifiability ModelDecision is required before a successor model."
                )
        if version.state is MMMModelingStage.AWAITING_MODEL_REVIEW:
            version = self._transition(version, MMMModelingStage.ITERATING_MODEL)
        plan = self.repo.get_plan(model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        old_artifact = self.repo.get_artifact(model_version_id)
        successor = self.start_design(
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=version.cycle_id,
            track_id=version.track_id,
            actor_id=actor_id,
            model_ready_run_id=version.model_ready_run_id,
            model_ready_manifest_fingerprint=version.model_ready_manifest_fingerprint,
            model_ready_manifest_ref=version.model_ready_manifest_ref,
            business_profile_snapshot_id=version.business_profile_snapshot_id,
            model_window_start=plan.model_window_start,
            model_window_end=plan.model_window_end,
            scope=plan.scope,
            media_channels=plan.media_channels,
            rf_channels=plan.rf_channels,
            compute_profile=plan.compute_profile,
        )
        update: dict[str, Any] = {
            "supersedes_model_version_id": version.model_version_id,
            "iteration_reason": reason,
            "version": version.version + 1,
        }
        if ident is not None and ident.status is DecisionStatus.APPROVED:
            update["iteration_reason"] = ITERATION_REASON_IDENTIFIABILITY
            update["source_model_decision_id"] = ident.decision_id
            failed_run = next(
                (
                    item
                    for item in self.repo.list_fit_runs(model_version_id)
                    if item.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR
                ),
                None,
            )
            if failed_run is not None:
                update["source_fit_run_id"] = failed_run.fit_run_id
            package = self.repo.get_identifiability_package_for_version(model_version_id)
            compiled = compile_successor_model_plan(
                predecessor=plan,
                successor_model_version_id=successor.model_version_id,
                decision=ident,
                knot_proposal=None if package is None else package.knot_strategy_proposal,
            )
            if isinstance(compiled, DataFoundationWorkRequest):
                raise IdentifiabilityDecisionRequiredError(compiled.reason)
            if compiled.fingerprint == plan.fingerprint:
                raise ModelSpecInvalidError("Successor ModelPlan must have a new fingerprint.")
            self.repo.put_plan(compiled)
            update["model_plan_id"] = compiled.model_plan_id
            update["model_plan_fingerprint"] = compiled.fingerprint
            if selected_alternative(ident) is IdentifiabilityAlternativeId.B:
                brief = self.repo.get_brief(successor.model_version_id)
                if brief is not None:
                    self.repo.put_brief(
                        brief.model_copy(
                            update={
                                "known_limitations": brief.known_limitations
                                + (PROMOTION_NOT_EXPLICITLY_MODELED,),
                                "non_media_treatments": compiled.non_media_treatments or (),
                            }
                        )
                    )
        successor = successor.model_copy(update=update)
        stored = self.repo.put_version(successor)
        predecessor = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        if predecessor.state is not MMMModelingStage.ITERATION_REQUIRED and ident is not None:
            raise ModelVersionImmutableError("Failed predecessor must remain ITERATION_REQUIRED.")
        if old_artifact is not None:
            still = self.repo.get_artifact(model_version_id)
            if still is None or still.binary_sha256 != old_artifact.binary_sha256:
                raise ArtifactVerificationFailedError(
                    "Predecessor artifact mutated during iteration."
                )
        return stored
