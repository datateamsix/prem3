"""Deterministic exposure role qualification. Does not mutate P6-07 constraint families."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.contracts import ModelConsumptionContract
from app.investment_planning.enums import ExposureOptimizationRole
from app.investment_planning.errors import ExposureModelInputUnsupportedError
from app.investment_planning.exposure_evidence import ExposureRiskPolicy
from app.investment_planning.exposure_guardrails import (
    ExposureGuardrail,
    ExposureGuardrailQualificationReceipt,
    build_qualification_receipt,
    map_guardrail_role,
)
from app.investment_planning.exposure_metrics import get_metric_definition
from app.investment_planning.exposure_observations import ExposureMetricObservation
from app.investment_planning.identity import (
    require_canonical_channel_id,
    require_canonical_market_id,
)

REACH_FREQUENCY_METRICS = frozenset(
    {"UNIQUE_REACH", "AVERAGE_FREQUENCY", "INCREMENTAL_REACH", "OVER_FREQUENCY_SHARE"}
)


def consumption_supports_exposure_metric(
    contract: ModelConsumptionContract | None, metric_id: str
) -> bool:
    if contract is None:
        return False
    if metric_id not in REACH_FREQUENCY_METRICS:
        return False
    for variable in contract.variables:
        name = f"{variable.model_variable_id} {variable.model_variable_name or ''}".lower()
        if "rf" in name or "reach" in name or "frequency" in name:
            return True
    return False


def policy_has_spend_quality(policy: ExposureRiskPolicy, metric_id: str) -> bool:
    return any(item.metric_id == metric_id for item in policy.spend_quality_relationships)


def qualify_exposure_guardrail(
    guardrail: ExposureGuardrail,
    *,
    observations: tuple[ExposureMetricObservation, ...],
    policy: ExposureRiskPolicy,
    known_market_ids: frozenset[str] | set[str],
    consumption: ModelConsumptionContract | None = None,
    created_at: datetime,
) -> ExposureGuardrailQualificationReceipt:
    issues: list[str] = []
    metric_valid = True
    try:
        get_metric_definition(guardrail.metric_id)
    except Exception:
        metric_valid = False
        issues.append("EXPOSURE_METRIC_NOT_COMPARABLE")
    entity_mapping_valid = True
    if guardrail.market_id:
        try:
            require_canonical_market_id(guardrail.market_id, known_market_ids=known_market_ids)
        except Exception:
            entity_mapping_valid = False
            issues.append("EXPOSURE_ENTITY_MAPPING_REQUIRED")
    if guardrail.channel_id:
        try:
            require_canonical_channel_id(guardrail.channel_id)
        except Exception:
            entity_mapping_valid = False
            issues.append("EXPOSURE_ENTITY_MAPPING_REQUIRED")
    matching = tuple(item for item in observations if item.metric_id == guardrail.metric_id)
    source_current = bool(matching) and all(
        item.freshness.value != "STALE" for item in matching
    )
    if matching and not source_current:
        issues.append("EXPOSURE_DATA_STALE")
    coverage_sufficient = bool(matching)
    if not coverage_sufficient:
        issues.append("EXPOSURE_COVERAGE_INSUFFICIENT")
    requested = map_guardrail_role(guardrail.role)
    model_input_supported = consumption_supports_exposure_metric(consumption, guardrail.metric_id)
    if requested is ExposureOptimizationRole.MODEL_INPUT:
        if guardrail.metric_id not in policy.model_input_metrics or not model_input_supported:
            raise ExposureModelInputUnsupportedError(
                "Exposure metric is not a supported model/media execution input.",
                code="EXPOSURE_MODEL_INPUT_UNSUPPORTED",
            )
        assigned = ExposureOptimizationRole.MODEL_INPUT
        role_supported = True
        spend_quality = False
    elif requested is ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY:
        spend_quality = policy_has_spend_quality(policy, guardrail.metric_id)
        if not spend_quality:
            assigned = ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
            role_supported = False
            issues.append("SPEND_QUALITY_RELATIONSHIP_REQUIRED")
            issues.append("EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED")
        else:
            assigned = ExposureOptimizationRole.CONSTRAINT_OR_FEASIBILITY
            role_supported = True
    else:
        assigned = ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
        role_supported = True
        spend_quality = False
        model_input_supported = False
    if not metric_valid or not entity_mapping_valid:
        issues.append("EXPOSURE_GUARDRAIL_REVIEW_REQUIRED")
        assigned = ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL
        role_supported = False
    return build_qualification_receipt(
        guardrail=guardrail,
        requested_role=requested,
        assigned_role=assigned,
        metric_valid=metric_valid,
        source_current=source_current,
        entity_mapping_valid=entity_mapping_valid,
        coverage_sufficient=coverage_sufficient,
        role_supported=role_supported,
        spend_quality_relationship=spend_quality,
        model_input_supported=model_input_supported,
        issues=tuple(dict.fromkeys(issues)),
        created_at=created_at,
    )


def scenario_guardrail_does_not_mutate_curve(curve: object) -> object:
    """Role C may attach limitations. It must not rewrite a Meridian response curve."""
    return curve
