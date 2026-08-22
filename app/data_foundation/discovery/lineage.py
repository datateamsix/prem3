"""Lineage summaries. Job-history inference is P1."""

from __future__ import annotations

from app.data_foundation.contracts import ResourceIdentity


def describe_lineage(resource: ResourceIdentity) -> str:
    if resource.logical_path:
        return f"physical:{resource.logical_path}"
    return f"location:{resource.location_type.value}"
