"""Read-back verification and current-view advancement."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.runtime_contracts import MTAFailureClass, MTARunStatus


class ReadbackError(RuntimeError):
    failure_class = MTAFailureClass.BIGQUERY_READBACK_ERROR


class InMemoryResultStore:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.current_views: dict[str, str] = {}
        self.verified_runs: set[str] = set()

    def write(self, table: str, rows: list[dict[str, Any]]) -> str:
        self.tables[table] = list(rows)
        return canonical_fingerprint({"table": table, "rows": rows})

    def read_back(self, table: str) -> list[dict[str, Any]]:
        if table not in self.tables:
            raise ReadbackError(f"Missing required output table {table}")
        return list(self.tables[table])

    def verify_required(
        self, *, run_id: str, required_tables: list[str] | tuple[str, ...]
    ) -> dict[str, str]:
        fingerprints: dict[str, str] = {}
        for table in required_tables:
            rows = self.read_back(table)
            fingerprints[table] = canonical_fingerprint({"table": table, "n": len(rows)})
        self.verified_runs.add(run_id)
        return fingerprints

    def advance_current(
        self, *, run_id: str, mapping: dict[str, str], run_status: MTARunStatus
    ) -> None:
        if run_status is not MTARunStatus.SUCCEEDED:
            raise ReadbackError("Current views advance only after SUCCEEDED.")
        if run_id not in self.verified_runs:
            raise ReadbackError("Current views require verified read-back.")
        self.current_views.update(mapping)
