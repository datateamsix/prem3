"""Governed MMM modeling service. Agent proposes; humans approve; worker executes."""

from __future__ import annotations

import hashlib
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
from app.modeling.common.errors import (
    ArtifactVerificationFailedError,
    FakeRuntimeAcceptanceError,
    FitApprovalRequiredError,
    InputContractMismatchError,
    LedgerPublicationError,
    ModelReviewFailedError,
    ModelSpecInvalidError,
    ModelVersionImmutableError,
    ModelVersionNotFoundError,
    ResourceExhaustedError,
    StaleApprovalError,
)
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compiler import compile_fit_plan_payload, compile_meridian_model_spec
from app.modeling.mmm.contracts import (
    AcceptanceDecision,
    ComputeProfile,
    DecisionStatus,
    DecisionType,
    FitApproval,
    FitDispatchStatus,
    FitRun,
    FitRunStatus,
    LedgerPublicationStatus,
    MeridianFitDispatch,
    MeridianFitPlan,
    MeridianModelArtifactManifest,
    MeridianPriorValidationReceipt,
    MeridianRuntimeMode,
    MMMModelVersion,
    ModelAcceptanceApproval,
    ModelReadyCoverage,
    OfficialHealthStatus,
    PriorValidationStatus,
    ReviewSource,
)
from app.modeling.mmm.coverage import (
    assert_cycle_does_not_define_window,
    assert_model_window_inside_coverage,
    assert_window_change_invalidates_approval,
)
from app.modeling.mmm.design import (
    REQUIRED_DECISION_TYPES,
    build_design_brief,
    initial_decisions,
    proposed_model_plan,
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
from app.modeling.mmm.repository import InMemoryModelingRepository, ModelingRepository
from app.modeling.mmm.review import assemble_review_pack
from app.modeling.mmm.states import (
    MMMModelingStage,
    assert_legal_modeling_transition,
)

MAX_CONCURRENT_FITS_PER_PROJECT = 1
MAX_CONCURRENT_FITS_PER_TENANT = 2


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
    ) -> None:
        self.repo = repo or InMemoryModelingRepository()
        self.runtime = runtime or FakeMeridianRuntime()
        self.ledger = ledger or InMemoryModelLedger()
        self.dispatcher = dispatcher
        self.object_store = object_store
        self.artifact_bucket = artifact_bucket
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

    def compile_fit_plan(self, version: MMMModelVersion) -> MeridianFitPlan:
        plan = self.repo.get_plan(version.model_version_id)
        if plan is None:
            raise ModelVersionNotFoundError("Model plan was not found.")
        payload = compile_fit_plan_payload(plan)
        fit_plan = MeridianFitPlan(
            model_version_id=version.model_version_id,
            model_plan_fingerprint=plan.fingerprint,
            meridian_version=PINNED_RUNTIME_VERSION,
            n_chains=payload["n_chains"],
            n_adapt=payload["n_adapt"],
            n_burnin=payload["n_burnin"],
            n_keep=payload["n_keep"],
            seed=payload["seed"],
            compute_profile=plan.compute_profile,
            input_fingerprint=plan.model_ready_manifest_fingerprint,
            fingerprint=canonical_fingerprint(payload),
        )
        return self.repo.put_fit_plan(fit_plan)

    def approve_fit(
        self, *, tenant_id: str, project_id: str, model_version_id: str, actor_id: str
    ) -> FitApproval:
        version = self.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )
        self._require_mutable(version)
        prior = self.repo.get_prior_receipt(model_version_id)
        if prior is None or prior.status is not PriorValidationStatus.PASS:
            raise FitApprovalRequiredError("Final prior validation must pass before fit approval.")
        existing = self.repo.get_fit_approval(model_version_id)
        fit_plan = self.compile_fit_plan(version)
        plan = self.repo.get_plan(model_version_id)
        assert plan is not None
        if (
            existing is not None
            and not existing.superseded
            and existing.fit_plan_fingerprint == fit_plan.fingerprint
            and existing.model_plan_fingerprint == plan.fingerprint
        ):
            return existing
        approval = FitApproval(
            approval_id=new_approval_id(),
            model_version_id=model_version_id,
            tenant_id=tenant_id,
            project_id=project_id,
            fit_plan_fingerprint=fit_plan.fingerprint,
            model_plan_fingerprint=plan.fingerprint,
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
            self._require_mutable(version)
            plan = self.repo.get_plan(model_version_id)
            fit_plan = self.repo.get_fit_plan(model_version_id)
            approval = self.repo.get_fit_approval(model_version_id)
            if plan is None or fit_plan is None:
                raise FitApprovalRequiredError("Fit plan has not been compiled.")
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
            assert_window_change_invalidates_approval(plan=plan, approval=approval)
            if approval.tenant_id != tenant_id or approval.project_id != project_id:
                raise StaleApprovalError("Cross-project fit approval rejected.")
            existing = [
                item
                for item in self.repo.list_fit_runs(model_version_id)
                if item.fit_plan_fingerprint == fit_plan.fingerprint
                and item.status
                in {FitRunStatus.PENDING, FitRunStatus.RUNNING, FitRunStatus.SUCCEEDED}
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
            run = FitRun(
                fit_run_id=new_fit_run_id(),
                model_version_id=model_version_id,
                tenant_id=tenant_id,
                project_id=project_id,
                fit_plan_fingerprint=fit_plan.fingerprint,
                status=FitRunStatus.RUNNING,
                compute_profile=fit_plan.compute_profile,
                runtime_mode=getattr(
                    self.runtime, "runtime_mode", MeridianRuntimeMode.FAKE_TEST
                ),
                meridian_version=PINNED_RUNTIME_VERSION,
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
        mode = runtime_mode_for_profile(
            fit_plan.compute_profile.value,
            official=not isinstance(self.runtime, FakeMeridianRuntime),
        )
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
        return run.model_copy(
            update={"dispatch_id": stored.dispatch_id, "status": FitRunStatus.PENDING}
        )

    def _execute_fit(self, version, plan, fit_plan, run: FitRun) -> FitRun:
        result = execute_approved_fit(
            self.runtime,
            plan,
            fit_plan,
            expected_input_fingerprint=plan.model_ready_manifest_fingerprint,
        )
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
                "ledger_readback_verified": ledger_verified,
                "ledger_status": ledger_status,
            }
        )
        self.repo.put_fit_run(completed)
        current = self.get_version(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
        if current.state is MMMModelingStage.FITTING_MODEL:
            current = self._transition(current, MMMModelingStage.EVALUATING_MODEL)
            self._transition(current, MMMModelingStage.AWAITING_MODEL_REVIEW)
        return completed

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
        )
        successor = successor.model_copy(
            update={
                "supersedes_model_version_id": version.model_version_id,
                "iteration_reason": reason,
                "version": version.version + 1,
            }
        )
        stored = self.repo.put_version(successor)
        if old_artifact is not None:
            still = self.repo.get_artifact(model_version_id)
            if still is None or still.binary_sha256 != old_artifact.binary_sha256:
                raise ArtifactVerificationFailedError(
                    "Predecessor artifact mutated during iteration."
                )
        return stored
