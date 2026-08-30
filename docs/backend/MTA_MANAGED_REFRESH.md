# MTA Managed Refresh

Operational MTA tables are continuously refreshed under an approved `MTAScheduledRefreshPlan`.

## Tables

- `mta_sessions`, `mta_conversions`, `mta_touchpoints` — bounded MERGE
- `mta_journeys`, `mta_path_frequencies` — bounded deterministic rebuild
- `mta_refresh_watermark` — progress cursor

## Template

`sql/mta/scheduled/daily_refresh_v1.sql.j2` (approval required — recurring cost).

## Parameters

Lookback, settlement days, source overlap, conversion event, channel registry/grouping versions, and server-owned destination dataset are pinned on the refresh plan fingerprint.

Implementation details land in `app/modeling/mta/refresh.py` (M5-01).
