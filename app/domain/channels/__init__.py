"""Canonical channel registry domain — one channel_id contract across PreM3."""

from __future__ import annotations

from app.domain.channels.bindings import (
    ChannelBinding,
    PlanningChannelAllocation,
    build_channel_binding,
    cross_method_join_on_channel_id,
    music_center_default_bindings,
    resolve_mmm_variable_to_channel,
)
from app.domain.channels.compiler import (
    extract_udf_literal_channel_ids,
    load_channel_grouping_rules,
)
from app.domain.channels.models import (
    ChannelDefinition,
    ChannelGroupingApproval,
    ChannelGroupingProposal,
    ChannelGroupingProvisioningReceipt,
    ChannelGroupingRule,
    ChannelGroupingRuleSet,
    ChannelRegistry,
)
from app.domain.channels.registry import AI_SEARCH_CHANNEL_ID, cached_channel_registry
from app.domain.channels.service import ChannelService
from app.domain.channels.validation import (
    ChannelValidationError,
    assert_channel_id_in_registry,
    assert_udf_outputs_in_registry,
    require_ai_search,
)

__all__ = [
    "AI_SEARCH_CHANNEL_ID",
    "ChannelBinding",
    "ChannelDefinition",
    "ChannelGroupingApproval",
    "ChannelGroupingProposal",
    "ChannelGroupingProvisioningReceipt",
    "ChannelGroupingRule",
    "ChannelGroupingRuleSet",
    "ChannelRegistry",
    "ChannelService",
    "ChannelValidationError",
    "PlanningChannelAllocation",
    "assert_channel_id_in_registry",
    "assert_udf_outputs_in_registry",
    "build_channel_binding",
    "cached_channel_registry",
    "cross_method_join_on_channel_id",
    "extract_udf_literal_channel_ids",
    "load_channel_grouping_rules",
    "music_center_default_bindings",
    "require_ai_search",
    "resolve_mmm_variable_to_channel",
]
