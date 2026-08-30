"""Simulation job entry. Restores authority from Firestore by run id only."""

from __future__ import annotations

import os

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "budget_array",
        "revenue_array",
        "draw_array",
        "posterior_samples",
        "allocations",
        "tenant_id",
        "gcs_uri",
        "model_path",
    }
)


def execute_server_owned_request(payload: dict[str, object]) -> None:
    if FORBIDDEN_REQUEST_KEYS.intersection(payload):
        raise RuntimeError("Simulation worker rejected untrusted request keys.")
    run_id = payload.get("simulation_run_id") or os.environ.get("PREM3_SIMULATION_RUN_ID")
    if not run_id:
        raise RuntimeError("Simulation worker requires PREM3_SIMULATION_RUN_ID.")
