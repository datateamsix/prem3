"""Metadata-first BigQuery discovery. No SELECT *."""

from __future__ import annotations

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import DiscoveryHints, QueryBudgetPolicy
from app.data_foundation.discovery.candidates import candidate_from_table
from app.data_foundation.discovery.query_budget import compile_profile_query
from app.data_foundation.warehouse import FoundationWarehouse, WarehouseTable


def discover_tables(
    warehouse: FoundationWarehouse,
    *,
    context: DataFoundationContext,
    policy: QueryBudgetPolicy | None = None,
    hints: DiscoveryHints | None = None,
) -> list[WarehouseTable]:
    del policy
    context.require_discovery_ready()
    found: list[WarehouseTable] = []
    prioritized = set(hints.datasets_to_prioritize) if hints else set()
    strict = bool(hints and hints.only_inspect_prioritized_datasets and prioritized)
    for project_id in context.source_project_ids:
        context.authorize_project(project_id)
        for table in warehouse.list_tables(project_id=project_id):
            if table.dataset_id == "prem3_modeling":
                continue
            if context.source_dataset_ids and table.dataset_id not in context.source_dataset_ids:
                continue
            if strict and table.dataset_id not in prioritized:
                continue
            found.append(table)
    if hints and hints.datasets_to_prioritize and not strict:
        found.sort(key=lambda item: item.dataset_id not in prioritized)
    return found


def shortlist_and_compile(
    table: WarehouseTable,
    *,
    context: DataFoundationContext,
    policy: QueryBudgetPolicy,
    partition_start: str | None = None,
) -> object:
    context.authorize_project(table.project_id)
    columns = tuple(str(column) for column in table.frame.columns)
    return compile_profile_query(
        project_id=table.project_id,
        dataset_id=table.dataset_id,
        table_id=table.table_id,
        columns=columns,
        partition_field=table.partition_field,
        partition_start=partition_start,
        policy=policy.model_copy(
            update={"require_partition_predicate": bool(table.partition_field)}
        ),
        estimated_bytes=int(table.frame.memory_usage(deep=True).sum()),
    )


def candidates_for_tables(
    tables: list[WarehouseTable],
    requirement_by_hint: dict[str, object],
    *,
    tenant_id: str,
    workspace_id: str,
) -> list:
    rows = []
    for table in tables:
        hint = None
        for key, requirement in requirement_by_hint.items():
            hay = f"{table.table_id} {table.dataset_id}".lower()
            if key.lower() in hay:
                hint = requirement
                break
        rows.append(
            candidate_from_table(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                project_id=table.project_id,
                dataset_id=table.dataset_id,
                table_id=table.table_id,
                field_names=tuple(str(column) for column in table.frame.columns),
                requirement=hint,  # type: ignore[arg-type]
                row_count=len(table.frame),
            )
        )
    return rows
