"""Channel Registry resolution. Provider is not channel. Direct is preserved, not erased."""

from __future__ import annotations

import re

from app.domain.channels.compiler import load_channel_grouping_rules
from app.domain.channels.models import ChannelGroupingRuleSet, ChannelRegistry
from app.domain.channels.registry import cached_channel_registry
from app.identity_graph.analytics.contracts import (
    ApprovedSourceMediumBinding,
    ChannelIdentityResolution,
)
from app.identity_graph.enums import (
    BindingStatus,
    ChannelResolutionMethod,
    RowResolutionStatus,
)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _rule_matches(rule, *, source: str, medium: str, campaign: str) -> bool:
    if not rule.enabled:
        return False
    has_predicate = any(
        [
            rule.source_exact,
            rule.source_regex,
            rule.medium_exact,
            rule.medium_regex,
            rule.campaign_exact,
            rule.campaign_regex,
        ]
    )
    if not has_predicate:
        return False
    if rule.source_exact is not None and _norm(rule.source_exact) != source:
        return False
    if rule.medium_exact is not None and _norm(rule.medium_exact) != medium:
        return False
    if rule.campaign_exact is not None and _norm(rule.campaign_exact) != campaign:
        return False
    if rule.source_regex is not None and re.search(rule.source_regex, source, re.I) is None:
        return False
    if rule.medium_regex is not None and re.search(rule.medium_regex, medium, re.I) is None:
        return False
    if rule.campaign_regex is not None and re.search(rule.campaign_regex, campaign, re.I) is None:
        return False
    return True


def resolve_channel(
    *,
    source: str | None,
    medium: str | None,
    campaign_name: str | None = None,
    provider_id: str | None = None,
    approved_bindings: tuple[ApprovedSourceMediumBinding, ...] = (),
    ruleset: ChannelGroupingRuleSet | None = None,
    registry: ChannelRegistry | None = None,
) -> ChannelIdentityResolution:
    del provider_id
    registry = registry or cached_channel_registry()
    source_n = _norm(source)
    medium_n = _norm(medium)
    campaign_n = _norm(campaign_name)
    for binding in approved_bindings:
        if binding.status != BindingStatus.APPROVED:
            continue
        if _norm(binding.source) == source_n and _norm(binding.medium) == medium_n:
            channel = registry.get(binding.channel_id)
            if channel is None:
                return ChannelIdentityResolution(
                    channel_id=None,
                    method=ChannelResolutionMethod.UNRESOLVED,
                    status=RowResolutionStatus.UNRESOLVED,
                    issues=("CHANNEL_NOT_IN_REGISTRY",),
                )
            return ChannelIdentityResolution(
                channel_id=channel.channel_id,
                channel_family_id=channel.channel_family_id,
                method=ChannelResolutionMethod.EXACT_SOURCE_MEDIUM_BINDING,
                status=RowResolutionStatus.RESOLVED,
            )
    grouping = ruleset or load_channel_grouping_rules()
    for rule in sorted(grouping.rules, key=lambda item: item.priority):
        if _rule_matches(rule, source=source_n, medium=medium_n, campaign=campaign_n):
            channel = registry.get(rule.output_channel_id)
            if channel is None:
                continue
            return ChannelIdentityResolution(
                channel_id=channel.channel_id,
                channel_family_id=channel.channel_family_id,
                method=ChannelResolutionMethod.GROUPING_RULE,
                status=RowResolutionStatus.RESOLVED,
            )
    if source_n in {"(direct)", "direct"} or medium_n in {"(none)", "(not set)"}:
        channel = registry.get("direct")
        if channel is not None:
            return ChannelIdentityResolution(
                channel_id=channel.channel_id,
                channel_family_id=channel.channel_family_id,
                method=ChannelResolutionMethod.DIRECT_PRESERVED,
                status=RowResolutionStatus.RESOLVED,
            )
    return ChannelIdentityResolution(
        channel_id=None,
        method=ChannelResolutionMethod.UNRESOLVED,
        status=RowResolutionStatus.UNRESOLVED,
        issues=("CHANNEL_UNRESOLVED",),
    )
