"""Validate channel IDs and grouping rule sets against the registry."""

from __future__ import annotations

import re

from app.domain.channels.models import ChannelGroupingRuleSet, ChannelRegistry
from app.domain.channels.registry import AI_SEARCH_CHANNEL_ID


class ChannelValidationError(ValueError):
    pass


def assert_channel_id_in_registry(channel_id: str, registry: ChannelRegistry) -> None:
    if channel_id not in registry.channel_ids():
        raise ChannelValidationError(
            f"Unknown channel_id {channel_id!r} is not in registry v{registry.channel_registry_version}."
        )


def assert_udf_outputs_in_registry(
    output_channel_ids: set[str] | frozenset[str] | list[str],
    registry: ChannelRegistry,
) -> None:
    known = registry.channel_ids()
    unknown = sorted(set(output_channel_ids) - known)
    if unknown:
        raise ChannelValidationError(
            f"UDF outputs not in channel registry: {', '.join(unknown)}"
        )


def validate_ruleset_against_registry(
    ruleset: ChannelGroupingRuleSet, registry: ChannelRegistry
) -> None:
    assert_channel_id_in_registry(ruleset.fallback_channel_id, registry)
    priorities: set[int] = set()
    for rule in ruleset.rules:
        if not rule.enabled:
            continue
        assert_channel_id_in_registry(rule.output_channel_id, registry)
        if rule.priority in priorities:
            raise ChannelValidationError(f"Duplicate rule priority {rule.priority}.")
        priorities.add(rule.priority)
        for pattern in (
            rule.source_regex,
            rule.medium_regex,
            rule.campaign_regex,
        ):
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ChannelValidationError(
                        f"Invalid regex in rule {rule.rule_id}: {exc}"
                    ) from exc


def display_name_change_preserves_id(
    *,
    before: ChannelRegistry,
    after: ChannelRegistry,
    channel_id: str,
) -> bool:
    left = before.get(channel_id)
    right = after.get(channel_id)
    if left is None or right is None:
        return False
    return left.channel_id == right.channel_id


def require_ai_search(registry: ChannelRegistry) -> None:
    if AI_SEARCH_CHANNEL_ID not in registry.channel_ids():
        raise ChannelValidationError("Canonical registry must include ai_search.")
