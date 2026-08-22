"""In-process governed warehouse used for deterministic proof and tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.tools.fingerprints import content_fingerprint, schema_signature


@dataclass
class WarehouseTable:
    project_id: str
    dataset_id: str
    table_id: str
    frame: pd.DataFrame
    labels: dict[str, str] = field(default_factory=dict)
    description: str = ""
    partition_field: str | None = None
    object_type: str = "TABLE"
    num_rows: int | None = None
    num_bytes: int | None = None
    location: str | None = None
    last_modified: str | None = None
    partitioning_type: str | None = None
    partition_count: int | None = None
    clustering_fields: tuple[str, ...] = ()
    row_count_kind: str = "EXACT"

    @property
    def fqdn(self) -> str:
        return f"{self.project_id}.{self.dataset_id}.{self.table_id}"


class FoundationWarehouse:
    """Customer source tables are read-only. Writes go only to prem3_modeling."""

    def __init__(self) -> None:
        self.datasets: dict[str, dict[str, str]] = {}
        self.tables: dict[str, WarehouseTable] = {}
        self.queries: list[str] = []

    def create_dataset(
        self,
        *,
        project_id: str,
        dataset_id: str,
        location: str = "US",
        friendly_name: str = "prem3-modeling",
    ) -> dict[str, str]:
        if dataset_id != "prem3_modeling" and dataset_id not in {"landing_raw", "src"}:
            # Tests may seed customer source datasets; only prem3_modeling is created by DF.
            pass
        key = f"{project_id}.{dataset_id}"
        existing = self.datasets.get(key)
        if existing is not None:
            return existing
        payload = {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "location": location,
            "friendly_name": friendly_name,
        }
        self.datasets[key] = payload
        return payload

    def seed_source_table(self, table: WarehouseTable) -> None:
        if table.dataset_id == "prem3_modeling":
            raise ValueError("Customer source tables cannot be seeded into prem3_modeling.")
        self.tables[table.fqdn] = table
        self.datasets.setdefault(
            f"{table.project_id}.{table.dataset_id}",
            {
                "project_id": table.project_id,
                "dataset_id": table.dataset_id,
                "location": "US",
                "friendly_name": table.dataset_id,
            },
        )

    def get_table(self, fqdn: str) -> WarehouseTable | None:
        return self.tables.get(fqdn)

    def read_table(self, fqdn: str) -> pd.DataFrame:
        table = self.tables.get(fqdn)
        if table is None:
            raise KeyError(f"Table not found: {fqdn}")
        self.queries.append(f"READ {fqdn}")
        return table.frame.copy(deep=True)

    def write_foundation_table(self, table: WarehouseTable) -> WarehouseTable:
        if table.dataset_id != "prem3_modeling":
            raise PermissionError("Data Foundation may write only to prem3_modeling.")
        self.create_dataset(project_id=table.project_id, dataset_id="prem3_modeling")
        self.tables[table.fqdn] = table
        return table

    def refuse_overwrite_source(self, fqdn: str) -> None:
        table = self.tables.get(fqdn)
        if table is not None and table.dataset_id != "prem3_modeling":
            raise PermissionError("Customer source tables are immutable.")

    def list_tables(
        self, *, project_id: str, dataset_id: str | None = None
    ) -> list[WarehouseTable]:
        rows = [item for item in self.tables.values() if item.project_id == project_id]
        if dataset_id is not None:
            rows = [item for item in rows if item.dataset_id == dataset_id]
        return rows

    def schema_fingerprint(self, fqdn: str) -> str:
        table = self.tables[fqdn]
        return str(schema_signature(table.frame))

    def content_hash(self, fqdn: str, key_columns: list[str]) -> str:
        table = self.tables[fqdn]
        columns = [str(column) for column in table.frame.columns]
        keys = [column for column in key_columns if column in columns] or columns[:1]
        return content_fingerprint(table.frame, columns=columns, key_columns=keys)
