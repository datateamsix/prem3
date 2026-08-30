"""Production Firestore twin for the MMM modeling domain. No binaries or HTML."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
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

COL_TENANTS = "tenants"
COL_WORKSPACES = "workspaces"
COL_INDEX = "mmm_modeling_index"


def _already_exists(exc: BaseException) -> bool:
    """Live Firestore raises AlreadyExists; FakeFirestore raises FileExistsError."""
    return isinstance(exc, FileExistsError) or "AlreadyExists" in type(exc).__name__


class FirestoreModelingRepository:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _ws(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COL_TENANTS)
            .document(tenant_id)
            .collection(COL_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, key: str, tenant_id: str, workspace_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"{kind}__{key}").set(
            {"tenant_id": tenant_id, "workspace_id": workspace_id, "kind": kind}
        )

    def _lookup(self, kind: str, key: str) -> tuple[str, str] | None:
        snap = self._db.collection(COL_INDEX).document(f"{kind}__{key}").get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return str(data["tenant_id"]), str(data["workspace_id"])

    def _put(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model: Any
    ) -> None:
        self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).set(
            model_to_document(model)
        )

    def _get(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model_type: Any
    ):
        snap = self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def _stream(self, tenant_id: str, workspace_id: str, collection: str, model_type: Any) -> list:
        return [
            document_to_model(model_type, snap.to_dict())
            for snap in self._ws(tenant_id, workspace_id).collection(collection).stream()
        ]

    def _owner(self, model_version_id: str) -> tuple[str, str] | None:
        return self._lookup("model_version", model_version_id)

    def put_version(self, version: MMMModelVersion) -> MMMModelVersion:
        existing = self.get_version(
            tenant_id=version.tenant_id,
            project_id=version.project_id,
            model_version_id=version.model_version_id,
        )
        if existing is not None and existing.accepted:
            if (
                existing.model_window_start != version.model_window_start
                or existing.model_window_end != version.model_window_end
                or existing.model_plan_fingerprint != version.model_plan_fingerprint
                or not version.accepted
            ):
                raise ModelVersionImmutableError("Accepted model versions cannot be rewritten.")
        self._put(
            version.tenant_id,
            version.project_id,
            "mmm_model_versions",
            version.model_version_id,
            version,
        )
        self._index(
            "model_version", version.model_version_id, version.tenant_id, version.project_id
        )
        return version

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None:
        version = self._get(
            tenant_id, project_id, "mmm_model_versions", model_version_id, MMMModelVersion
        )
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
            for item in self._stream(
                tenant_id, project_id, "mmm_model_versions", MMMModelVersion
            )
            if item.tenant_id == tenant_id and item.project_id == project_id
        ]
        if cycle_id is not None:
            items = [item for item in items if item.cycle_id == cycle_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def put_plan(self, plan: ModelPlan) -> ModelPlan:
        loc = self._owner(plan.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before plan persistence.")
        self._put(loc[0], loc[1], "mmm_model_plans", plan.model_version_id, plan)
        return plan

    def get_plan(self, model_version_id: str) -> ModelPlan | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_model_plans", model_version_id, ModelPlan)

    def put_brief(self, brief: MMMModelDesignBrief) -> MMMModelDesignBrief:
        loc = self._owner(brief.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before brief persistence.")
        self._put(loc[0], loc[1], "mmm_design_briefs", brief.model_version_id, brief)
        return brief

    def get_brief(self, model_version_id: str) -> MMMModelDesignBrief | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], "mmm_design_briefs", model_version_id, MMMModelDesignBrief
        )

    def put_decision(self, decision: ModelDecision) -> ModelDecision:
        self._put(
            decision.tenant_id,
            decision.project_id,
            "mmm_model_decisions",
            decision.decision_id,
            decision,
        )
        self._index("decision", decision.decision_id, decision.tenant_id, decision.project_id)
        return decision

    def get_decision(
        self, *, tenant_id: str, project_id: str, decision_id: str
    ) -> ModelDecision | None:
        decision = self._get(
            tenant_id, project_id, "mmm_model_decisions", decision_id, ModelDecision
        )
        if decision is None:
            return None
        if decision.tenant_id != tenant_id or decision.project_id != project_id:
            return None
        return decision

    def list_decisions(self, model_version_id: str) -> list[ModelDecision]:
        loc = self._owner(model_version_id)
        if loc is None:
            return []
        return [
            item
            for item in self._stream(loc[0], loc[1], "mmm_model_decisions", ModelDecision)
            if item.model_version_id == model_version_id
        ]

    def put_fit_plan(self, plan: MeridianFitPlan) -> MeridianFitPlan:
        loc = self._owner(plan.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before fit plan.")
        self._put(loc[0], loc[1], "mmm_fit_plans", plan.model_version_id, plan)
        return plan

    def get_fit_plan(self, model_version_id: str) -> MeridianFitPlan | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_fit_plans", model_version_id, MeridianFitPlan)

    def put_fit_approval(self, approval: FitApproval) -> FitApproval:
        self._put(
            approval.tenant_id,
            approval.project_id,
            "mmm_fit_approvals",
            approval.model_version_id,
            approval,
        )
        return approval

    def get_fit_approval(self, model_version_id: str) -> FitApproval | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_fit_approvals", model_version_id, FitApproval)

    def put_fit_run(self, run: FitRun) -> FitRun:
        self._put(run.tenant_id, run.project_id, "mmm_fit_runs", run.fit_run_id, run)
        self._index("fit_run", run.fit_run_id, run.tenant_id, run.project_id)
        return run

    def get_fit_run(
        self, *, tenant_id: str, project_id: str, fit_run_id: str
    ) -> FitRun | None:
        run = self._get(tenant_id, project_id, "mmm_fit_runs", fit_run_id, FitRun)
        if run is None:
            return None
        if run.tenant_id != tenant_id or run.project_id != project_id:
            return None
        return run

    def list_fit_runs(self, model_version_id: str) -> list[FitRun]:
        loc = self._owner(model_version_id)
        if loc is None:
            return []
        return [
            item
            for item in self._stream(loc[0], loc[1], "mmm_fit_runs", FitRun)
            if item.model_version_id == model_version_id
        ]

    def put_prior_receipt(
        self, receipt: MeridianPriorValidationReceipt
    ) -> MeridianPriorValidationReceipt:
        loc = self._owner(receipt.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before prior receipt.")
        self._put(loc[0], loc[1], "mmm_prior_receipts", receipt.model_version_id, receipt)
        return receipt

    def get_prior_receipt(self, model_version_id: str) -> MeridianPriorValidationReceipt | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], "mmm_prior_receipts", model_version_id, MeridianPriorValidationReceipt
        )

    def put_artifact(
        self, manifest: MeridianModelArtifactManifest
    ) -> MeridianModelArtifactManifest:
        loc = self._owner(manifest.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before artifact metadata.")
        self._put(loc[0], loc[1], "mmm_artifacts", manifest.model_version_id, manifest)
        return manifest

    def get_artifact(self, model_version_id: str) -> MeridianModelArtifactManifest | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], "mmm_artifacts", model_version_id, MeridianModelArtifactManifest
        )

    def put_binary(self, *, fit_run_id: str, payload: bytes) -> None:
        del fit_run_id, payload
        raise ModelVersionImmutableError("Model binaries are not stored in Firestore.")

    def get_binary(self, fit_run_id: str) -> bytes | None:
        del fit_run_id
        return None

    def put_health(self, receipt: MeridianModelHealthReceipt) -> MeridianModelHealthReceipt:
        loc = self._owner(receipt.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before health receipt.")
        self._put(loc[0], loc[1], "mmm_health", receipt.model_version_id, receipt)
        return receipt

    def get_health(self, model_version_id: str) -> MeridianModelHealthReceipt | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_health", model_version_id, MeridianModelHealthReceipt)

    def put_review(self, pack: MMMModelReviewPack) -> MMMModelReviewPack:
        loc = self._owner(pack.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before review pack.")
        self._put(loc[0], loc[1], "mmm_reviews", pack.model_version_id, pack)
        return pack

    def get_review(self, model_version_id: str) -> MMMModelReviewPack | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_reviews", model_version_id, MMMModelReviewPack)

    def put_acceptance(self, approval: ModelAcceptanceApproval) -> ModelAcceptanceApproval:
        self._put(
            approval.tenant_id,
            approval.project_id,
            "mmm_acceptances",
            approval.model_version_id,
            approval,
        )
        return approval

    def get_acceptance(self, model_version_id: str) -> ModelAcceptanceApproval | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], "mmm_acceptances", model_version_id, ModelAcceptanceApproval
        )

    def list_running_fits(
        self, *, tenant_id: str, project_id: str | None = None
    ) -> list[FitRun]:
        if project_id is None:
            return []
        return [
            item
            for item in self._stream(tenant_id, project_id, "mmm_fit_runs", FitRun)
            if item.tenant_id == tenant_id and item.status is FitRunStatus.RUNNING
        ]

    def put_dispatch(self, dispatch: MeridianFitDispatch) -> MeridianFitDispatch:
        self._put(
            dispatch.tenant_id,
            dispatch.project_id,
            "mmm_fit_dispatches",
            dispatch.dispatch_id,
            dispatch,
        )
        self._index("dispatch", dispatch.dispatch_id, dispatch.tenant_id, dispatch.project_id)
        return dispatch

    def get_dispatch(self, dispatch_id: str) -> MeridianFitDispatch | None:
        loc = self._lookup("dispatch", dispatch_id)
        if loc is None:
            return None
        return self._get(loc[0], loc[1], "mmm_fit_dispatches", dispatch_id, MeridianFitDispatch)

    def claim_canonical_dispatch(self, dispatch: MeridianFitDispatch) -> MeridianFitDispatch:
        key = f"{dispatch.model_version_id}::{dispatch.fit_plan_fingerprint}".replace("/", "_")
        ref = (
            self._ws(dispatch.tenant_id, dispatch.project_id)
            .collection("mmm_canonical_fits")
            .document(key)
        )
        try:
            ref.create(model_to_document(dispatch))
        except Exception as exc:
            if not _already_exists(exc):
                raise
            snap = ref.get()
            return document_to_model(MeridianFitDispatch, snap.to_dict())
        return self.put_dispatch(dispatch)

    def list_dispatches(self, model_version_id: str) -> list[MeridianFitDispatch]:
        loc = self._owner(model_version_id)
        if loc is None:
            return []
        return [
            item
            for item in self._stream(loc[0], loc[1], "mmm_fit_dispatches", MeridianFitDispatch)
            if item.model_version_id == model_version_id
        ]

    def put_reproducibility(
        self, manifest: MMMReproducibilityManifest
    ) -> MMMReproducibilityManifest:
        self._db.collection(COL_INDEX).document(
            f"repro__{manifest.model_plan_fingerprint}"
        ).set(model_to_document(manifest))
        return manifest

    def get_reproducibility(self, model_version_id: str) -> MMMReproducibilityManifest | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        version = self.get_version(
            tenant_id=loc[0], project_id=loc[1], model_version_id=model_version_id
        )
        if version is None or version.model_plan_fingerprint is None:
            return None
        snap = (
            self._db.collection(COL_INDEX)
            .document(f"repro__{version.model_plan_fingerprint}")
            .get()
        )
        if not snap.exists:
            return None
        return document_to_model(MMMReproducibilityManifest, snap.to_dict())

    def put_identifiability_package(
        self, package: MMMIdentifiabilityDecisionPackage
    ) -> MMMIdentifiabilityDecisionPackage:
        loc = self._owner(package.failed_model_version_id)
        if loc is None:
            raise ModelVersionImmutableError(
                "Model version is required before identifiability package."
            )
        self._put(
            loc[0],
            loc[1],
            "mmm_identifiability_packages",
            package.package_id,
            package,
        )
        self._index("identifiability_package", package.package_id, loc[0], loc[1])
        self._index(
            "identifiability_version",
            package.failed_model_version_id,
            loc[0],
            loc[1],
        )
        self._ws(loc[0], loc[1]).collection("mmm_identifiability_index").document(
            package.failed_model_version_id
        ).set({"package_id": package.package_id})
        return package

    def get_identifiability_package(
        self, package_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None:
        loc = self._lookup("identifiability_package", package_id)
        if loc is None:
            return None
        return self._get(
            loc[0],
            loc[1],
            "mmm_identifiability_packages",
            package_id,
            MMMIdentifiabilityDecisionPackage,
        )

    def get_identifiability_package_for_version(
        self, model_version_id: str
    ) -> MMMIdentifiabilityDecisionPackage | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        snap = (
            self._ws(loc[0], loc[1])
            .collection("mmm_identifiability_index")
            .document(model_version_id)
            .get()
        )
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        package_id = str(data.get("package_id") or "")
        if not package_id:
            return None
        return self.get_identifiability_package(package_id)

    def put_prefit_receipt(
        self, receipt: MeridianPreFitValidationReceipt
    ) -> MeridianPreFitValidationReceipt:
        loc = self._owner(receipt.model_version_id)
        if loc is None:
            raise ModelVersionImmutableError("Model version is required before pre-fit receipt.")
        self._put(loc[0], loc[1], "mmm_prefit_receipts", receipt.model_version_id, receipt)
        return receipt

    def get_prefit_receipt(
        self, model_version_id: str
    ) -> MeridianPreFitValidationReceipt | None:
        loc = self._owner(model_version_id)
        if loc is None:
            return None
        return self._get(
            loc[0], loc[1], "mmm_prefit_receipts", model_version_id, MeridianPreFitValidationReceipt
        )
