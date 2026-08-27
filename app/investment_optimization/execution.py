"""Dispatch-time fingerprint revalidation and execution-key identity."""

from __future__ import annotations

from app.investment_optimization.consumption import bind_projection_to_accepted_model
from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    OptimizationInputContract,
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
)
from app.investment_optimization.enums import (
    EXECUTION_POLICY_VERSION,
    PINNED_MERIDIAN_RUNTIME,
    PINNED_OPTIMIZER_GTOL,
    PINNED_SPEND_CONSTRAINT_LOWER,
    PINNED_SPEND_CONSTRAINT_UPPER,
    RUNNING_OPTIMIZATION_STATUSES,
    OptimizationIssueCode,
    OptimizationReadinessStatus,
    OptimizationRunStatus,
)
from app.investment_optimization.errors import (
    ModelArtifactUnavailableError,
    OptimizationNotReadyError,
    OptimizationReadinessStaleError,
    OptimizationReviewRequiredError,
)
from app.investment_optimization.readiness import receipt_is_stale
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.contracts import PortfolioSnapshotRef
from app.investment_planning.fingerprint import metadata_fingerprint
from app.modeling.mmm.contracts import MMMModelVersion


def optimizer_defaults_fingerprint() -> str:
    return metadata_fingerprint(
        {
            "runtime": PINNED_MERIDIAN_RUNTIME,
            "policy": EXECUTION_POLICY_VERSION,
            "fixed_budget": True,
            "use_posterior": True,
            "spend_constraint_lower": PINNED_SPEND_CONSTRAINT_LOWER,
            "spend_constraint_upper": PINNED_SPEND_CONSTRAINT_UPPER,
            "gtol": PINNED_OPTIMIZER_GTOL,
        }
    )


def execution_key(
    *,
    receipt: OptimizationReadinessReceipt,
    mapping: PortfolioModelMapping,
    input_contract: OptimizationInputContract,
    model_fingerprint: str,
    plan_version_fingerprint: str | None,
) -> str:
    return metadata_fingerprint(
        {
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.fingerprint,
            "mapping_fingerprint": mapping.fingerprint,
            "input_fingerprint": input_contract.fingerprint,
            "model_fingerprint": model_fingerprint,
            "plan_version_fingerprint": plan_version_fingerprint or "",
            "defaults": optimizer_defaults_fingerprint(),
        }
    )


def revalidate_for_dispatch(
    *,
    receipt: OptimizationReadinessReceipt,
    snapshot: PortfolioSnapshotRef | None,
    mapping: PortfolioModelMapping | None,
    input_contract: OptimizationInputContract | None,
    contract: ModelConsumptionContract | None,
    version: MMMModelVersion | None,
) -> ModelConsumptionContract:
    if receipt.status is OptimizationReadinessStatus.REVIEW_REQUIRED:
        raise OptimizationReviewRequiredError(
            "Optimization review is required before native execution."
        )
    if receipt.status is not OptimizationReadinessStatus.OPTIMIZATION_READY:
        raise OptimizationNotReadyError(
            "Native fixed-budget optimization requires OPTIMIZATION_READY."
        )
    if mapping is None or input_contract is None or contract is None or version is None:
        raise OptimizationReadinessStaleError("Optimization readiness is stale.")
    if receipt.model_version_id != version.model_version_id:
        raise OptimizationReadinessStaleError(
            "Accepted model no longer matches the readiness receipt."
        )
    if receipt_is_stale(
        receipt,
        portfolio_fingerprint=None if snapshot is None else snapshot.fingerprint,
        model_fingerprint=None if contract is None else contract.fingerprint,
        mapping_fingerprint=mapping.fingerprint,
    ):
        raise OptimizationReadinessStaleError("Optimization readiness is stale.")
    if (
        receipt.mapping_fingerprint
        and receipt.mapping_fingerprint != mapping.fingerprint
    ):
        raise OptimizationReadinessStaleError("Portfolio-model mapping changed after readiness.")
    if (
        receipt.input_contract_fingerprint
        and receipt.input_contract_fingerprint != input_contract.fingerprint
    ):
        raise OptimizationReadinessStaleError(
            "Optimization input contract changed after readiness."
        )
    if (
        snapshot is not None
        and input_contract.portfolio_fingerprint
        and snapshot.fingerprint != input_contract.portfolio_fingerprint
    ):
        raise OptimizationReadinessStaleError("Approved plan version changed after readiness.")
    rebound = bind_projection_to_accepted_model(contract, version)
    if any(
        issue.code is OptimizationIssueCode.MODEL_CONSUMPTION_PROJECTION_STALE
        for issue in rebound.issues
    ):
        raise OptimizationReadinessStaleError(
            "Planning consumption projection is stale versus accepted MMM."
        )
    if not rebound.optimizer_artifact_ref and not rebound.response_evidence_ref:
        raise ModelArtifactUnavailableError("Accepted model optimizer artifact is unavailable.")
    return rebound


def home_overlay_status(
    store: OptimizationMetadataStore, *, tenant_id: str, project_id: str
) -> str | None:
    run = store.latest_run(tenant_id=tenant_id, project_id=project_id)
    if run is not None:
        if run.status is OptimizationRunStatus.COMPLETE:
            return "OPTIMIZATION_COMPLETE"
        if run.status in RUNNING_OPTIMIZATION_STATUSES:
            return "OPTIMIZATION_RUNNING"
    receipt = store.latest_receipt(tenant_id=tenant_id, project_id=project_id)
    if receipt is None:
        return None
    return receipt.status.value
