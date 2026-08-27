"""Immutable GCS optimization result artifact plus read-back verification."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app.investment_optimization.contracts import (
    OptimizationOutcomeEstimate,
    OptimizationResultPayload,
    OptimizationResultRow,
)
from app.investment_optimization.enums import (
    ARTIFACT_SCHEMA_VERSION,
    ModelVariableOptimizationEligibility,
    OptimizationAmountKind,
    OptimizationRunKind,
    OptimizerConstraintStatus,
)
from app.investment_optimization.errors import ResultReadbackFailedError
from app.investment_planning.actuals import round_money
from app.investment_planning.fingerprint import metadata_fingerprint
from app.service.object_store import ObjectStore


def artifact_object_name(optimization_run_id: str) -> str:
    return f"optimization_result_{optimization_run_id}"


def _row_payload(row: OptimizationResultRow) -> dict[str, Any]:
    return {
        "model_variable_id": row.model_variable_id,
        "market_id": row.market_id,
        "channel_id": row.channel_id,
        "eligibility": row.eligibility.value,
        "baseline": format(row.baseline, "f"),
        "recommended": format(row.recommended, "f"),
        "absolute_change": format(row.absolute_change, "f"),
        "percent_change": None if row.percent_change is None else format(row.percent_change, "f"),
        "percent_change_unavailable": row.percent_change_unavailable,
        "constraint_status": row.constraint_status.value,
        "amount_kind": row.amount_kind.value,
        "outcome_estimates": [
            {
                "name": item.name,
                "value": item.value,
                "amount_kind": item.amount_kind.value,
            }
            for item in row.outcome_estimates
        ],
    }


def artifact_document(payload: OptimizationResultPayload) -> dict[str, Any]:
    body = {
        "schema_version": payload.schema_version,
        "optimization_run_id": payload.optimization_run_id,
        "result_id": payload.result_id,
        "run_kind": payload.run_kind.value,
        "amount_kind": payload.amount_kind.value,
        "currency": payload.currency,
        "fixed_budget": format(payload.fixed_budget, "f"),
        "recommended_total": format(payload.recommended_total, "f"),
        "rows": [_row_payload(row) for row in payload.rows],
    }
    fingerprint = metadata_fingerprint(body)
    body["fingerprint"] = fingerprint
    return body


def result_fingerprint(payload: OptimizationResultPayload) -> str:
    return str(artifact_document(payload)["fingerprint"])


def write_result_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    payload: OptimizationResultPayload,
) -> tuple[str, str | None]:
    object_name = artifact_object_name(payload.optimization_run_id)
    document = artifact_document(payload)
    data = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    meta = store.write_bytes(
        bucket=bucket,
        object_name=object_name,
        data=data,
        content_type="application/json",
    )
    return object_name, meta.generation


def _decimal(value: object, *, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ResultReadbackFailedError(f"Artifact field {field} must be a Decimal string.")
    return round_money(Decimal(value))


def _payload_from_document(document: dict[str, Any]) -> OptimizationResultPayload:
    rows: list[OptimizationResultRow] = []
    for item in document["rows"]:
        estimates = tuple(
            OptimizationOutcomeEstimate(
                name=str(est["name"]),
                value=str(est["value"]),
                amount_kind=OptimizationAmountKind(str(est.get("amount_kind", "MODEL_ESTIMATE"))),
            )
            for est in item.get("outcome_estimates") or ()
        )
        percent_raw = item.get("percent_change")
        rows.append(
            OptimizationResultRow(
                model_variable_id=str(item["model_variable_id"]),
                market_id=str(item.get("market_id") or ""),
                channel_id=str(item.get("channel_id") or ""),
                eligibility=ModelVariableOptimizationEligibility(str(item["eligibility"])),
                baseline=_decimal(item["baseline"], field="baseline"),
                recommended=_decimal(item["recommended"], field="recommended"),
                absolute_change=_decimal(item["absolute_change"], field="absolute_change"),
                percent_change=(
                    None if percent_raw is None else _decimal(percent_raw, field="percent_change")
                ),
                percent_change_unavailable=bool(item.get("percent_change_unavailable")),
                constraint_status=OptimizerConstraintStatus(
                    str(item.get("constraint_status") or "WITHIN_BOUNDS")
                ),
                amount_kind=OptimizationAmountKind(
                    str(item.get("amount_kind") or "MODEL_RECOMMENDED")
                ),
                outcome_estimates=estimates,
            )
        )
    return OptimizationResultPayload(
        optimization_run_id=str(document["optimization_run_id"]),
        result_id=str(document["result_id"]),
        run_kind=OptimizationRunKind(str(document.get("run_kind") or "FIXED_BUDGET")),
        amount_kind=OptimizationAmountKind(str(document.get("amount_kind") or "MODEL_RECOMMENDED")),
        currency=str(document["currency"]),
        fixed_budget=_decimal(document["fixed_budget"], field="fixed_budget"),
        recommended_total=_decimal(document["recommended_total"], field="recommended_total"),
        rows=tuple(rows),
        fingerprint=str(document["fingerprint"]),
        schema_version=str(document["schema_version"]),
    )


def read_back_result(
    *,
    store: ObjectStore,
    bucket: str,
    object_name: str,
    expected_fingerprint: str,
    expected_keys: set[str],
    expected_total: Decimal | None = None,
) -> OptimizationResultPayload:
    raw = store.read_bytes(bucket=bucket, object_name=object_name)
    if raw is None:
        raise ResultReadbackFailedError("Optimization result artifact was not found.")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResultReadbackFailedError("Optimization result artifact is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise ResultReadbackFailedError("Optimization result artifact schema is invalid.")
    if document.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ResultReadbackFailedError("Optimization result artifact schema version is invalid.")
    stored_fp = document.get("fingerprint")
    body = {key: value for key, value in document.items() if key != "fingerprint"}
    computed = metadata_fingerprint(body)
    if stored_fp != expected_fingerprint or computed != expected_fingerprint:
        raise ResultReadbackFailedError("Optimization result artifact fingerprint does not match.")
    rows_raw = document.get("rows")
    if not isinstance(rows_raw, list):
        raise ResultReadbackFailedError("Optimization result artifact rows are invalid.")
    keys = {str(row.get("model_variable_id")) for row in rows_raw if isinstance(row, dict)}
    if keys != expected_keys:
        raise ResultReadbackFailedError(
            "Optimization result artifact key set does not match mapped variables."
        )
    recommended_total = _decimal(document.get("recommended_total"), field="recommended_total")
    fixed_budget = _decimal(document.get("fixed_budget"), field="fixed_budget")
    target = round_money(expected_total) if expected_total is not None else fixed_budget
    if recommended_total != target or recommended_total != fixed_budget:
        raise ResultReadbackFailedError(
            "Optimization result artifact total does not equal the fixed budget."
        )
    return _payload_from_document(document)
