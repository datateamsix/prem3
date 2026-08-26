"""Versioned channel grouping — immutable routine versions."""

from __future__ import annotations

import re

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import MTAChannelGrouping, MTAChannelGroupingRule


class ChannelGroupingValidationError(ValueError):
    pass


def compile_channel_grouping_sql(grouping: MTAChannelGrouping) -> str:
    """Compile a deterministic BigQuery SQL UDF body for channel grouping."""
    lines = [
        f"-- Prem3 MTA channel grouping {grouping.version}",
        f"-- fingerprint={grouping.fingerprint}",
        "CASE",
    ]
    ordered = sorted(grouping.rules, key=lambda r: r.priority)
    for rule in ordered:
        preds: list[str] = []
        if rule.source_pattern:
            preds.append(f"REGEXP_CONTAINS(LOWER(source), r'{_escape(rule.source_pattern)}')")
        if rule.medium_pattern:
            preds.append(f"REGEXP_CONTAINS(LOWER(medium), r'{_escape(rule.medium_pattern)}')")
        if rule.campaign_pattern:
            preds.append(
                f"REGEXP_CONTAINS(LOWER(IFNULL(campaign, '')), r'{_escape(rule.campaign_pattern)}')"
            )
        if not preds:
            continue
        lines.append(
            f"  WHEN {' AND '.join(preds)} THEN '{rule.canonical_channel_id}'"
        )
    lines.append(
        "  WHEN LOWER(medium) = '(none)' OR LOWER(source) = '(direct)' "
        f"THEN '{grouping.direct_channel_id}'"
    )
    lines.append(f"  ELSE '{grouping.fallback_channel_id}'")
    lines.append("END")
    return "\n".join(lines)


def _escape(pattern: str) -> str:
    return pattern.replace("\\", "\\\\").replace("'", "\\'")


def validate_channel_grouping(grouping: MTAChannelGrouping) -> None:
    if not grouping.rules:
        raise ChannelGroupingValidationError("Channel grouping requires at least one rule.")
    priorities = [r.priority for r in grouping.rules]
    if len(priorities) != len(set(priorities)):
        raise ChannelGroupingValidationError("Duplicate rule priorities are not allowed.")
    ids = [r.rule_id for r in grouping.rules]
    if len(ids) != len(set(ids)):
        raise ChannelGroupingValidationError("Duplicate rule_ids are not allowed.")
    for rule in grouping.rules:
        for pattern in (rule.source_pattern, rule.medium_pattern, rule.campaign_pattern):
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ChannelGroupingValidationError(
                        f"Invalid regex in rule {rule.rule_id}: {exc}"
                    ) from exc
    sql = compile_channel_grouping_sql(grouping)
    if "CREATE OR REPLACE" in sql.upper():
        raise ChannelGroupingValidationError("Compiled SQL must not include CREATE OR REPLACE.")


def build_channel_grouping(
    *,
    version: str,
    rules: tuple[MTAChannelGroupingRule, ...] | list[MTAChannelGroupingRule],
    created_by: str,
    business_profile_snapshot_id: str | None = None,
    approved_by: str | None = None,
) -> MTAChannelGrouping:
    rule_tuple = tuple(rules)
    payload = {
        "version": version,
        "rules": [r.model_dump(mode="json") for r in rule_tuple],
        "business_profile_snapshot_id": business_profile_snapshot_id,
    }
    fingerprint = canonical_fingerprint(payload)
    grouping = MTAChannelGrouping(
        channel_grouping_id=f"cg_{fingerprint[:16]}",
        version=version,
        business_profile_snapshot_id=business_profile_snapshot_id,
        rules=rule_tuple,
        created_by=created_by,
        approved_by=approved_by,
        fingerprint=fingerprint,
        routine_name=f"channel_grouping_{version}",
    )
    sql = compile_channel_grouping_sql(grouping)
    sql_fp = canonical_fingerprint({"sql": sql})
    grouping = grouping.model_copy(update={"sql_fingerprint": sql_fp})
    validate_channel_grouping(grouping)
    return grouping


def assert_grouping_version_immutable(
    *,
    existing_version: str,
    proposed_version: str,
    existing_fingerprint: str,
    proposed_fingerprint: str,
) -> None:
    if existing_version == proposed_version and existing_fingerprint != proposed_fingerprint:
        raise ChannelGroupingValidationError(
            f"Cannot mutate channel_grouping_{existing_version}; create a new version."
        )


DEFAULT_MUSIC_CENTER_RULES: tuple[MTAChannelGroupingRule, ...] = (
    MTAChannelGroupingRule(
        rule_id="paid-search",
        priority=10,
        source_pattern=r"google|bing",
        medium_pattern=r"cpc|ppc|paid",
        canonical_channel_id="Paid Search",
    ),
    MTAChannelGroupingRule(
        rule_id="paid-social",
        priority=20,
        source_pattern=r"facebook|instagram|meta|tiktok|linkedin",
        medium_pattern=r"paid|cpc|cpm|social",
        canonical_channel_id="Paid Social",
    ),
    MTAChannelGroupingRule(
        rule_id="display",
        priority=30,
        medium_pattern=r"display|banner|cpm",
        canonical_channel_id="Display",
    ),
    MTAChannelGroupingRule(
        rule_id="organic-search",
        priority=40,
        medium_pattern=r"organic",
        canonical_channel_id="Organic Search",
    ),
    MTAChannelGroupingRule(
        rule_id="email",
        priority=50,
        medium_pattern=r"email|e-mail",
        canonical_channel_id="Email",
    ),
)
