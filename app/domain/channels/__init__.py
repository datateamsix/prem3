"""Canonical channel registry domain — one channel_id contract across PreM3."""

from __future__ import annotations

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
    "ChannelDefinition",
    "ChannelGroupingApproval",
    "ChannelGroupingProposal",
    "ChannelGroupingProvisioningReceipt",
    "ChannelGroupingRule",
    "ChannelGroupingRuleSet",
    "ChannelRegistry",
    "ChannelService",
    "ChannelValidationError",
    "assert_channel_id_in_registry",
    "assert_udf_outputs_in_registry",
    "cached_channel_registry",
    "extract_udf_literal_channel_ids",
    "load_channel_grouping_rules",
    "require_ai_search",
]
