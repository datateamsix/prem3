"""MTA SQL asset package — registry, renderer, compiler."""

from __future__ import annotations

from app.modeling.mta.sql.compiler import (
    CompiledSqlAsset,
    compile_required_sql_assets,
    provisioning_plan_fingerprint,
)
from app.modeling.mta.sql.registry import (
    REQUIRED_ASSET_IDS,
    SqlAssetEntry,
    SqlAssetManifest,
    cached_sql_asset_manifest,
    load_sql_asset_manifest,
)
from app.modeling.mta.sql.renderer import render_sql_asset, render_sql_template

__all__ = [
    "CompiledSqlAsset",
    "REQUIRED_ASSET_IDS",
    "SqlAssetEntry",
    "SqlAssetManifest",
    "cached_sql_asset_manifest",
    "compile_required_sql_assets",
    "load_sql_asset_manifest",
    "provisioning_plan_fingerprint",
    "render_sql_asset",
    "render_sql_template",
]
