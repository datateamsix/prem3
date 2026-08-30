"""Load and compile ChannelGroupingRuleSet assets."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.domain.channels.models import ChannelGroupingRule, ChannelGroupingRuleSet
from app.domain.channels.registry import cached_channel_registry, repo_root
from app.domain.channels.validation import validate_ruleset_against_registry
from app.modeling.common.fingerprints import canonical_fingerprint


def default_rules_path(*, version: int = 1) -> Path:
    return repo_root() / "assets" / "channels" / f"channel_grouping_rules_v{version}.yaml"


def load_channel_grouping_rules(
    path: Path | None = None, *, version: int = 1
) -> ChannelGroupingRuleSet:
    rules_path = path or default_rules_path(version=version)
    raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    rules = tuple(
        ChannelGroupingRule(
            rule_id=str(row["id"]),
            priority=int(row["priority"]),
            output_channel_id=str(row["output_channel_id"]),
            source_exact=row.get("source_exact"),
            source_regex=row.get("source_regex"),
            medium_exact=row.get("medium_exact"),
            medium_regex=row.get("medium_regex"),
            campaign_exact=row.get("campaign_exact"),
            campaign_regex=row.get("campaign_regex"),
            enabled=bool(row.get("enabled", True)),
            description=row.get("description"),
        )
        for row in raw.get("rules", [])
    )
    payload = {
        "version": int(raw.get("version", version)),
        "fallback_channel_id": raw.get("fallback_channel_id", "other"),
        "rules": [
            {
                "rule_id": r.rule_id,
                "priority": r.priority,
                "output_channel_id": r.output_channel_id,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }
    ruleset = ChannelGroupingRuleSet(
        version=int(raw.get("version", version)),
        contract=str(raw.get("contract", "PREM3_CHANNEL_GROUPING_RULESET")),
        fallback_channel_id=str(raw.get("fallback_channel_id", "other")),
        rules=rules,
        fingerprint=canonical_fingerprint(payload),
    )
    validate_ruleset_against_registry(ruleset, cached_channel_registry(version))
    return ruleset


def extract_udf_literal_channel_ids(sql_text: str) -> set[str]:
    """Pull THEN/ELSE 'channel_id' literals from CASE UDF bodies."""
    return set(
        re.findall(r"(?:THEN|ELSE)\s+'([a-z0-9_]+)'", sql_text, flags=re.IGNORECASE)
    )
