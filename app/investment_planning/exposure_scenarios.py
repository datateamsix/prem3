"""Bounded exposure risk scenarios. Assumptions, not causal curve edits."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import SensitiveDataClass
from app.investment_planning.exposure_metrics import get_metric_definition
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.ids import new_exposure_scenario_id


class ExposureRiskScenarioAssumption(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    metric_id: str
    delta_kind: str
    delta_ref: str
    rationale: str


class ExposureRiskScenario(FrozenModel):
    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    scenario_id: str
    project_id: str
    period: str
    scope: str
    assumptions: tuple[ExposureRiskScenarioAssumption, ...]
    metric_definition_fingerprints: tuple[str, ...]
    source_rationale: str
    created_at: datetime
    fingerprint: str


def pin_exposure_risk_scenario(
    *,
    project_id: str,
    period: str,
    scope: str,
    source_rationale: str,
    assumptions: tuple[tuple[str, str, str, str], ...],
    created_at: datetime,
) -> ExposureRiskScenario:
    """assumptions: (metric_id, delta_kind, delta_ref, rationale). Values stay in delta_ref."""
    rows: list[ExposureRiskScenarioAssumption] = []
    fingerprints: list[str] = []
    for metric_id, delta_kind, delta_ref, rationale in assumptions:
        definition = get_metric_definition(metric_id)
        fingerprints.append(definition.fingerprint)
        rows.append(
            ExposureRiskScenarioAssumption(
                metric_id=metric_id,
                delta_kind=delta_kind,
                delta_ref=delta_ref,
                rationale=rationale,
            )
        )
    scenario_id = new_exposure_scenario_id()
    fingerprint = metadata_fingerprint(
        {
            "scenario_id": scenario_id,
            "project_id": project_id,
            "period": period,
            "scope": scope,
            "assumptions": tuple(item.model_dump() for item in rows),
            "definitions": tuple(fingerprints),
        }
    )
    return ExposureRiskScenario(
        scenario_id=scenario_id,
        project_id=project_id,
        period=period,
        scope=scope,
        assumptions=tuple(rows),
        metric_definition_fingerprints=tuple(fingerprints),
        source_rationale=source_rationale,
        created_at=created_at,
        fingerprint=fingerprint,
    )


BOUNDED_EXAMPLE_DELTAS: tuple[tuple[str, str, str], ...] = (
    ("COST_PER_QUALIFIED_EXPOSURE", "percent", "cpm_plus_10"),
    ("VIEWABILITY_RATE", "percent", "viewability_minus_8"),
    ("INCREMENTAL_REACH", "percent", "incremental_reach_minus_15"),
    ("IVT_RATE", "pp", "ivt_plus_3pp"),
    ("IN_TARGET_RATE", "percent", "audience_match_minus_10"),
)
