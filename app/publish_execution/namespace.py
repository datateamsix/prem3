"""Protect Data Foundation warehouse names from customer model-ready publish."""

from __future__ import annotations

from app.data_foundation.owned_resources import (
    DF_OWNED_EXACT_TABLES,
    DF_OWNED_PREFIXES,
    is_data_foundation_table,
)

RESERVED_EXACT_TABLES: frozenset[str] = DF_OWNED_EXACT_TABLES
RESERVED_PREFIXES: tuple[str, ...] = DF_OWNED_PREFIXES


def is_reserved_bigquery_table(table_id: str) -> bool:
    return is_data_foundation_table(table_id)


def assert_model_ready_namespace(table_id: str) -> None:
    if is_reserved_bigquery_table(table_id):
        raise ValueError(table_id)
