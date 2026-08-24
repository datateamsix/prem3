"""Queryable BigQuery model ledger. Binary models stay in GCS."""

from __future__ import annotations

from typing import Any, Protocol

BQ_MODEL_LEDGER_TABLES = (
    "mmm_model_versions",
    "mmm_fit_runs",
    "mmm_model_decisions",
    "mmm_model_health",
    "mmm_model_channel_summary",
)


class ModelLedger(Protocol):
    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryModelLedger:
    """Unit/CI ledger. Production writes are versioned/run-scoped BigQuery rows."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            table: [] for table in BQ_MODEL_LEDGER_TABLES
        }

    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if table not in BQ_MODEL_LEDGER_TABLES:
            raise ValueError(f"Unknown model ledger table {table}.")
        stored = dict(row)
        self.rows[table].append(stored)
        return stored
