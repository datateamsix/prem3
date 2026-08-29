"""Cross-method ChannelBinding — stable channel_id joins without fuzzy labels."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.contracts import utc_now
from app.domain.channels.models import FrozenModel
from app.domain.channels.registry import AI_SEARCH_CHANNEL_ID, cached_channel_registry
from app.domain.channels.validation import assert_channel_id_in_registry
from app.modeling.common.fingerprints import canonical_fingerprint

# Dataset A / Meridian variable names → canonical registry IDs.
# Do not rename Meridian variables; bind them.
MMM_VARIABLE_TO_CHANNEL: dict[str, str] = {
    "paid_search": "search_paid",
    "paid_search_impressions": "search_paid",
    "paid_search_spend": "search_paid",
    "shopping": "shopping_paid",
    "shopping_impressions": "shopping_paid",
    "shopping_spend": "shopping_paid",
    "paid_social": "social_paid",
    "paid_social_impressions": "social_paid",
    "paid_social_spend": "social_paid",
    "organic_sessions": "search_organic",
    "ai_search": AI_SEARCH_CHANNEL_ID,
    "ai_search_impressions": AI_SEARCH_CHANNEL_ID,
    "ai_search_spend": AI_SEARCH_CHANNEL_ID,
}


class ChannelBinding(FrozenModel):
    """Deterministic cross-method binding to one registry channel_id."""

    channel_id: str
    channel_registry_version: int
    business_profile_channel_ref: str | None = None
    data_source_refs: tuple[str, ...] = ()
    mmm_variable_refs: tuple[str, ...] = ()
    mta_grouping_refs: tuple[str, ...] = ()
    planning_allocation_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    fingerprint: str


class PlanningChannelAllocation(FrozenModel):
    """Additive planning seam — allocations pin canonical channel_id (no optimizer)."""

    allocation_id: str
    channel_id: str
    channel_registry_version: int
    amount: float | None = None
    currency: str | None = None
    label: str | None = None


def resolve_mmm_variable_to_channel(variable_name: str) -> str:
    channel_id = MMM_VARIABLE_TO_CHANNEL.get(variable_name)
    if channel_id is None:
        raise KeyError(f"No canonical channel binding for MMM variable: {variable_name}")
    assert_channel_id_in_registry(channel_id, cached_channel_registry())
    return channel_id


def build_channel_binding(
    *,
    channel_id: str,
    channel_registry_version: int | None = None,
    business_profile_channel_ref: str | None = None,
    data_source_refs: tuple[str, ...] | list[str] = (),
    mmm_variable_refs: tuple[str, ...] | list[str] = (),
    mta_grouping_refs: tuple[str, ...] | list[str] = (),
    planning_allocation_refs: tuple[str, ...] | list[str] = (),
) -> ChannelBinding:
    registry = cached_channel_registry()
    version = channel_registry_version or registry.channel_registry_version
    assert_channel_id_in_registry(channel_id, registry)
    for var in mmm_variable_refs:
        bound = resolve_mmm_variable_to_channel(var)
        if bound != channel_id:
            raise ValueError(
                f"MMM variable {var} binds to {bound}, not requested {channel_id}"
            )
    payload = {
        "channel_id": channel_id,
        "channel_registry_version": version,
        "business_profile_channel_ref": business_profile_channel_ref,
        "data_source_refs": list(data_source_refs),
        "mmm_variable_refs": list(mmm_variable_refs),
        "mta_grouping_refs": list(mta_grouping_refs),
        "planning_allocation_refs": list(planning_allocation_refs),
    }
    return ChannelBinding(
        channel_id=channel_id,
        channel_registry_version=version,
        business_profile_channel_ref=business_profile_channel_ref,
        data_source_refs=tuple(data_source_refs),
        mmm_variable_refs=tuple(mmm_variable_refs),
        mta_grouping_refs=tuple(mta_grouping_refs),
        planning_allocation_refs=tuple(planning_allocation_refs),
        fingerprint=canonical_fingerprint(payload),
    )


def music_center_default_bindings() -> tuple[ChannelBinding, ...]:
    """Contract-compatibility bindings for Music Center across BIQ/MMM/MTA/Planning."""
    return (
        build_channel_binding(
            channel_id="search_paid",
            business_profile_channel_ref="biq:music_center:paid_search",
            data_source_refs=("ga4:source=google/medium=cpc",),
            mmm_variable_refs=("paid_search", "paid_search_impressions"),
            mta_grouping_refs=("ruleset_v1:search_paid",),
            planning_allocation_refs=("plan:search_paid",),
        ),
        build_channel_binding(
            channel_id="social_paid",
            business_profile_channel_ref="biq:music_center:paid_social",
            mmm_variable_refs=("paid_social",),
            mta_grouping_refs=("ruleset_v1:social_paid",),
            planning_allocation_refs=("plan:social_paid",),
        ),
        build_channel_binding(
            channel_id="shopping_paid",
            mmm_variable_refs=("shopping",),
            mta_grouping_refs=("ruleset_v1:shopping_paid",),
            planning_allocation_refs=("plan:shopping_paid",),
        ),
        build_channel_binding(
            channel_id=AI_SEARCH_CHANNEL_ID,
            business_profile_channel_ref="biq:music_center:ai_search",
            data_source_refs=("ga4:source=chatgpt.com/medium=referral",),
            mmm_variable_refs=("ai_search",),
            mta_grouping_refs=("ruleset_v1:ai_search",),
            planning_allocation_refs=("plan:ai_search",),
        ),
        build_channel_binding(
            channel_id="direct",
            mta_grouping_refs=("ruleset_v1:direct",),
            planning_allocation_refs=("plan:direct",),
        ),
    )


def cross_method_join_on_channel_id(
    *,
    biq_registry_channel_ids: set[str],
    mmm_channel_ids: set[str],
    mta_channel_ids: set[str],
    planning_channel_ids: set[str],
) -> set[str]:
    """Intersection join — no display-label fuzzy matching."""
    return (
        biq_registry_channel_ids
        & mmm_channel_ids
        & mta_channel_ids
        & planning_channel_ids
    )
