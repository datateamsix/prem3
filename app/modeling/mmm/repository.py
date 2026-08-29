"""Durable MMM modeling store. Memory and Firestore twins."""

from __future__ import annotations

from threading import Lock
from typing import Protocol

from app.modeling.common.errors import ModelVersionImmutableError
from app.modeling.mmm.contracts import (
    FitApproval,
    FitRun,
    FitRunStatus,
    MeridianFitDispatch,
    MeridianFitPlan,
    MeridianModelArtifactManifest,
    MeridianModelHealthReceipt,
    MeridianPreFitValidationReceipt,
    MeridianPriorValidationReceipt,
    MMMIdentifiabilityDecisionPackage,
    MMMModelDesignBrief,
    MMMModelReviewPack,
    MMMModelVersion,
    MMMReproducibilityManifest,
    ModelAcceptanceApproval,
    ModelDecision,
    ModelPlan,
)


class ModelingRepository(Protocol):
    def put_version(self, version: MMMModelVersion) -> MMMModelVersion: ...
    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None: ...
    def list_versions(
        self, *, tenant_id: str, project_id: str, cycle_id: str | None = None
    ) -> list[MMMModelVersion]: ...
    def put_plan(self, plan: ModelPlan) -> ModelPlan: ...
    def get_plan(self, model_version_id: str) -> ModelPlan | None: ...
    def put_brief(self, brief: MMMModelDesignBrief) -> MMMModelDesignBrief: ...
    def get_brief(self, model_version_id: str) -> MMMModelDesignBrief | None: ...
    def put_decision(self, decision: ModelDecision) -> ModelDecision: ...
    def get_decision(
        self, *, tenant_id: str, project_id: str, decision_id: str
    ) -> ModelDecision | None: ...
    def list_decisions(self, model_version_id: str) -> list[ModelDecision]: ...
    def put_fit_plan(self, plan: MeridianFitPlan) -> MeridianFitPlan: ...
    def get_fit_plan(self, model_version_id: str) -> MeridianFitPlan | None: ...
    def put_fit_approval(self, approval: FitApproval) -> FitApproval: ...
    def get_fit_approval(self, model_version_id: str) -> FitApproval | None: ...
    def put_fit_run(self, run: FitRun) -> FitRun: ...
    def get_fit_run(
        self, *, tenant_id: str, project_id: str, fit_run_id: str
    ) -> FitRun | None: ...
    def list_fit_runs(self, model_version_id: str) -> list[FitRun]: ...
    def put_prior_receipt(
        self, receipt: MeridianPriorValidationReceipt
    ) -> MeridianPriorValidationReceipt: ...
    def get_prior_receipt(
        self, model_version_id: str
    ) -> MeridianPriorValidationReceipt | None: ...
    def put_artifact(
        self, manifest: MeridianModelArtifactManifest
    ) -> MeridianModelArtifactManifest: ...
    def get_artifact(
        self, model_version_id: str
    ) -> MeridianModelArtifactManifest | None: ...
    def put_binary(self, *, fit_run_id: str, payload: bytes) -> None: ...
    def get_binary(self, fit_run_id: str) -> bytes | None: ...
    def put_health(self, receipt: MeridianModelHealthReceipt) -> MeridianModelHealthReceipt: ...
    def get_health(self, model_version_id: str) -> MeridianModelHealthReceipt | None: ...
    def put_review(self, pack: MMMModelReviewPack) -> MMMModelReviewPack: ...
    def get_review(self, model_version_id: str) -> MMMModelReviewPack | None: ...
    def put_acceptance(self, approval: ModelAcceptanceApproval) -> ModelAcceptanceApproval: ...
    def get_acceptance(self, model_version_id: str) -> ModelAcceptanceApproval | None: ...
    def list_running_fits(
        self, *, tenant_id: str, project_id: str | None = None
    ) -> list[FitRun]: ...
    def put_dispatch(self, dispatch: MeridianFitDispatch) -> MeridianFitDispatch: ...
    def get_dispatch(self, dispatch_id: str) -> MeridianFitDispatch | None: ...
    def claim_canonical_dispatch(
        self, dispatch: MeridianFitDispatch
    ) -> MeridianFitDispatch: ...
    def list_dispatches(self, model_version_id: str) -> list[MeridianFitDispatch]: ...
    def put_reproducibility(
        self, manifest: MMMReproducibilityManifest
    ) -> MMMReproducibilityManifest: ...
    def get_reproducibility(
        self, model_version_id: str
    ) -> MMMReproducibilityManifest | None: ...
    def put_identifiability_package(
        self, package: MMMIdentifiabilityDecisionPackage
    ) -> MMMIdentifiabilityDecisionPackage: ...
    def get_identifiability_package(
        self, package_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None: ...
    def get_identifiability_package_for_version(
        self, model_version_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None: ...
    def put_prefit_receipt(
        self, receipt: MeridianPreFitValidationReceipt
    ) -> MeridianPreFitValidationReceipt: ...
    def get_prefit_receipt(
        self, model_version_id: str
    ) -> MeridianPreFitValidationReceipt | None: ...


class InMemoryModelingRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self.versions: dict[str, MMMModelVersion] = {}
        self.plans: dict[str, ModelPlan] = {}
        self.briefs: dict[str, MMMModelDesignBrief] = {}
        self.decisions: dict[str, ModelDecision] = {}
        self.fit_plans: dict[str, MeridianFitPlan] = {}
        self.fit_approvals: dict[str, FitApproval] = {}
        self.fit_runs: dict[str, FitRun] = {}
        self.prior_receipts: dict[str, MeridianPriorValidationReceipt] = {}
        self.artifacts: dict[str, MeridianModelArtifactManifest] = {}
        self.binaries: dict[str, bytes] = {}
        self.health: dict[str, MeridianModelHealthReceipt] = {}
        self.reviews: dict[str, MMMModelReviewPack] = {}
        self.acceptances: dict[str, ModelAcceptanceApproval] = {}
        self.dispatches: dict[str, MeridianFitDispatch] = {}
        self.canonical_dispatches: dict[str, str] = {}
        self.reproducibility: dict[str, MMMReproducibilityManifest] = {}
        self.identifiability_packages: dict[str, MMMIdentifiabilityDecisionPackage] = {}
        self.identifiability_by_version: dict[str, str] = {}
        self.prefit_receipts: dict[str, MeridianPreFitValidationReceipt] = {}

    def put_version(self, version: MMMModelVersion) -> MMMModelVersion:
        with self._lock:
            existing = self.versions.get(version.model_version_id)
            if existing is not None and existing.accepted:
                if (
                    existing.model_window_start != version.model_window_start
                    or existing.model_window_end != version.model_window_end
                    or existing.model_plan_fingerprint != version.model_plan_fingerprint
                    or not version.accepted
                ):
                    raise ModelVersionImmutableError(
                        "Accepted model versions cannot be rewritten."
                    )
            self.versions[version.model_version_id] = version
            return version

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None:
        version = self.versions.get(model_version_id)
        if version is None:
            return None
        if version.tenant_id != tenant_id or version.project_id != project_id:
            return None
        return version

    def list_versions(
        self, *, tenant_id: str, project_id: str, cycle_id: str | None = None
    ) -> list[MMMModelVersion]:
        items = [
            item
            for item in self.versions.values()
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        if cycle_id is not None:
            items = [item for item in items if item.cycle_id == cycle_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def put_plan(self, plan: ModelPlan) -> ModelPlan:
        self.plans[plan.model_version_id] = plan
        return plan

    def get_plan(self, model_version_id: str) -> ModelPlan | None:
        return self.plans.get(model_version_id)

    def put_brief(self, brief: MMMModelDesignBrief) -> MMMModelDesignBrief:
        self.briefs[brief.model_version_id] = brief
        return brief

    def get_brief(self, model_version_id: str) -> MMMModelDesignBrief | None:
        return self.briefs.get(model_version_id)

    def put_decision(self, decision: ModelDecision) -> ModelDecision:
        self.decisions[decision.decision_id] = decision
        return decision

    def get_decision(
        self, *, tenant_id: str, project_id: str, decision_id: str
    ) -> ModelDecision | None:
        decision = self.decisions.get(decision_id)
        if decision is None:
            return None
        if decision.tenant_id != tenant_id or decision.project_id != project_id:
            return None
        return decision

    def list_decisions(self, model_version_id: str) -> list[ModelDecision]:
        return [
            item
            for item in self.decisions.values()
            if item.model_version_id == model_version_id
        ]

    def put_fit_plan(self, plan: MeridianFitPlan) -> MeridianFitPlan:
        self.fit_plans[plan.model_version_id] = plan
        return plan

    def get_fit_plan(self, model_version_id: str) -> MeridianFitPlan | None:
        return self.fit_plans.get(model_version_id)

    def put_fit_approval(self, approval: FitApproval) -> FitApproval:
        self.fit_approvals[approval.model_version_id] = approval
        return approval

    def get_fit_approval(self, model_version_id: str) -> FitApproval | None:
        return self.fit_approvals.get(model_version_id)

    def put_fit_run(self, run: FitRun) -> FitRun:
        self.fit_runs[run.fit_run_id] = run
        return run

    def get_fit_run(
        self, *, tenant_id: str, project_id: str, fit_run_id: str
    ) -> FitRun | None:
        run = self.fit_runs.get(fit_run_id)
        if run is None:
            return None
        if run.tenant_id != tenant_id or run.project_id != project_id:
            return None
        return run

    def list_fit_runs(self, model_version_id: str) -> list[FitRun]:
        return [
            item
            for item in self.fit_runs.values()
            if item.model_version_id == model_version_id
        ]

    def put_prior_receipt(
        self, receipt: MeridianPriorValidationReceipt
    ) -> MeridianPriorValidationReceipt:
        self.prior_receipts[receipt.model_version_id] = receipt
        return receipt

    def get_prior_receipt(
        self, model_version_id: str
    ) -> MeridianPriorValidationReceipt | None:
        return self.prior_receipts.get(model_version_id)

    def put_artifact(
        self, manifest: MeridianModelArtifactManifest
    ) -> MeridianModelArtifactManifest:
        self.artifacts[manifest.model_version_id] = manifest
        return manifest

    def get_artifact(self, model_version_id: str) -> MeridianModelArtifactManifest | None:
        return self.artifacts.get(model_version_id)

    def put_binary(self, *, fit_run_id: str, payload: bytes) -> None:
        self.binaries[fit_run_id] = payload

    def get_binary(self, fit_run_id: str) -> bytes | None:
        return self.binaries.get(fit_run_id)

    def put_health(self, receipt: MeridianModelHealthReceipt) -> MeridianModelHealthReceipt:
        self.health[receipt.model_version_id] = receipt
        return receipt

    def get_health(self, model_version_id: str) -> MeridianModelHealthReceipt | None:
        return self.health.get(model_version_id)

    def put_review(self, pack: MMMModelReviewPack) -> MMMModelReviewPack:
        self.reviews[pack.model_version_id] = pack
        return pack

    def get_review(self, model_version_id: str) -> MMMModelReviewPack | None:
        return self.reviews.get(model_version_id)

    def put_acceptance(self, approval: ModelAcceptanceApproval) -> ModelAcceptanceApproval:
        self.acceptances[approval.model_version_id] = approval
        return approval

    def get_acceptance(self, model_version_id: str) -> ModelAcceptanceApproval | None:
        return self.acceptances.get(model_version_id)

    def list_running_fits(
        self, *, tenant_id: str, project_id: str | None = None
    ) -> list[FitRun]:
        return [
            item
            for item in self.fit_runs.values()
            if item.tenant_id == tenant_id
            and item.status is FitRunStatus.RUNNING
            and (project_id is None or item.project_id == project_id)
        ]

    def put_dispatch(self, dispatch: MeridianFitDispatch) -> MeridianFitDispatch:
        self.dispatches[dispatch.dispatch_id] = dispatch
        return dispatch

    def get_dispatch(self, dispatch_id: str) -> MeridianFitDispatch | None:
        return self.dispatches.get(dispatch_id)

    def claim_canonical_dispatch(
        self, dispatch: MeridianFitDispatch
    ) -> MeridianFitDispatch:
        key = f"{dispatch.model_version_id}::{dispatch.fit_plan_fingerprint}"
        with self._lock:
            existing_id = self.canonical_dispatches.get(key)
            if existing_id is not None:
                return self.dispatches[existing_id]
            self.dispatches[dispatch.dispatch_id] = dispatch
            self.canonical_dispatches[key] = dispatch.dispatch_id
            return dispatch

    def list_dispatches(self, model_version_id: str) -> list[MeridianFitDispatch]:
        return [
            item
            for item in self.dispatches.values()
            if item.model_version_id == model_version_id
        ]

    def put_reproducibility(
        self, manifest: MMMReproducibilityManifest
    ) -> MMMReproducibilityManifest:
        self.reproducibility[manifest.model_plan_fingerprint] = manifest
        return manifest

    def get_reproducibility(
        self, model_version_id: str
    ) -> MMMReproducibilityManifest | None:
        version = self.versions.get(model_version_id)
        if version is None or version.model_plan_fingerprint is None:
            return None
        return self.reproducibility.get(version.model_plan_fingerprint)

    def put_identifiability_package(
        self, package: MMMIdentifiabilityDecisionPackage
    ) -> MMMIdentifiabilityDecisionPackage:
        self.identifiability_packages[package.package_id] = package
        self.identifiability_by_version[package.failed_model_version_id] = package.package_id
        return package

    def get_identifiability_package(
        self, package_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None:
        return self.identifiability_packages.get(package_id)

    def get_identifiability_package_for_version(
        self, model_version_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None:
        package_id = self.identifiability_by_version.get(model_version_id)
        if package_id is None:
            return None
        return self.identifiability_packages.get(package_id)

    def put_prefit_receipt(
        self, receipt: MeridianPreFitValidationReceipt
    ) -> MeridianPreFitValidationReceipt:
        self.prefit_receipts[receipt.model_version_id] = receipt
        return receipt

    def get_prefit_receipt(
        self, model_version_id: str
    ) -> MeridianPreFitValidationReceipt | None:
        return self.prefit_receipts.get(model_version_id)
