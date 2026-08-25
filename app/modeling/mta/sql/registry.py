"""Load and resolve MTA SQL asset entries from sql/mta/manifest.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.domain.channels.registry import repo_root


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SqlAssetEntry(FrozenModel):
    asset_id: str
    asset_type: str
    path: str
    approval: str | None = None
    write_mode: str | None = None
    unique_key: str | None = None
    immutable_after_first_run: bool = False
    note: str | None = None
    version: str = "1"
    approval_class: str | None = None
    dependencies: tuple[str, ...] = ()
    validation_assets: tuple[str, ...] = ()


class SqlAssetManifest(FrozenModel):
    library_id: str
    version: int
    authority: str
    canonical_channel_registry: str
    channel_grouping_rules: str | None = None
    model_registry: str | None = None
    assets: tuple[SqlAssetEntry, ...] = ()

    def get(self, asset_id: str) -> SqlAssetEntry:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        raise KeyError(f"Unknown SQL asset_id: {asset_id}")

    def require(self, asset_ids: list[str] | tuple[str, ...]) -> tuple[SqlAssetEntry, ...]:
        return tuple(self.get(asset_id) for asset_id in asset_ids)


REQUIRED_ASSET_IDS = (
    "channel_grouping_v1",
    "channel_grouping_current",
    "create_operational_tables_v1",
    "create_run_output_tables_v1",
    "ga4_sessions_last_click_v1",
    "ga4_sessions_collected_fallback_v1",
    "merge_sessions_v1",
    "merge_conversions_v1",
    "merge_touchpoints_v1",
    "rebuild_journeys_v1",
    "rebuild_path_frequencies_v1",
    "update_watermark_v1",
    "daily_refresh_v1",
    "validate_channel_grouping_v1",
    "validate_uniqueness_v1",
    "validate_journey_ordering_v1",
    "validate_outputs_v1",
)


def manifest_path() -> Path:
    return repo_root() / "sql" / "mta" / "manifest.yaml"


def load_sql_asset_manifest(path: Path | None = None) -> SqlAssetManifest:
    data = yaml.safe_load((path or manifest_path()).read_text(encoding="utf-8"))
    assets = []
    for row in data.get("assets", []):
        assets.append(
            SqlAssetEntry(
                asset_id=str(row["id"]),
                asset_type=str(row["type"]),
                path=str(row["path"]),
                approval=row.get("approval"),
                write_mode=row.get("write_mode"),
                unique_key=row.get("unique_key"),
                immutable_after_first_run=bool(row.get("immutable_after_first_run", False)),
                note=row.get("note"),
                approval_class=row.get("approval") or row.get("approval_class"),
            )
        )
    return SqlAssetManifest(
        library_id=str(data["library_id"]),
        version=int(data["version"]),
        authority=str(data["authority"]),
        canonical_channel_registry=str(data["canonical_channel_registry"]),
        channel_grouping_rules=data.get("channel_grouping_rules"),
        model_registry=data.get("model_registry"),
        assets=tuple(assets),
    )


@lru_cache(maxsize=1)
def cached_sql_asset_manifest() -> SqlAssetManifest:
    return load_sql_asset_manifest()


def resolve_asset_path(entry: SqlAssetEntry) -> Path:
    path = repo_root() / entry.path
    if not path.is_file():
        raise FileNotFoundError(f"SQL asset missing: {entry.path}")
    return path
