# MTA BigQuery Asset Library

Authority: `sql/mta/manifest.yaml` + Jinja templates under `sql/mta/`.

Production SQL must resolve through the asset registry/compiler — not large string
literals in handlers. Small test fragments are allowed exceptions.

## Asset classes

| Class | Examples |
|---|---|
| BIGQUERY_UDF | `channel_grouping_v1`, `channel_grouping_current` |
| BIGQUERY_DDL | operational + run output tables |
| BIGQUERY_SOURCE_QUERY | GA4 last-click / collected fallback |
| BIGQUERY_DML | MERGE sessions/conversions/touchpoints; journey/path rebuild; watermark |
| BIGQUERY_VALIDATION | uniqueness, journey ordering, outputs |
| BIGQUERY_SCHEDULED_QUERY | `daily_refresh_v1` |

Each entry carries version, path, template params, dependencies, write_mode / grain,
approval class, and fingerprint policy.

## Fingerprints

Template asset/version + params + rendered SQL + target object + dependency versions.
Lookback, source binding, grouping version, and compiler policy changes yield different
fingerprints when they change execution semantics.
