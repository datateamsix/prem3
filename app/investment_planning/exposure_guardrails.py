"""Exposure guardrails and qualification receipts. P6-08 owns qualification."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import (
    ExposureGuardrailRole,
    ExposureOptimizationRole,
    SensitiveDataClass,
)
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.ids import new_exposure_guardrail_id, new_exposure_qualification_id


def map_guardrail_role(role: ExposureGuardrailRole) -> ExposureOptimizationRole:
    if role is ExposureGuardrailRole.MODEL_INPUT:
        return ExposureOptimizationRole.MODEL_INPUT
    if role is ExposureGuardrailRole.CONSTRAINT:
        return ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
    return ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL


class ExposureGuardrail(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    guardrail_id: str
    project_id: str
    metric_id: str
    entity_scope: str
    market_id: str | None = None
    channel_id: str | None = None
    operator: str
    threshold_ref: str
    role: ExposureGuardrailRole
    authority: str
    status: str
    source_ref: str
    fingerprint: str


class ExposureGuardrailQualificationReceipt(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    qualification_id: str
    guardrail_id: str
    project_id: str
    requested_role: ExposureOptimizationRole
    assigned_role: ExposureOptimizationRole
    metric_valid: bool
    source_current: bool
    entity_mapping_valid: bool
    coverage_sufficient: bool
    role_supported: bool
    spend_quality_relationship: bool
    model_input_supported: bool
    issues: tuple[str, ...] = ()
    created_at: datetime
    fingerprint: str


def new_guardrail(
    *,
    project_id: str,
    metric_id: str,
    role: ExposureGuardrailRole,
    operator: str = "lte",
    threshold_ref: str = "policy",
    entity_scope: str = "channel",
    market_id: str | None = None,
    channel_id: str | None = None,
    authority: str = "HUMAN_CONFIRMED",
    status: str = "ACTIVE",
    source_ref: str = "policy",
) -> ExposureGuardrail:
    guardrail_id = new_exposure_guardrail_id()
    fingerprint = metadata_fingerprint(
        {
            "guardrail_id": guardrail_id,
            "metric_id": metric_id,
            "role": role.value,
            "operator": operator,
            "threshold_ref": threshold_ref,
            "entity_scope": entity_scope,
        }
    )
    return ExposureGuardrail(
        guardrail_id=guardrail_id,
        project_id=project_id,
        metric_id=metric_id,
        entity_scope=entity_scope,
        market_id=market_id,
        channel_id=channel_id,
        operator=operator,
        threshold_ref=threshold_ref,
        role=role,
        authority=authority,
        status=status,
        source_ref=source_ref,
        fingerprint=fingerprint,
    )


def build_qualification_receipt(
    *,
    guardrail: ExposureGuardrail,
    requested_role: ExposureOptimizationRole,
    assigned_role: ExposureOptimizationRole,
    metric_valid: bool,
    source_current: bool,
    entity_mapping_valid: bool,
    coverage_sufficient: bool,
    role_supported: bool,
    spend_quality_relationship: bool,
    model_input_supported: bool,
    issues: tuple[str, ...],
    created_at: datetime,
) -> ExposureGuardrailQualificationReceipt:
    qualification_id = new_exposure_qualification_id()
    fingerprint = metadata_fingerprint(
        {
            "qualification_id": qualification_id,
            "guardrail_id": guardrail.guardrail_id,
            "requested_role": requested_role.value,
            "assigned_role": assigned_role.value,
            "issues": issues,
        }
    )
    return ExposureGuardrailQualificationReceipt(
        qualification_id=qualification_id,
        guardrail_id=guardrail.guardrail_id,
        project_id=guardrail.project_id,
        requested_role=requested_role,
        assigned_role=assigned_role,
        metric_valid=metric_valid,
        source_current=source_current,
        entity_mapping_valid=entity_mapping_valid,
        coverage_sufficient=coverage_sufficient,
        role_supported=role_supported,
        spend_quality_relationship=spend_quality_relationship,
        model_input_supported=model_input_supported,
        issues=issues,
        created_at=created_at,
        fingerprint=fingerprint,
    )
