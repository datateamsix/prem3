"""Versioned MTA analytical policies."""

from __future__ import annotations

from datetime import date, timedelta

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import (
    GA4SettlementPolicy,
    SessionTrafficSourcePolicy,
)

# GA4 daily export tables may receive late events for up to ~3 days.
DEFAULT_SETTLEMENT_LAG_DAYS = 3


def settled_through_date(
    *,
    as_of: date,
    policy: GA4SettlementPolicy = GA4SettlementPolicy.DAILY_SETTLED,
    lag_days: int = DEFAULT_SETTLEMENT_LAG_DAYS,
) -> date | None:
    if policy is GA4SettlementPolicy.PREVIEW_INTRADAY:
        return None
    return as_of - timedelta(days=lag_days)


def select_traffic_source_policy(
    *,
    has_session_traffic_source_last_click: bool,
    has_collected_traffic_source: bool,
) -> SessionTrafficSourcePolicy:
    if has_session_traffic_source_last_click:
        return SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1
    if has_collected_traffic_source:
        return SessionTrafficSourcePolicy.FIRST_VALID_COLLECTED_SOURCE_V1
    return SessionTrafficSourcePolicy.FIRST_VALID_COLLECTED_SOURCE_V1


def traffic_source_policy_fingerprint(policy: SessionTrafficSourcePolicy) -> str:
    return canonical_fingerprint(
        {"policy": policy.value, "adapter_version": "m5-00.1"}
    )


def assert_canonical_not_intraday(
    *,
    settlement_policy: GA4SettlementPolicy,
    uses_intraday_shards: bool,
) -> None:
    if (
        settlement_policy is GA4SettlementPolicy.DAILY_SETTLED
        and uses_intraday_shards
    ):
        raise ValueError(
            "Canonical DAILY_SETTLED runs must not use events_intraday_* shards."
        )
