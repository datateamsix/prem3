"""BigQuery job helpers for MTA SQL asset execution (production path)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from google.cloud import bigquery

from app.integrations.bigquery import get_bigquery_client


@dataclass(frozen=True)
class QueryJobResult:
    job_id: str
    bytes_processed: int | None
    dry_run: bool
    rows: tuple[dict[str, Any], ...] = ()


def client_for_project(project_id: str | None = None) -> bigquery.Client:
    import google.auth

    base = get_bigquery_client()
    if project_id is None or project_id == base.project:
        return base
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(
        project=project_id, credentials=credentials, location=base.location
    )


def ensure_dataset(client: bigquery.Client, *, project_id: str, dataset_id: str) -> None:
    ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(ref)
    except Exception:
        ds = bigquery.Dataset(ref)
        ds.location = client.location or "US"
        ds.description = "PreM3 modeling depot"
        client.create_dataset(ds, exists_ok=True)


def run_query(
    client: bigquery.Client,
    sql: str,
    *,
    params: dict[str, Any] | None = None,
    dry_run: bool = False,
    fetch: bool = False,
) -> QueryJobResult:
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    if params:
        qparams: list[bigquery.ScalarQueryParameter] = []
        for key, value in params.items():
            if isinstance(value, date):
                qparams.append(bigquery.ScalarQueryParameter(key, "DATE", value))
            elif isinstance(value, bool):
                qparams.append(bigquery.ScalarQueryParameter(key, "BOOL", value))
            elif isinstance(value, int):
                qparams.append(bigquery.ScalarQueryParameter(key, "INT64", value))
            elif isinstance(value, float):
                qparams.append(bigquery.ScalarQueryParameter(key, "FLOAT64", value))
            else:
                qparams.append(bigquery.ScalarQueryParameter(key, "STRING", str(value)))
        job_config.query_parameters = qparams
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return QueryJobResult(
            job_id=job.job_id or "dry_run",
            bytes_processed=job.total_bytes_processed,
            dry_run=True,
        )
    result = job.result()
    rows: tuple[dict[str, Any], ...] = ()
    if fetch:
        rows = tuple(dict(r.items()) for r in result)
    return QueryJobResult(
        job_id=job.job_id or "",
        bytes_processed=job.total_bytes_processed,
        dry_run=False,
        rows=rows,
    )


def split_sql_statements(sql: str) -> list[str]:
    """Split multi-statement DDL on semicolons outside strings (simple heuristic)."""
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    for ch in sql:
        if ch == "'" and not in_single:
            in_single = True
            buf.append(ch)
        elif ch == "'" and in_single:
            in_single = False
            buf.append(ch)
        elif ch == ";" and not in_single:
            stmt = "".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def execute_sql_script(
    client: bigquery.Client,
    sql: str,
    *,
    params: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> list[QueryJobResult]:
    """Execute multi-statement SQL as a BigQuery script job when possible."""
    statements = split_sql_statements(sql)
    if not statements:
        return []
    # Prefer one script job so later DDL is not skipped after an early success.
    try:
        return [run_query(client, sql, params=params, dry_run=dry_run)]
    except Exception:
        if len(statements) == 1:
            raise
        results: list[QueryJobResult] = []
        for stmt in statements:
            results.append(run_query(client, stmt, params=params, dry_run=dry_run))
        return results


def get_routine_definition(
    client: bigquery.Client, *, project_id: str, dataset_id: str, routine_id: str
) -> str | None:
    try:
        routine = client.get_routine(f"{project_id}.{dataset_id}.{routine_id}")
    except Exception:
        return None
    body = getattr(routine, "body", None)
    return str(body) if body is not None else None


def table_exists(
    client: bigquery.Client, *, project_id: str, dataset_id: str, table_id: str
) -> bool:
    try:
        client.get_table(f"{project_id}.{dataset_id}.{table_id}")
        return True
    except Exception:
        return False


def describe_table(
    client: bigquery.Client, *, project_id: str, dataset_id: str, table_id: str
) -> dict[str, Any]:
    table = client.get_table(f"{project_id}.{dataset_id}.{table_id}")
    return {
        "table_id": table.table_id,
        "num_rows": table.num_rows,
        "partitioning_type": getattr(table.time_partitioning, "type_", None)
        if table.time_partitioning
        else None,
        "partitioning_field": getattr(table.time_partitioning, "field", None)
        if table.time_partitioning
        else None,
        "clustering_fields": list(table.clustering_fields or []),
        "schema": [{"name": f.name, "type": f.field_type} for f in table.schema],
        "description": table.description,
    }
