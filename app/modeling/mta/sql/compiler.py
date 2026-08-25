"""Compile provisioning/refresh plans from SQL assets + contracts."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.sql.registry import (
    REQUIRED_ASSET_IDS,
    SqlAssetEntry,
    SqlAssetManifest,
    cached_sql_asset_manifest,
)
from app.modeling.mta.sql.renderer import render_sql_asset


class CompiledSqlAsset:
    __slots__ = ("entry", "rendered_sql", "sql_fingerprint", "params")

    def __init__(
        self,
        *,
        entry: SqlAssetEntry,
        rendered_sql: str,
        sql_fingerprint: str,
        params: dict[str, Any],
    ) -> None:
        self.entry = entry
        self.rendered_sql = rendered_sql
        self.sql_fingerprint = sql_fingerprint
        self.params = params


def compile_required_sql_assets(
    *,
    params: dict[str, Any],
    manifest: SqlAssetManifest | None = None,
    asset_ids: tuple[str, ...] = REQUIRED_ASSET_IDS,
) -> tuple[CompiledSqlAsset, ...]:
    catalog = manifest or cached_sql_asset_manifest()
    compiled: list[CompiledSqlAsset] = []
    for asset_id in asset_ids:
        entry = catalog.get(asset_id)
        rendered, fingerprint = render_sql_asset(entry, params=params)
        compiled.append(
            CompiledSqlAsset(
                entry=entry,
                rendered_sql=rendered,
                sql_fingerprint=fingerprint,
                params=params,
            )
        )
    return tuple(compiled)


def provisioning_plan_fingerprint(
    *,
    tenant_id: str,
    project_id: str,
    gcp_project_id: str,
    dataset_id: str,
    channel_grouping_version: str,
    compiled: tuple[CompiledSqlAsset, ...],
) -> str:
    return canonical_fingerprint(
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "gcp_project_id": gcp_project_id,
            "dataset_id": dataset_id,
            "channel_grouping_version": channel_grouping_version,
            "assets": [
                {
                    "asset_id": item.entry.asset_id,
                    "sql_fingerprint": item.sql_fingerprint,
                    "approval_class": item.entry.approval_class,
                }
                for item in compiled
            ],
        }
    )
