"""Presentation-safe Evaluation execution read model. Dispatch success is not MODEL_READY."""

from __future__ import annotations

from app.control_plane.models import (
    DatasetEvaluationRef,
    DispatchStatus,
    EvaluationDispatch,
    EvaluationStatus,
)
from app.publish_execution.model_ready import ModelReadyEvidenceResolver
from app.service.models import EvaluationExecutionView


def compose_execution_view(
    evaluation: DatasetEvaluationRef,
    dispatch: EvaluationDispatch | None,
    *,
    model_ready_resolver: ModelReadyEvidenceResolver | None = None,
) -> EvaluationExecutionView:
    evidence = None
    if model_ready_resolver is not None:
        evidence = model_ready_resolver.resolve(
            tenant_id=evaluation.tenant_id,
            workspace_id=evaluation.workspace_id,
            dataset_id=evaluation.dataset_id,
            run_id=evaluation.run_id,
        )
    model_ready = evidence is not None
    dispatch_status = dispatch.status.value if dispatch is not None else None
    dispatch_succeeded = dispatch is not None and dispatch.status is DispatchStatus.SUCCEEDED
    terminal = bool(
        dispatch is not None
        and dispatch.status in {DispatchStatus.SUCCEEDED, DispatchStatus.FAILED_TERMINAL}
    )
    approval_required = dispatch_succeeded and not model_ready
    outcome = None
    if model_ready:
        outcome = "MODEL_READY"
    elif dispatch is not None and dispatch.status is DispatchStatus.FAILED_TERMINAL:
        outcome = dispatch.last_error_code
    elif approval_required:
        outcome = "WAITING_FOR_APPROVAL"
    return EvaluationExecutionView(
        run_id=evaluation.run_id,
        evaluation_status=evaluation.status.value,
        dispatch_status=dispatch_status,
        execution_started_at=dispatch.started_at if dispatch else None,
        execution_updated_at=dispatch.updated_at if dispatch else evaluation.updated_at,
        execution_completed_at=dispatch.completed_at if dispatch else None,
        current_stage=None,
        terminal=terminal,
        outcome=outcome,
        model_ready=model_ready,
        approval_required=approval_required,
        issue_count=None,
        readiness_receipt_available=model_ready,
        eda_receipt_available=model_ready,
    )


def evaluation_status_is_accepted(evaluation: DatasetEvaluationRef) -> bool:
    return evaluation.status is EvaluationStatus.ACCEPTED
