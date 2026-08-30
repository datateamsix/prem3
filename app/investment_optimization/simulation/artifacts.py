"""Parquet draw artifacts on the customer object store."""

from __future__ import annotations

import io

import pandas as pd

from app.investment_optimization.errors import SimulationArtifactWriteFailedError
from app.investment_optimization.simulation.models import SimulationDrawArtifact
from app.investment_planning.fingerprint import metadata_fingerprint
from app.service.object_store import ObjectStore


def draw_object_name(simulation_run_id: str, candidate_id: str) -> str:
    return f"simulation_draws_{simulation_run_id}_{candidate_id}.parquet"


def write_draw_artifact(
    artifact: SimulationDrawArtifact,
    *,
    object_store: ObjectStore,
    bucket: str,
) -> str:
    frame = pd.DataFrame(
        {
            "draw_id": list(range(artifact.draw_count)),
            "candidate_outcome": list(artifact.candidate_outcomes),
            "baseline_outcome": list(artifact.baseline_outcomes),
            "loss": list(artifact.losses),
        }
    )
    buffer = io.BytesIO()
    try:
        frame.to_parquet(buffer, index=False)
        object_store.write_bytes(
            bucket=bucket,
            object_name=draw_object_name(
                artifact.simulation_run_id, artifact.candidate_portfolio_id
            ),
            data=buffer.getvalue(),
        )
    except Exception as exc:
        raise SimulationArtifactWriteFailedError(
            "Simulation draw artifact could not be written."
        ) from exc
    return draw_object_name(artifact.simulation_run_id, artifact.candidate_portfolio_id)


def read_draw_artifact(
    *,
    object_store: ObjectStore,
    bucket: str,
    object_name: str,
) -> pd.DataFrame:
    payload = object_store.read_bytes(bucket=bucket, object_name=object_name)
    if payload is None:
        raise SimulationArtifactWriteFailedError("Simulation draw artifact was not found.")
    return pd.read_parquet(io.BytesIO(payload))


def artifact_fingerprint(
    *,
    candidate_outcomes: tuple[float, ...],
    baseline_outcomes: tuple[float, ...],
) -> str:
    return metadata_fingerprint(
        {
            "candidate": [round(value, 12) for value in candidate_outcomes],
            "baseline": [round(value, 12) for value in baseline_outcomes],
        }
    )
