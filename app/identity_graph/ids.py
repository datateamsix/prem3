"""Server-owned Marketing Identity Graph identifiers."""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier

CAMPAIGN_ID_PREFIX = "cmp"


def _opaque(prefix: str) -> str:
    return validate_resource_identifier(f"{prefix}_{uuid4().hex[:20]}", field="resource_id")


def new_campaign_id(*, issued: set[str] | frozenset[str] | None = None) -> str:
    """Mint an opaque cmp_ ID. Never derived from name, provider, market, or channel."""
    used = issued or set()
    for _ in range(8):
        value = _opaque(CAMPAIGN_ID_PREFIX)
        if value not in used:
            return value
    raise RuntimeError("Unable to mint a unique campaign_id.")


def new_binding_id() -> str:
    return _opaque("igb")


def new_tracking_binding_id() -> str:
    return _opaque("igt")


def new_ga4_source_binding_id() -> str:
    return _opaque("igs")


def new_topology_id() -> str:
    return _opaque("igto")


def new_policy_id() -> str:
    return _opaque("igp")


def new_edge_id() -> str:
    return _opaque("ige")


def assert_campaign_id_shape(campaign_id: str) -> str:
    if not campaign_id.startswith(f"{CAMPAIGN_ID_PREFIX}_"):
        raise ValueError(f"campaign_id must start with {CAMPAIGN_ID_PREFIX}_.")
    return validate_resource_identifier(campaign_id, field="campaign_id")
