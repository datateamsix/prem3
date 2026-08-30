# MTA BigQuery Asset Library

Source-controlled BigQuery + configuration assets for PreM3 MTA.

Ingested from PreM3 MTA Asset Library V1 into:

- `assets/channels/` — canonical channel registry + grouping rules
- `assets/mta/` — model registry and refresh/analysis config schemas
- `sql/mta/` — Jinja SQL templates (UDF, DDL, source, DML, scheduled, validation)
- `sql/mta/manifest.yaml` — asset index with repo-relative paths

## Core rule

**One canonical channel contract across PreM3.**

Business IQ, Data Foundation, MMM, MTA, Planning, and Decision Intelligence must use the same stable `channel_id` values.

The MTA channel-grouping UDF maps observed GA4 `source / medium / campaign` values into that canonical registry. It does not invent a separate MTA taxonomy.

## User editing

The normal UI should edit a structured, ordered `ChannelGroupingRuleSet`, not raw SQL.

The backend:

1. validates all target channel IDs against the Channel Registry;
2. compiles immutable BigQuery UDF version `channel_grouping_vN`;
3. validates the routine on discovered traffic values + test fixtures;
4. fingerprints the exact SQL and routine;
5. writes the routine only after approval;
6. optionally advances a convenience `channel_grouping_current` alias;
7. pins historical MTA runs to the immutable version used.

## Operational pipeline

Continuously refreshed:

- `mta_sessions`
- `mta_conversions`
- `mta_touchpoints`
- `mta_journeys`
- `mta_path_frequencies`
- `mta_refresh_watermark`

Immutable MTA analyses then reference an exact source cutoff, lookback, channel version, and input fingerprint.

## Incremental write policy

- Sessions, conversions, touchpoints: bounded `MERGE`.
- Journeys and path frequencies: bounded deterministic rebuild of impacted conversion partitions.
- Historical attribution result tables: immutable run-scoped assets.
- Scheduled refresh: BigQuery scheduled query or equivalent managed transfer, provisioned only after user approval.

## Model configuration

Backend supports First Touch, Last Touch, Last Non-Direct, Linear, Time Decay, Position Based, Markov, and Shapley. Frontend may filter a subset; result schema stays model-neutral.

## AI Search / Answer Engines

Registry V1 includes `ai_search`. The default UDF recognizes identifiable referrals from common AI-native answer/search products. This does not imply all AI-mediated discovery is observable.
