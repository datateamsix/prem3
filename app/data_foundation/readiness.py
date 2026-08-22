"""Deterministic DF readiness. Gemini cannot emit these states."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import (
    DataFoundationReadyReceipt,
    SourceAssessment,
    SourceBinding,
    SourceFoundationReceipt,
    TransformationReceipt,
)
from app.data_foundation.enums import (
    DataFoundationReadyStatus,
    QualityStatus,
    SourceFoundationStatus,
)
from app.data_foundation.ids import new_receipt_id
from app.data_foundation.quality.engine import has_source_blocker
from app.data_foundation.warehouse import FoundationWarehouse


def evaluate_source_foundation(
    *,
    context: DataFoundationContext,
    binding: SourceBinding,
    assessment: SourceAssessment,
    governance_import_ready: bool,
    transform_receipt: TransformationReceipt | None,
    currency_known: bool,
    timezone_known: bool,
) -> SourceFoundationReceipt:
    """Emit FOUNDATION_SOURCE_* only. Gemini cannot emit these states."""
    blockers = has_source_blocker(assessment)
    freshness_known = assessment.operational.freshness_known
    contract_ok = assessment.contract.required_fields_present
    transform_ok = transform_receipt is not None and transform_receipt.status == "APPLIED"
    if not binding.contract.required_fields:
        transform_ok = transform_receipt is None or transform_receipt.status == "APPLIED"
    reviews = [
        item.check_id
        for item in assessment.quality.checks
        if item.status is QualityStatus.REVIEW
    ]
    ready = (
        governance_import_ready
        and assessment.operational.access_works
        and contract_ok
        and not blockers
        and freshness_known
        and currency_known
        and timezone_known
        and (transform_ok or not _requires_transform(assessment))
        and binding.lifecycle_state != "RETIRED"
    )
    status = (
        SourceFoundationStatus.FOUNDATION_SOURCE_READY
        if ready
        else SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY
    )
    return SourceFoundationReceipt(
        receipt_id=new_receipt_id(),
        tenant_id=context.tenant_id,
        workspace_id=context.workspace_id,
        source_ids=(binding.source_id,),
        plan_id=transform_receipt.plan_id if transform_receipt else None,
        executed_at=datetime.now(UTC),
        executed_by=context.actor_id,
        status=status.value,
        status_code=status,
        governance_import_ready=governance_import_ready,
        premodel_review_remaining=bool(reviews),
        premodel_review_findings=tuple(reviews),
        unresolved_findings=tuple(
            item.check_id
            for item in assessment.quality.checks
            if item.status in {QualityStatus.BLOCKER, QualityStatus.REVIEW, QualityStatus.UNKNOWN}
        ),
    )


def _requires_transform(assessment: SourceAssessment) -> bool:
    return any(item.status is QualityStatus.BLOCKER for item in assessment.quality.checks)


def evaluate_data_foundation_ready(
    *,
    context: DataFoundationContext,
    warehouse: FoundationWarehouse,
    source_receipts: list[SourceFoundationReceipt],
    required_source_ids: list[str],
    allowed_exceptions: set[str],
    foundation_receipt_exists: bool,
    approval_valid: bool,
) -> DataFoundationReadyReceipt:
    project = context.destination_project_id
    if project is None:
        status = DataFoundationReadyStatus.NOT_READY
        ready_count = 0
        exceptions: tuple[str, ...] = ()
    else:
        dataset_ok = f"{project}.prem3_modeling" in warehouse.datasets
        canonical = {
            f"{project}.prem3_modeling.canonical_kpi",
            f"{project}.prem3_modeling.canonical_media",
            f"{project}.prem3_modeling.source_registry",
        }
        assets_ok = all(warehouse.get_table(name) is not None for name in canonical)
        ready_ids = {
            item.source_ids[0]
            for item in source_receipts
            if item.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY
            and item.governance_import_ready
        }
        missing = [item for item in required_source_ids if item not in ready_ids]
        exceptions = tuple(item for item in missing if item in allowed_exceptions)
        blocking = [item for item in missing if item not in allowed_exceptions]
        ready = (
            dataset_ok
            and assets_ok
            and approval_valid
            and foundation_receipt_exists
            and not blocking
            and bool(source_receipts)
        )
        status = (
            DataFoundationReadyStatus.DATA_FOUNDATION_READY
            if ready
            else DataFoundationReadyStatus.NOT_READY
        )
        ready_count = len(ready_ids)
    m2_11 = bool(source_receipts) and all(item.governance_import_ready for item in source_receipts)
    return DataFoundationReadyReceipt(
        receipt_id=new_receipt_id(),
        tenant_id=context.tenant_id,
        workspace_id=context.workspace_id,
        source_ids=tuple(required_source_ids),
        executed_at=datetime.now(UTC),
        executed_by=context.actor_id,
        status=status.value,
        status_code=status,
        required_sources_ready=ready_count,
        typed_exceptions=exceptions,
        m2_11_import_ready=m2_11,
        foundation_source_ready_count=ready_count,
    )
