"""Durable MMM modeling store. Memory and Firestore twins."""

from __future__ import annotations

from threading import Lock
from typing import Protocol

from app.modeling.mmm.contracts import (
    FitApproval,
    FitRun,
    FitRunStatus,
    MeridianFitPlan,
    MeridianModelArtifactManifest,
    MeridianModelHealthReceipt,
    MeridianPriorValidationReceipt,
    MMMModelDesignBrief,
    MMMModelReviewPack,
    MMMModelVersion,
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

    def put_version(self, version: MMMModelVersion) -> MMMModelVersion:
        with self._lock:
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
