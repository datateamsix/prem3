"""Canonical Data Foundation warehouse names. Customer publish must not target these."""

from __future__ import annotations

# Exact names compiled from the current Foundation Plan plus documented depot assets.
DF_OWNED_EXACT_TABLES: frozenset[str] = frozenset(
    {
        "canonical_controls",
        "canonical_kpi",
        "canonical_media",
        "canonical_treatments",
        "model_input_mmm",
        "quality_findings",
        "source_health",
        "source_registry",
        "stg_drive_imports",
        "transformation_receipts",
    }
)

# Staging tables are also named stg_<source_id>.
DF_OWNED_PREFIXES: tuple[str, ...] = ("canonical_", "stg_")


def is_data_foundation_table(table_id: str) -> bool:
    name = table_id.strip()
    if name in DF_OWNED_EXACT_TABLES:
        return True
    return any(name.startswith(prefix) for prefix in DF_OWNED_PREFIXES)
