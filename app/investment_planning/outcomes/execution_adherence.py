"""Execution adherence. Missing actuals are not zero spend."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.investment_optimization.enums import AdherenceClass, ExecutionAdherenceStatus
from app.investment_optimization.errors import (
    ExecutionAdherenceNotComputableError,
    ExecutionEvidenceIncompleteError,
)
from app.investment_optimization.ids import new_execution_adherence_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import ExecutionAdherence
from app.investment_planning.portfolio import variance_percent


def compute_execution_adherence(
    *,
    tenant_id: str,
    project_id: str,
    approved_plan_ref: str,
    planned: dict[str, Decimal | None],
    actual: dict[str, Decimal | None],
    actual_spend_source_ref: str | None = None,
    exposure_handoff_ref: str | None = None,
    require_complete: bool = False,
) -> ExecutionAdherence:
    if not planned:
        raise ExecutionAdherenceNotComputableError(
            "Execution adherence requires a planned portfolio."
        )
    comparable = 0
    incomplete = 0
    for key, planned_value in planned.items():
        actual_value = actual.get(key)
        if planned_value is None or actual_value is None:
            incomplete += 1
            continue
        comparable += 1
        _ = variance_percent(planned_value, actual_value)
    limitations: list[str] = []
    if incomplete:
        limitations.append("EXECUTION_ADHERENCE_INCOMPLETE")
    if not actual:
        limitations.append("EXECUTION_EVIDENCE_INCOMPLETE")
        incomplete = max(incomplete, len(planned))
    if require_complete and (incomplete or not actual):
        raise ExecutionEvidenceIncompleteError(
            "Actual spend is incomplete; missing actuals are not zero execution."
        )
    status = (
        ExecutionAdherenceStatus.INCOMPLETE
        if incomplete or not actual
        else ExecutionAdherenceStatus.COMPLETE
    )
    adherence = (
        AdherenceClass.INCOMPLETE
        if status is ExecutionAdherenceStatus.INCOMPLETE
        else AdherenceClass.MATCH
    )
    created = datetime.now(UTC)
    payload = {
        "plan": approved_plan_ref,
        "comparable": comparable,
        "incomplete": incomplete,
        "status": status.value,
    }
    return ExecutionAdherence(
        execution_adherence_id=new_execution_adherence_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        approved_plan_ref=approved_plan_ref,
        actual_spend_source_ref=actual_spend_source_ref,
        exposure_handoff_ref=exposure_handoff_ref,
        status=status,
        adherence_class=adherence,
        comparable_line_count=comparable,
        incomplete_line_count=incomplete,
        limitations=tuple(limitations),
        fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )
