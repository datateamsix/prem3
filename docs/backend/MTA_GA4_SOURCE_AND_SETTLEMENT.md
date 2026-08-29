# MTA GA4 Source and Settlement (M5-00)

## Discovery

Recognized datasets: `analytics_<property_id>`

Tables: `events_YYYYMMDD` (canonical), `events_intraday_YYYYMMDD` (preview/health only).

## Settlement

`GA4SettlementPolicy.DAILY_SETTLED` excludes recent unstable days (default lag 3)
because GA4 daily export shards may receive late events.

Intraday must never silently become canonical attribution evidence.

## Traffic source policy

Versioned `SessionTrafficSourcePolicy`:

- `GA4_SESSION_LAST_CLICK_V1` when `session_traffic_source_last_click` is present
- `FIRST_VALID_COLLECTED_SOURCE_V1` fallback

Every input contract pins policy + fingerprint.

## Identity

`IdentityStrategy` options: pseudo-only, user-id preferred with pseudo fallback,
user-id only. Do not silently stitch across devices.
