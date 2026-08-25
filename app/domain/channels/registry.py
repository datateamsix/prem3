"""Load versioned channel registry YAML from assets/channels."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.channels.models import ChannelDefinition, ChannelRegistry
from app.modeling.common.fingerprints import canonical_fingerprint

AI_SEARCH_CHANNEL_ID = "ai_search"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_registry_path(*, version: int = 1) -> Path:
    return repo_root() / "assets" / "channels" / f"channel_registry_v{version}.yaml"


def load_channel_registry(
    path: Path | None = None, *, version: int = 1
) -> ChannelRegistry:
    registry_path = path or default_registry_path(version=version)
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    channels = tuple(
        ChannelDefinition(
            channel_id=str(row["id"]),
            display_name=str(row["display_name"]),
            channel_family_id=str(row["family_id"]),
            mta_default=bool(row.get("mta_default", True)),
            mmm_allowed=bool(row.get("mmm_allowed", True)),
            deprecated=bool(row.get("deprecated", False)),
        )
        for row in raw.get("channels", [])
    )
    payload = {
        "version": int(raw.get("version", version)),
        "contract": raw.get("contract"),
        "channels": [
            {
                "channel_id": c.channel_id,
                "display_name": c.display_name,
                "channel_family_id": c.channel_family_id,
                "mta_default": c.mta_default,
                "mmm_allowed": c.mmm_allowed,
                "deprecated": c.deprecated,
            }
            for c in channels
        ],
    }
    return ChannelRegistry(
        channel_registry_version=int(raw.get("version", version)),
        contract=str(raw.get("contract", "PREM3_CANONICAL_CHANNEL_REGISTRY")),
        channels=channels,
        fingerprint=canonical_fingerprint(payload),
    )


@lru_cache(maxsize=4)
def cached_channel_registry(version: int = 1) -> ChannelRegistry:
    return load_channel_registry(version=version)
