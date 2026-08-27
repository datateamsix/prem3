"""Immutable ScenarioArtifact from a completed OptimizationRun result."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.investment_optimization.artifact import read_back_result
from app.investment_optimization.contracts import (
    OptimizationResultPayload,
    OptimizationRun,
    ScenarioArtifact,
)
from app.investment_optimization.enums import (
    SCENARIO_SCHEMA_VERSION,
    OptimizationAmountKind,
    OptimizationRunStatus,
    ScenarioStatus,
    ScenarioType,
)
from app.investment_optimization.errors import (
    ResultReadbackFailedError,
    ScenarioRequiresCompletedOptimizationError,
)
from app.investment_optimization.ids import new_scenario_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.service.object_store import ObjectStore


def scenario_object_name(scenario_id: str) -> str:
    return f"scenario_{scenario_id}"


def _result_body(payload: OptimizationResultPayload) -> dict[str, Any]:
    return {
        "schema_version": SCENARIO_SCHEMA_VERSION,
        "optimization_run_id": payload.optimization_run_id,
        "result_id": payload.result_id,
        "amount_kind": payload.amount_kind.value,
        "currency": payload.currency,
        "fixed_budget": format(payload.fixed_budget, "f"),
        "recommended_total": format(payload.recommended_total, "f"),
        "rows": [
            {
                "model_variable_id": row.model_variable_id,
                "market_id": row.market_id,
                "channel_id": row.channel_id,
                "eligibility": row.eligibility.value,
                "baseline": format(row.baseline, "f"),
                "recommended": format(row.recommended, "f"),
                "absolute_change": format(row.absolute_change, "f"),
                "percent_change": (
                    None if row.percent_change is None else format(row.percent_change, "f")
                ),
                "percent_change_unavailable": row.percent_change_unavailable,
                "constraint_status": row.constraint_status.value,
                "amount_kind": row.amount_kind.value,
            }
            for row in payload.rows
        ],
    }


def write_scenario_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    scenario_id: str,
    payload: OptimizationResultPayload,
) -> tuple[str, str | None, str]:
    body = _result_body(payload)
    body["scenario_id"] = scenario_id
    fingerprint = metadata_fingerprint({key: value for key, value in body.items()})
    body["fingerprint"] = fingerprint
    object_name = scenario_object_name(scenario_id)
    data = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    meta = store.write_bytes(
        bucket=bucket,
        object_name=object_name,
        data=data,
        content_type="application/json",
    )
    return object_name, meta.generation, fingerprint


def read_scenario_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    object_name: str,
    expected_fingerprint: str,
) -> dict[str, Any]:
    raw = store.read_bytes(bucket=bucket, object_name=object_name)
    if raw is None:
        raise ResultReadbackFailedError("Scenario artifact was not found.")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ResultReadbackFailedError("Scenario artifact schema is invalid.")
    stored_fp = document.get("fingerprint")
    body = {key: value for key, value in document.items() if key != "fingerprint"}
    if stored_fp != expected_fingerprint or metadata_fingerprint(body) != expected_fingerprint:
        raise ResultReadbackFailedError("Scenario artifact fingerprint does not match.")
    return document


def require_completed_run(run: OptimizationRun) -> None:
    if run.status is not OptimizationRunStatus.COMPLETE or not run.result_id:
        raise ScenarioRequiresCompletedOptimizationError(
            "Scenario requires a completed optimization result."
        )


def build_scenario_artifact(
    *,
    run: OptimizationRun,
    payload: OptimizationResultPayload,
    source_plan_id: str,
    source_plan_revision: int,
    source_plan_fingerprint: str,
    period: str,
    actor_id: str,
    object_store: ObjectStore,
    artifact_bucket: str,
) -> ScenarioArtifact:
    require_completed_run(run)
    scenario_id = new_scenario_id()
    object_name, generation, artifact_fp = write_scenario_artifact(
        store=object_store,
        bucket=artifact_bucket,
        scenario_id=scenario_id,
        payload=payload,
    )
    metadata = {
        "scenario_id": scenario_id,
        "optimization_run_id": run.optimization_run_id,
        "optimization_result_ref": run.result_id,
        "source_plan_id": source_plan_id,
        "source_plan_revision": source_plan_revision,
        "source_plan_fingerprint": source_plan_fingerprint,
        "baseline_fingerprint": run.plan_version_fingerprint or "",
        "recommendation_fingerprint": payload.fingerprint,
        "artifact_fingerprint": artifact_fp,
        "amount_kind": OptimizationAmountKind.MODEL_RECOMMENDED.value,
    }
    now = datetime.now(UTC)
    return ScenarioArtifact(
        scenario_id=scenario_id,
        tenant_id=run.tenant_id,
        project_id=run.project_id,
        scenario_type=ScenarioType.OPTIMIZER_RECOMMENDATION,
        status=ScenarioStatus.AVAILABLE,
        source_plan_id=source_plan_id,
        source_plan_revision=source_plan_revision,
        source_plan_fingerprint=source_plan_fingerprint,
        optimization_run_id=run.optimization_run_id,
        optimization_result_ref=run.result_id or "",
        baseline_fingerprint=run.plan_version_fingerprint or "",
        recommendation_fingerprint=payload.fingerprint,
        period=period,
        currency=payload.currency,
        amount_kind=OptimizationAmountKind.MODEL_RECOMMENDED,
        artifact_bucket=artifact_bucket,
        artifact_object_name=object_name,
        artifact_generation=generation,
        artifact_fingerprint=artifact_fp,
        created_at=now,
        created_by=actor_id,
        fingerprint=metadata_fingerprint(metadata),
    )


def load_completed_result(
    *,
    run: OptimizationRun,
    object_store: ObjectStore,
    expected_keys: set[str],
    result_ref,
) -> OptimizationResultPayload:
    require_completed_run(run)
    if result_ref is None:
        raise ScenarioRequiresCompletedOptimizationError(
            "Scenario requires a completed optimization result."
        )
    return read_back_result(
        store=object_store,
        bucket=result_ref.artifact_bucket,
        object_name=result_ref.artifact_object_name,
        expected_fingerprint=result_ref.result_fingerprint,
        expected_keys=expected_keys,
    )
