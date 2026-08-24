"""Modeling receipts: concise proof, not raw logs."""

from __future__ import annotations

from typing import Any

from app.modeling.mmm.contracts import (
    FitApproval,
    MeridianFitPlan,
    MeridianModelArtifactManifest,
    MeridianModelHealthReceipt,
    MeridianPriorValidationReceipt,
    MMMModelDesignBrief,
    MMMModelReviewPack,
    MMMModelVersion,
    MMMReproducibilityManifest,
    ModelAcceptanceApproval,
    ModelDecision,
    ModelingReceipt,
)
from app.modeling.mmm.mel import modeling_episode_evidence


def design_receipt(version: MMMModelVersion, brief: MMMModelDesignBrief) -> ModelingReceipt:
    return modeling_episode_evidence(
        event="MODEL_DESIGN",
        model_version_id=version.model_version_id,
        payload={
            "state": version.state.value,
            "model_plan_fingerprint": version.model_plan_fingerprint,
            "decisions_requiring_human_input": list(brief.decisions_requiring_human_input),
        },
    )


def decision_receipt(decision: ModelDecision) -> ModelingReceipt:
    return modeling_episode_evidence(
        event="MODEL_DECISION",
        model_version_id=decision.model_version_id,
        payload={
            "decision_id": decision.decision_id,
            "decision_type": decision.decision_type.value,
            "status": decision.status.value,
            "plan_fingerprint": decision.plan_fingerprint,
        },
    )


def fit_approval_receipt(approval: FitApproval) -> ModelingReceipt:
    return modeling_episode_evidence(
        event="FIT_APPROVAL",
        model_version_id=approval.model_version_id,
        payload={
            "approval_id": approval.approval_id,
            "fit_plan_fingerprint": approval.fit_plan_fingerprint,
            "approved_by": approval.approved_by,
        },
    )


def acceptance_receipt(approval: ModelAcceptanceApproval) -> ModelingReceipt:
    return modeling_episode_evidence(
        event="MODEL_ACCEPTANCE",
        model_version_id=approval.model_version_id,
        payload={
            "approval_id": approval.approval_id,
            "decision": approval.decision.value,
            "review_pack_fingerprint": approval.review_pack_fingerprint,
            "model_artifact_fingerprint": approval.model_artifact_fingerprint,
        },
    )


def reproducibility_manifest(
    *,
    version: MMMModelVersion,
    decision_ids: tuple[str, ...],
    fit_plan: MeridianFitPlan | None,
    artifact: MeridianModelArtifactManifest | None,
    review: MMMModelReviewPack | None,
    acceptance: ModelAcceptanceApproval | None,
    asset_versions: tuple[str, ...] = (),
) -> MMMReproducibilityManifest:
    return MMMReproducibilityManifest(
        project_id=version.project_id,
        cycle_id=version.cycle_id,
        track_id=version.track_id,
        business_profile_snapshot_id=version.business_profile_snapshot_id,
        model_ready_manifest_fingerprint=version.model_ready_manifest_fingerprint,
        model_plan_fingerprint=version.model_plan_fingerprint or "",
        decision_ids=decision_ids,
        meridian_version=version.meridian_version,
        external_knowledge_asset_versions=asset_versions,
        worker_image_digest=None if artifact is None else artifact.worker_image_digest,
        fit_configuration={} if fit_plan is None else fit_plan.model_dump(mode="json"),
        model_artifact_hash=None if artifact is None else artifact.binary_sha256,
        review_artifact_refs=() if review is None else (review.fingerprint,),
        acceptance_approval_id=None if acceptance is None else acceptance.approval_id,
    )


def receipt_cannot_mutate_plan(receipt: ModelingReceipt) -> bool:
    payload: dict[str, Any] = receipt.payload
    return payload.get("can_mutate_plan") is False


__all__ = [
    "MeridianModelHealthReceipt",
    "MeridianPriorValidationReceipt",
    "ModelingReceipt",
    "acceptance_receipt",
    "decision_receipt",
    "design_receipt",
    "fit_approval_receipt",
    "receipt_cannot_mutate_plan",
    "reproducibility_manifest",
]
