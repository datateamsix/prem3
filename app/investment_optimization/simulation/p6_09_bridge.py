"""Load P6-09A draw artifacts into existing RiskFrontierService.evaluate tuples."""

from __future__ import annotations

from app.investment_optimization.simulation.artifacts import read_draw_artifact
from app.service.object_store import ObjectStore


def draws_for_evaluate(
    *,
    object_store: ObjectStore,
    bucket: str,
    artifact_ref: str,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    frame = read_draw_artifact(
        object_store=object_store, bucket=bucket, object_name=artifact_ref
    )
    candidate = tuple(float(value) for value in frame["candidate_outcome"].tolist())
    baseline = tuple(float(value) for value in frame["baseline_outcome"].tolist())
    return candidate, baseline
