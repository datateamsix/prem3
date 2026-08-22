"""Compiled profiling SQL only. Agent/user SQL is rejected."""

from __future__ import annotations

import re

from app.data_foundation.contracts import CompiledQuery, QueryBudgetPolicy

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|grant|revoke)\b",
    re.IGNORECASE,
)


def validate_identifier(value: str, *, field: str) -> str:
    if _IDENT.fullmatch(value) is None:
        raise ValueError(f"{field} is not a safe BigQuery identifier.")
    return value


def compile_profile_query(
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    columns: tuple[str, ...],
    partition_field: str | None,
    partition_start: str | None,
    policy: QueryBudgetPolicy,
    estimated_bytes: int | None = None,
) -> CompiledQuery:
    if policy.allow_arbitrary_sql:
        raise ValueError("Arbitrary SQL is not a supported Data Foundation policy.")
    validate_identifier(project_id.replace("-", "_"), field="project_id")
    dataset = validate_identifier(dataset_id, field="dataset_id")
    table = validate_identifier(table_id, field="table_id")
    if not columns:
        raise ValueError("Profiling requires an explicit column list.")
    if policy.allow_select_star:
        raise ValueError("SELECT * discovery is forbidden.")
    select_list = ", ".join(validate_identifier(column, field="column") for column in columns)
    where_parts: list[str] = []
    partition_predicate = None
    if partition_field:
        field = validate_identifier(partition_field, field="partition_field")
        if partition_start is None and policy.require_partition_predicate:
            raise ValueError("Partitioned sources require a compiled partition predicate.")
        if partition_start is not None:
            partition_predicate = f"{field} >= DATE('{partition_start}')"
            where_parts.append(partition_predicate)
    elif policy.require_partition_predicate:
        # Unpartitioned shortlist tables may profile with LIMIT only.
        pass
    where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    sql = (
        f"SELECT {select_list} FROM `{project_id}.{dataset}.{table}`"
        f"{where_sql} LIMIT {int(policy.sample_limit)}"
    )
    if _FORBIDDEN.search(sql):
        raise ValueError("Compiled SQL failed the mutation/DDL denylist.")
    if estimated_bytes is not None and estimated_bytes > policy.max_bytes_scanned:
        raise ValueError("Query budget exceeded before execution.")
    return CompiledQuery(
        operation="bounded_profile",
        sql=sql,
        labels={
            "prem3_purpose": "data_foundation_profile",
            "prem3_table": table,
        },
        estimated_bytes=estimated_bytes,
        partition_predicate=partition_predicate,
    )


def reject_arbitrary_sql(sql: str) -> None:
    raise ValueError("Agent/user SQL is not accepted by Data Foundation discovery.")
