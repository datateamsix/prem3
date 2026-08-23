"""Pure EvaluationDispatch claim decisions. Stores apply them atomically."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.control_plane.models import DispatchStatus, EvaluationDispatch

CLAIM_LEASE = timedelta(seconds=7200)
TERMINAL_STATUSES = frozenset({DispatchStatus.SUCCEEDED, DispatchStatus.FAILED_TERMINAL})
_UNSET: Any = object()


class DispatchClaimOutcome(StrEnum):
    CLAIMED = "claimed"
    RECLAIMED = "reclaimed"
    DUPLICATE_NOOP = "duplicate_noop"
    DENIED = "denied"
    ALREADY_TERMINAL = "already_terminal"


def decide_claim(
    dispatch: EvaluationDispatch,
    *,
    owner: str,
    execution_name: str,
    now: datetime,
    lease: timedelta = CLAIM_LEASE,
) -> tuple[DispatchClaimOutcome, EvaluationDispatch]:
    """Decide whether this Cloud Run execution may own the Evaluation.

    Same execution may reclaim. A different active owner is fail-closed.
    Expired claims may be recovered.
    """
    if dispatch.status in TERMINAL_STATUSES:
        return DispatchClaimOutcome.ALREADY_TERMINAL, dispatch
    same_execution = bool(execution_name) and dispatch.cloud_run_execution_name == execution_name
    active = (
        dispatch.claim_owner is not None
        and dispatch.claim_expires_at is not None
        and dispatch.claim_expires_at > now
    )
    if same_execution:
        updated = _with_updates(
            dispatch,
            now=now,
            status=DispatchStatus.RUNNING,
            claim_owner=owner,
            claim_expires_at=now + lease,
            cloud_run_execution_name=execution_name,
            started_at=dispatch.started_at or now,
            attempt_count=dispatch.attempt_count + (0 if dispatch.claim_owner == owner else 1),
        )
        return DispatchClaimOutcome.RECLAIMED, updated
    if active:
        return DispatchClaimOutcome.DENIED, dispatch
    updated = _with_updates(
        dispatch,
        now=now,
        status=DispatchStatus.RUNNING,
        claim_owner=owner,
        claim_expires_at=now + lease,
        cloud_run_execution_name=execution_name,
        started_at=dispatch.started_at or now,
        attempt_count=dispatch.attempt_count + 1,
    )
    return DispatchClaimOutcome.CLAIMED, updated


def mark_launching(
    dispatch: EvaluationDispatch,
    *,
    now: datetime,
    execution_name: str | None,
) -> EvaluationDispatch:
    if dispatch.status in TERMINAL_STATUSES or dispatch.status is DispatchStatus.RUNNING:
        return dispatch
    return _with_updates(
        dispatch,
        now=now,
        status=DispatchStatus.LAUNCHING,
        launched_at=dispatch.launched_at or now,
        cloud_run_execution_name=execution_name or dispatch.cloud_run_execution_name,
    )


def mark_queued(
    dispatch: EvaluationDispatch,
    *,
    now: datetime,
    cloud_task_name: str,
) -> EvaluationDispatch:
    return _with_updates(
        dispatch,
        now=now,
        status=DispatchStatus.QUEUED,
        cloud_task_name=cloud_task_name,
    )


def mark_enqueue_failure(
    dispatch: EvaluationDispatch,
    *,
    now: datetime,
    error_code: str,
) -> EvaluationDispatch:
    return _with_updates(
        dispatch,
        now=now,
        status=DispatchStatus.FAILED_RETRYABLE,
        failed_at=now,
        last_error_code=error_code,
        last_error_detail=None,
    )


def mark_succeeded(dispatch: EvaluationDispatch, *, now: datetime) -> EvaluationDispatch:
    return _with_updates(
        dispatch,
        now=now,
        status=DispatchStatus.SUCCEEDED,
        completed_at=now,
        claim_owner=None,
        claim_expires_at=None,
        last_error_code=None,
        last_error_detail=None,
    )


def mark_failed(
    dispatch: EvaluationDispatch,
    *,
    now: datetime,
    retryable: bool,
    error_code: str,
) -> EvaluationDispatch:
    status = (
        DispatchStatus.FAILED_RETRYABLE if retryable else DispatchStatus.FAILED_TERMINAL
    )
    return _with_updates(
        dispatch,
        now=now,
        status=status,
        failed_at=now,
        completed_at=now if not retryable else dispatch.completed_at,
        claim_owner=None if not retryable else dispatch.claim_owner,
        claim_expires_at=None if not retryable else dispatch.claim_expires_at,
        last_error_code=error_code,
        last_error_detail=None,
    )


def utc_now() -> datetime:
    return datetime.now(UTC)


def _with_updates(
    dispatch: EvaluationDispatch,
    *,
    now: datetime,
    status: DispatchStatus | None = None,
    attempt_count: int | None = None,
    cloud_task_name: str | None = None,
    cloud_run_execution_name: str | None = None,
    claim_owner: str | None = _UNSET,
    claim_expires_at: datetime | None = _UNSET,
    launched_at: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    failed_at: datetime | None = None,
    last_error_code: str | None = _UNSET,
    last_error_detail: str | None = _UNSET,
) -> EvaluationDispatch:
    payload = dispatch.model_dump()
    payload["updated_at"] = now
    if status is not None:
        payload["status"] = status
    if attempt_count is not None:
        payload["attempt_count"] = attempt_count
    if cloud_task_name is not None:
        payload["cloud_task_name"] = cloud_task_name
    if cloud_run_execution_name is not None:
        payload["cloud_run_execution_name"] = cloud_run_execution_name
    if claim_owner is not _UNSET:
        payload["claim_owner"] = claim_owner
    if claim_expires_at is not _UNSET:
        payload["claim_expires_at"] = claim_expires_at
    if launched_at is not None:
        payload["launched_at"] = launched_at
    if started_at is not None:
        payload["started_at"] = started_at
    if completed_at is not None:
        payload["completed_at"] = completed_at
    if failed_at is not None:
        payload["failed_at"] = failed_at
    if last_error_code is not _UNSET:
        payload["last_error_code"] = last_error_code
    if last_error_detail is not _UNSET:
        payload["last_error_detail"] = last_error_detail
    return EvaluationDispatch.model_validate(payload)
