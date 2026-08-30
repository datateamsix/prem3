"""Channel registry service façade."""

from __future__ import annotations

from app.domain.channels.compiler import (
    extract_udf_literal_channel_ids,
    load_channel_grouping_rules,
)
from app.domain.channels.models import ChannelGroupingRuleSet, ChannelRegistry
from app.domain.channels.registry import cached_channel_registry, load_channel_registry
from app.domain.channels.validation import (
    assert_udf_outputs_in_registry,
    require_ai_search,
    validate_ruleset_against_registry,
)


class ChannelService:
    def load_registry(self, *, version: int = 1) -> ChannelRegistry:
        registry = load_channel_registry(version=version)
        require_ai_search(registry)
        return registry

    def load_ruleset(self, *, version: int = 1) -> ChannelGroupingRuleSet:
        return load_channel_grouping_rules(version=version)

    def validate_udf_sql(self, sql_text: str, *, registry_version: int = 1) -> None:
        registry = cached_channel_registry(registry_version)
        ids = extract_udf_literal_channel_ids(sql_text)
        # ELSE / fallback may appear as ELSE 'other'
        assert_udf_outputs_in_registry(ids, registry)

    def validate_ruleset(
        self, ruleset: ChannelGroupingRuleSet, *, registry_version: int = 1
    ) -> None:
        validate_ruleset_against_registry(ruleset, cached_channel_registry(registry_version))
