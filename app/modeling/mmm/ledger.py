"""Queryable BigQuery model ledger. Binary models stay in GCS."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.contracts import utc_now
from app.modeling.common.errors import LedgerPublicationError
from app.modeling.mmm.contracts import (
    FitRun,
    MeridianModelHealthReceipt,
    MMMModelVersion,
    ModelDecision,
)

try:
    from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
except ImportError:  # pragma: no cover - live ledger only
    QueryJobConfig = None
    ScalarQueryParameter = None

BQ_MODEL_LEDGER_TABLES = (
    "mmm_model_versions",
    "mmm_fit_runs",
    "mmm_model_decisions",
    "mmm_model_health",
    "mmm_model_channel_summary",
)

LEDGER_COLUMNS = {
    "mmm_model_versions": (
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "model_plan_fingerprint",
        "meridian_version",
        "state",
        "accepted",
        "model_window_start",
        "model_window_end",
        "created_at",
    ),
    "mmm_fit_runs": (
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "fit_run_id",
        "fit_plan_fingerprint",
        "runtime_mode",
        "status",
        "meridian_version",
        "created_at",
    ),
    "mmm_model_decisions": (
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "decision_id",
        "decision_type",
        "status",
        "plan_fingerprint",
        "created_at",
    ),
    "mmm_model_health": (
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "fit_run_id",
        "review_source",
        "blocking_fail_count",
        "review_count",
        "meridian_version",
        "created_at",
    ),
    "mmm_model_channel_summary": (
        "project_id",
        "cycle_id",
        "track_id",
        "model_version_id",
        "fit_run_id",
        "channel",
        "roi",
        "contribution",
        "meridian_version",
        "created_at",
    ),
}

LEDGER_COLUMN_TYPES = {
    "project_id": "STRING",
    "cycle_id": "STRING",
    "track_id": "STRING",
    "model_version_id": "STRING",
    "model_plan_fingerprint": "STRING",
    "meridian_version": "STRING",
    "state": "STRING",
    "accepted": "BOOL",
    "model_window_start": "STRING",
    "model_window_end": "STRING",
    "created_at": "TIMESTAMP",
    "fit_run_id": "STRING",
    "fit_plan_fingerprint": "STRING",
    "runtime_mode": "STRING",
    "status": "STRING",
    "decision_id": "STRING",
    "decision_type": "STRING",
    "plan_fingerprint": "STRING",
    "review_source": "STRING",
    "blocking_fail_count": "INT64",
    "review_count": "INT64",
    "channel": "STRING",
    "roi": "FLOAT64",
    "contribution": "FLOAT64",
}


class ModelLedger(Protocol):
    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]: ...

    def read_back(self, *, table: str, model_version_id: str) -> dict[str, Any] | None: ...


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

    def read_back(self, *, table: str, model_version_id: str) -> dict[str, Any] | None:
        for row in reversed(self.rows.get(table, [])):
            if row.get("model_version_id") == model_version_id:
                return dict(row)
        return None


def compile_model_version_row(
    version: MMMModelVersion, *, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    row = {
        "project_id": version.project_id,
        "cycle_id": version.cycle_id,
        "track_id": version.track_id,
        "model_version_id": version.model_version_id,
        "model_plan_fingerprint": version.model_plan_fingerprint,
        "meridian_version": version.meridian_version,
        "state": version.state.value,
        "accepted": version.accepted,
        "model_window_start": version.model_window_start,
        "model_window_end": version.model_window_end,
        "created_at": version.created_at.isoformat(),
    }
    if extra:
        row.update(extra)
    return row


def compile_fit_run_row(run: FitRun, *, cycle_id: str, track_id: str) -> dict[str, Any]:
    return {
        "project_id": run.project_id,
        "cycle_id": cycle_id,
        "track_id": track_id,
        "model_version_id": run.model_version_id,
        "fit_run_id": run.fit_run_id,
        "fit_plan_fingerprint": run.fit_plan_fingerprint,
        "runtime_mode": run.runtime_mode.value,
        "status": run.status.value,
        "meridian_version": run.meridian_version,
        "created_at": run.created_at.isoformat(),
    }


def compile_decision_row(
    decision: ModelDecision, *, cycle_id: str, track_id: str
) -> dict[str, Any]:
    return {
        "project_id": decision.project_id,
        "cycle_id": cycle_id,
        "track_id": track_id,
        "model_version_id": decision.model_version_id,
        "decision_id": decision.decision_id,
        "decision_type": decision.decision_type.value,
        "status": decision.status.value,
        "plan_fingerprint": decision.plan_fingerprint,
        "created_at": decision.created_at.isoformat(),
    }


def compile_health_row(
    health: MeridianModelHealthReceipt, *, project_id: str, cycle_id: str, track_id: str
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "cycle_id": cycle_id,
        "track_id": track_id,
        "model_version_id": health.model_version_id,
        "fit_run_id": health.fit_run_id,
        "review_source": health.review_source.value,
        "blocking_fail_count": health.blocking_fail_count,
        "review_count": health.review_count,
        "meridian_version": health.meridian_version,
        "created_at": health.generated_at.isoformat(),
    }


def compile_channel_summary_row(
    *,
    project_id: str,
    cycle_id: str,
    track_id: str,
    model_version_id: str,
    fit_run_id: str,
    channel: str,
    roi: float | None,
    contribution: float | None,
    meridian_version: str,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "cycle_id": cycle_id,
        "track_id": track_id,
        "model_version_id": model_version_id,
        "fit_run_id": fit_run_id,
        "channel": channel,
        "roi": roi,
        "contribution": contribution,
        "meridian_version": meridian_version,
        "created_at": utc_now().isoformat(),
    }


class BigQueryModelLedger:
    """Versioned append writes into the Project Measurement Home dataset."""

    def __init__(
        self,
        *,
        client: Any,
        project_id: str,
        dataset_id: str,
        access_token: str,
        location: str,
    ) -> None:
        self._client = client
        self._project_id = project_id
        self._dataset_id = dataset_id
        self._access_token = access_token
        self._location = location
        self._seq = 0

    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if table not in BQ_MODEL_LEDGER_TABLES:
            raise ValueError(f"Unknown model ledger table {table}.")
        self._seq += 1
        table_id = f"{table}_{row['model_version_id']}_{self._seq:04d}"
        columns = list(LEDGER_COLUMNS[table])
        values = [[row.get(column) for column in columns]]
        try:
            self._client.write_versioned_table(
                access_token=self._access_token,
                project_id=self._project_id,
                dataset_id=self._dataset_id,
                table_id=table_id,
                columns=columns,
                rows=values,
                location=self._location,
            )
        except FileExistsError as exc:
            raise LedgerPublicationError("Historical ledger tables are append/versioned.") from exc
        readback = self._client.get_table_rows(
            access_token=self._access_token,
            project_id=self._project_id,
            dataset_id=self._dataset_id,
            table_id=table_id,
        )
        if readback is None:
            raise LedgerPublicationError("Ledger write had no read-back.")
        stored = dict(row)
        stored["_table_id"] = table_id
        stored["_readback"] = readback
        return stored

    def read_back(self, *, table: str, model_version_id: str) -> dict[str, Any] | None:
        del table, model_version_id
        return None


def publish_fit_ledger(
    ledger: ModelLedger,
    *,
    version: MMMModelVersion,
    run: FitRun,
    decisions: list[ModelDecision],
    health: MeridianModelHealthReceipt | None,
    channel_rows: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    written = {
        "mmm_model_versions": ledger.write(
            table="mmm_model_versions", row=compile_model_version_row(version)
        ),
        "mmm_fit_runs": ledger.write(
            table="mmm_fit_runs",
            row=compile_fit_run_row(run, cycle_id=version.cycle_id, track_id=version.track_id),
        ),
    }
    for decision in decisions:
        ledger.write(
            table="mmm_model_decisions",
            row=compile_decision_row(
                decision, cycle_id=version.cycle_id, track_id=version.track_id
            ),
        )
    if health is not None:
        written["mmm_model_health"] = ledger.write(
            table="mmm_model_health",
            row=compile_health_row(
                health,
                project_id=version.project_id,
                cycle_id=version.cycle_id,
                track_id=version.track_id,
            ),
        )
    for row in channel_rows:
        ledger.write(table="mmm_model_channel_summary", row=row)
    readback = ledger.read_back(
        table="mmm_fit_runs", model_version_id=version.model_version_id
    )
    if readback is None or readback.get("fit_plan_fingerprint") != run.fit_plan_fingerprint:
        raise LedgerPublicationError("Ledger read-back fingerprint mismatch.")
    written["readback"] = readback
    return written


class CanonicalBigQueryModelLedger:
    """Append-only Project Measurement Home ledger. Destinations are injected."""

    def __init__(self, *, client: Any, project_id: str, dataset_id: str) -> None:
        self._client = client
        self._project_id = project_id
        self._dataset_id = dataset_id

    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if table not in BQ_MODEL_LEDGER_TABLES:
            raise ValueError(f"Unknown model ledger table {table}.")
        if QueryJobConfig is None or ScalarQueryParameter is None:
            raise LedgerPublicationError(
                "google-cloud-bigquery is required for live ledger writes."
            )
        columns = LEDGER_COLUMNS[table]
        table_ref = f"{self._project_id}.{self._dataset_id}.{table}"
        colsql = ", ".join(f"`{name}`" for name in columns)
        placeholders = ", ".join(f"@{name}" for name in columns)
        sql = f"INSERT INTO `{table_ref}` ({colsql}) VALUES ({placeholders})"
        parameters = [
            ScalarQueryParameter(
                name,
                _parameter_type(LEDGER_COLUMN_TYPES[name]),
                row.get(name),
            )
            for name in columns
        ]
        try:
            self._client.query(
                sql, job_config=QueryJobConfig(query_parameters=parameters)
            ).result()
        except Exception as exc:
            raise LedgerPublicationError(f"BQ_LEDGER_FAILED: {exc}") from exc
        return dict(row)

    def read_back(self, *, table: str, model_version_id: str) -> dict[str, Any] | None:
        if QueryJobConfig is None or ScalarQueryParameter is None:
            raise LedgerPublicationError(
                "google-cloud-bigquery is required for live ledger read-back."
            )
        sql = (
            f"SELECT * FROM `{self._project_id}.{self._dataset_id}.{table}` "
            "WHERE model_version_id = @model_version_id "
            "ORDER BY created_at DESC LIMIT 1"
        )
        job = self._client.query(
            sql,
            job_config=QueryJobConfig(
                query_parameters=[
                    ScalarQueryParameter("model_version_id", "STRING", model_version_id)
                ]
            ),
        )
        rows = list(job.result())
        if not rows:
            return None
        return _row_to_dict(rows[0])

    def read_history(
        self, *, table: str, model_version_id: str | None = None
    ) -> list[dict[str, Any]]:
        if table not in BQ_MODEL_LEDGER_TABLES:
            raise ValueError(f"Unknown model ledger table {table}.")
        if QueryJobConfig is None or ScalarQueryParameter is None:
            raise LedgerPublicationError(
                "google-cloud-bigquery is required for live ledger read-back."
            )
        sql = f"SELECT * FROM `{self._project_id}.{self._dataset_id}.{table}`"
        parameters: list[Any] = []
        if model_version_id is not None:
            sql += " WHERE model_version_id = @model_version_id"
            parameters.append(
                ScalarQueryParameter("model_version_id", "STRING", model_version_id)
            )
        sql += " ORDER BY created_at ASC"
        job = self._client.query(
            sql,
            job_config=QueryJobConfig(query_parameters=parameters),
        )
        return [_row_to_dict(row) for row in job.result()]


def ledger_table_ddl(*, project_id: str, dataset_id: str, table: str) -> str:
    if table not in BQ_MODEL_LEDGER_TABLES:
        raise ValueError(f"Unknown model ledger table {table}.")
    columns = ", ".join(
        f"`{name}` {LEDGER_COLUMN_TYPES[name]}" for name in LEDGER_COLUMNS[table]
    )
    return f"CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.{table}` ({columns})"


def ensure_model_ledger_tables(client: Any, *, project_id: str, dataset_id: str) -> tuple[str, ...]:
    created: list[str] = []
    for table in BQ_MODEL_LEDGER_TABLES:
        sql = ledger_table_ddl(project_id=project_id, dataset_id=dataset_id, table=table)
        client.query(sql).result()
        created.append(table)
    return tuple(created)


def _row_to_dict(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key, value in list(payload.items()):
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload


def _parameter_type(bq_type: str) -> str:
    if bq_type == "BOOL":
        return "BOOL"
    if bq_type == "INT64":
        return "INT64"
    if bq_type == "FLOAT64":
        return "FLOAT64"
    if bq_type == "TIMESTAMP":
        return "TIMESTAMP"
    return "STRING"
