"""Read-back verification and current-view advancement."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.bq_executor import client_for_project
from app.modeling.mta.runtime_contracts import MTAFailureClass, MTARunStatus

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - unit tests use InMemoryResultStore
    bigquery = None


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


class BigQueryResultStore:
    """Write/read-back MTA result tables in prem3_modeling."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset: str = "prem3_modeling",
        client: Any | None = None,
    ) -> None:
        self.project_id = project_id
        self.dataset = dataset
        self._client = client or client_for_project(project_id)
        self.verified_runs: set[str] = set()
        self.current_views: dict[str, str] = {}

    def _table(self, name: str) -> str:
        return f"{self.project_id}.{self.dataset}.{name}"

    def write(self, table: str, rows: list[dict[str, Any]]) -> str:
        if bigquery is None:
            raise ReadbackError("google-cloud-bigquery is not installed")
        dest = self._table(table.replace(".", "_"))
        job = self._client.load_table_from_json(
            rows or [{"_empty": True}],
            dest,
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                autodetect=True,
            ),
        )
        job.result()
        return canonical_fingerprint({"table": table, "n": len(rows)})

    def read_back(self, table: str) -> list[dict[str, Any]]:
        dest = self._table(table.replace(".", "_"))
        try:
            result = self._client.query(f"SELECT * FROM `{dest}`").result()
        except Exception as exc:
            raise ReadbackError(f"Missing required output table {table}") from exc
        return [dict(row.items()) for row in result]

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


class HybridResultStore:
    """Keep journey stash in memory; persist durable MTA outputs to BigQuery."""

    def __init__(self, durable: BigQueryResultStore) -> None:
        self._mem = InMemoryResultStore()
        self._durable = durable
        self.verified_runs = durable.verified_runs
        self.current_views = durable.current_views

    def write(self, table: str, rows: list[dict[str, Any]]) -> str:
        self._mem.write(table, rows)
        if table.startswith("_"):
            return canonical_fingerprint({"table": table, "n": len(rows)})
        return self._durable.write(table, rows)

    def read_back(self, table: str) -> list[dict[str, Any]]:
        if table.startswith("_") or table in self._mem.tables:
            return self._mem.read_back(table)
        return self._durable.read_back(table)

    def verify_required(
        self, *, run_id: str, required_tables: list[str] | tuple[str, ...]
    ) -> dict[str, str]:
        fingerprints: dict[str, str] = {}
        for table in required_tables:
            if table.startswith("_"):
                rows = self._mem.read_back(table)
            else:
                rows = self._durable.read_back(table)
            fingerprints[table] = canonical_fingerprint({"table": table, "n": len(rows)})
        self.verified_runs.add(run_id)
        self._durable.verified_runs.add(run_id)
        return fingerprints

    def advance_current(
        self, *, run_id: str, mapping: dict[str, str], run_status: MTARunStatus
    ) -> None:
        self._durable.advance_current(run_id=run_id, mapping=mapping, run_status=run_status)
        self.current_views.update(self._durable.current_views)
