# MTA BigQuery Output Contract

## Operational tables

`mta_sessions`, `mta_conversions`, `mta_touchpoints`, `mta_journeys`, `mta_path_frequencies`, `mta_refresh_watermark`

## Run-scoped outputs

`mta_source_manifest_<run_id>`, touchpoints/journeys/path frequencies snapshots, `mta_attribution_channel_results_<run_id>`, `mta_model_comparison_<run_id>`, Markov transition/removal tables, Shapley results when enabled, `mta_run_manifest_<run_id>`

## Current views

Advance `*_current` only after verified SUCCEEDED read-back.

SQL templates live under `sql/mta/` and are indexed by `sql/mta/manifest.yaml`.
