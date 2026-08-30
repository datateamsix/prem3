"""GCS persistence for amount-bearing assumption and constraint payloads."""

from __future__ import annotations

import json
from typing import Any

from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
)
from app.service.object_store import ObjectStore


def assumption_object_name(assumption_set_id: str) -> str:
    return f"assumption_set_{assumption_set_id}"


def constraint_object_name(constraint_set_id: str) -> str:
    return f"constraint_set_{constraint_set_id}"


def write_json_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    object_name: str,
    document: dict[str, Any],
) -> str | None:
    data = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    meta = store.write_bytes(
        bucket=bucket,
        object_name=object_name,
        data=data,
        content_type="application/json",
    )
    return meta.generation


def read_json_artifact(
    *, store: ObjectStore, bucket: str, object_name: str
) -> dict[str, Any] | None:
    raw = store.read_bytes(bucket=bucket, object_name=object_name)
    if raw is None:
        return None
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        return None
    return document


def write_assumption_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    assumptions: FutureScenarioAssumptions,
) -> tuple[str, str | None]:
    object_name = assumption_object_name(assumptions.assumption_set_id)
    generation = write_json_artifact(
        store=store,
        bucket=bucket,
        object_name=object_name,
        document=assumptions.model_dump(mode="json"),
    )
    return object_name, generation


def write_constraint_artifact(
    *,
    store: ObjectStore,
    bucket: str,
    constraint_set: OptimizationConstraintSet,
) -> tuple[str, str | None]:
    object_name = constraint_object_name(constraint_set.constraint_set_id)
    generation = write_json_artifact(
        store=store,
        bucket=bucket,
        object_name=object_name,
        document=constraint_set.model_dump(mode="json"),
    )
    return object_name, generation


def read_assumption_artifact(
    *, store: ObjectStore, bucket: str, object_name: str
) -> FutureScenarioAssumptions | None:
    document = read_json_artifact(store=store, bucket=bucket, object_name=object_name)
    if document is None:
        return None
    return FutureScenarioAssumptions.model_validate(document)


def read_constraint_artifact(
    *, store: ObjectStore, bucket: str, object_name: str
) -> OptimizationConstraintSet | None:
    document = read_json_artifact(store=store, bucket=bucket, object_name=object_name)
    if document is None:
        return None
    return OptimizationConstraintSet.model_validate(document)
