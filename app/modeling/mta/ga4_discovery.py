"""GA4 BigQuery export discovery helpers (metadata-first)."""

from __future__ import annotations

import re
from typing import Protocol

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import GA4DiscoveryResult, GA4SourceBinding
from app.modeling.mta.policies import (
    select_traffic_source_policy,
    settled_through_date,
)

_ANALYTICS_DATASET = re.compile(r"^analytics_(\d+)$")
_EVENTS_SHARD = re.compile(r"^events_(\d{8})$")
_INTRADAY_SHARD = re.compile(r"^events_intraday_(\d{8})$")


class TableLister(Protocol):
    def list_datasets(self, *, project_id: str) -> list[str]: ...

    def list_tables(self, *, project_id: str, dataset_id: str) -> list[str]: ...

    def get_table_schema_fields(
        self, *, project_id: str, dataset_id: str, table_id: str
    ) -> list[str]: ...


class InMemoryGA4Catalog:
    """Test double for GA4 dataset/table discovery."""

    def __init__(
        self,
        *,
        datasets: dict[str, list[str]] | None = None,
        schemas: dict[tuple[str, str, str], list[str]] | None = None,
    ) -> None:
        self.datasets = datasets or {}
        self.schemas = schemas or {}

    def list_datasets(self, *, project_id: str) -> list[str]:
        return list(self.datasets.keys())

    def list_tables(self, *, project_id: str, dataset_id: str) -> list[str]:
        return list(self.datasets.get(dataset_id, []))

    def get_table_schema_fields(
        self, *, project_id: str, dataset_id: str, table_id: str
    ) -> list[str]:
        return list(self.schemas.get((project_id, dataset_id, table_id), []))


def parse_analytics_property_id(dataset_id: str) -> str | None:
    match = _ANALYTICS_DATASET.match(dataset_id)
    return None if match is None else match.group(1)


def discover_ga4_exports(
    catalog: TableLister,
    *,
    gcp_project_id: str,
    as_of_iso: str | None = None,
) -> GA4DiscoveryResult:
    from datetime import date

    as_of = date.fromisoformat(as_of_iso) if as_of_iso else date.today()
    settled = settled_through_date(as_of=as_of)
    settled_iso = None if settled is None else settled.isoformat()
    bindings: list[GA4SourceBinding] = []
    notes: list[str] = []

    for dataset_id in catalog.list_datasets(project_id=gcp_project_id):
        property_id = parse_analytics_property_id(dataset_id)
        if property_id is None:
            continue
        tables = catalog.list_tables(project_id=gcp_project_id, dataset_id=dataset_id)
        daily_dates: list[str] = []
        for table_id in tables:
            m = _EVENTS_SHARD.match(table_id)
            if m:
                daily_dates.append(
                    f"{m.group(1)[0:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
                )
        daily_dates.sort()
        sample_table = None
        for table_id in tables:
            if _EVENTS_SHARD.match(table_id):
                sample_table = table_id
                break
        fields = (
            catalog.get_table_schema_fields(
                project_id=gcp_project_id, dataset_id=dataset_id, table_id=sample_table
            )
            if sample_table
            else []
        )
        has_last_click = "session_traffic_source_last_click" in fields
        has_collected = "collected_traffic_source" in fields
        policy = select_traffic_source_policy(
            has_session_traffic_source_last_click=has_last_click,
            has_collected_traffic_source=has_collected,
        )
        fp = canonical_fingerprint(
            {
                "project": gcp_project_id,
                "dataset": dataset_id,
                "property_id": property_id,
                "daily": daily_dates,
                "fields": fields,
                "policy": policy.value,
            }
        )
        bindings.append(
            GA4SourceBinding(
                gcp_project_id=gcp_project_id,
                dataset_id=dataset_id,
                property_id=property_id,
                earliest_shard_date=daily_dates[0] if daily_dates else None,
                latest_shard_date=daily_dates[-1] if daily_dates else None,
                settled_through_date=settled_iso,
                has_session_traffic_source_last_click=has_last_click,
                has_collected_traffic_source=has_collected,
                schema_fields_sample=tuple(fields[:40]),
                discovery_fingerprint=fp,
            )
        )
        notes.append(f"Selected traffic-source policy candidate: {policy.value}")

    selected = bindings[0] if len(bindings) == 1 else None
    return GA4DiscoveryResult(bindings=tuple(bindings), selected=selected, notes=tuple(notes))
