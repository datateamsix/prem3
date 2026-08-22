"""Protect Data Foundation warehouse names from customer model-ready publish."""

from __future__ import annotations

RESERVED_EXACT_TABLES: frozenset[str] = frozenset(
    {"source_registry", "source_health", "model_input_mmm"}
)
RESERVED_PREFIXES: tuple[str, ...] = ("canonical_", "stg_")


def is_reserved_bigquery_table(table_id: str) -> bool:
    name = table_id.strip()
    if name in RESERVED_EXACT_TABLES:
        return True
    return any(name.startswith(prefix) for prefix in RESERVED_PREFIXES)


def assert_model_ready_namespace(table_id: str) -> None:
    if is_reserved_bigquery_table(table_id):
        raise ValueError(table_id)
