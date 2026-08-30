"""Pinned external Meridian assets. Never fetch GitHub at runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modeling.common.errors import ExternalAssetDisabledError

PINNED_UPSTREAM_COMMIT = "8ca83f6b2ffd0230264bc3e3e968b1f0a1c4f9d7"
PINNED_RUNTIME_VERSION = "1.8.0"
SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "third_party"
    / "google_meridian"
    / PINNED_UPSTREAM_COMMIT
)


class ExternalAgentAsset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    provider: str = "google"
    repository: str = "google/meridian"
    upstream_commit_sha: str = PINNED_UPSTREAM_COMMIT
    upstream_path: str
    upstream_blob_sha: str
    license: str = "Apache-2.0"
    asset_type: str
    internal_version: str = "1"
    review_status: str = "REVIEWED"
    compatibility_status: str
    reviewed_at: str | None = None
    supersedes_asset_id: str | None = None
    enabled: bool = True
    mission3_role: str | None = None
    notes: str | None = None


def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def load_manifest() -> dict[str, Any]:
    path = SNAPSHOT_ROOT / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_sha256() -> str:
    payload = (SNAPSHOT_ROOT / "manifest.json").read_bytes()
    return hashlib.sha256(payload).hexdigest()


def listed_assets() -> tuple[ExternalAgentAsset, ...]:
    manifest = load_manifest()
    assets: list[ExternalAgentAsset] = []
    for item in manifest["assets"]:
        assets.append(
            ExternalAgentAsset(
                asset_id=item["asset_id"],
                upstream_path=item["upstream_path"],
                upstream_blob_sha=item["upstream_blob_sha"],
                asset_type=item["asset_type"],
                compatibility_status=item["compatibility_status"],
                enabled=bool(item.get("enabled", False)),
                mission3_role=item.get("mission3_role"),
                notes=item.get("notes"),
            )
        )
    return tuple(assets)


def require_enabled_asset(asset_id: str) -> ExternalAgentAsset:
    for asset in listed_assets():
        if asset.asset_id == asset_id:
            if not asset.enabled:
                raise ExternalAssetDisabledError(
                    f"External asset {asset_id} is disabled."
                )
            return asset
    raise ExternalAssetDisabledError(f"Unknown external asset {asset_id}.")


def read_snapshot_text(relative_path: str) -> str:
    path = SNAPSHOT_ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return path.read_text(encoding="utf-8")


def verify_vendored_blob(relative_path: str, expected_sha: str) -> None:
    content = (SNAPSHOT_ROOT / relative_path).read_bytes()
    actual = git_blob_sha(content)
    if actual != expected_sha:
        raise ValueError(f"Blob SHA mismatch for {relative_path}: {actual}")
