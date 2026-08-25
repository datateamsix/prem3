# MTA Live BigQuery Proof — Music Center SYNTHETIC_DEMO

**Evidence label:** `SYNTHETIC_DEMO`  
**Path:** production `MTAProvisioningService` (no demo-only architecture)  
**Target:** authorized PreM3 GCP project (`GOOGLE_CLOUD_PROJECT`, default `modelready-m3`)  
**Dataset:** `prem3_modeling` operational assets  
**Source:** `analytics_music_center_synthetic.events_*` (GA4-compatible)

## What is proven

1. Load Music Center synthetic GA4 events (incl. `ai_search` traffic)
2. Provision UDF `channel_grouping_v1` + operational DDL; read-back
3. Classify fixture through live UDF; registry-valid outputs; `ai_search` mapping
4. Refresh ×2 idempotency (sessions/conversions/touchpoints/journeys/path frequencies; zero duplicate keys)
5. Source correction reconcile + removal of stale rows
6. Watermark advances only after successful validation
7. Scheduled-query create / read-back / disable via Data Transfer API

## How to run

```bash
uv sync
uv run pytest tests/integration/test_mta_m5_01a_live_bq.py -m live_bq -v
```

## Physical design (operational)

| Table | Partition | Cluster |
|---|---|---|
| `mta_sessions` | `source_date` | `canonical_channel_id` |
| `mta_conversions` | `conversion_date` | `conversion_event` |
| `mta_touchpoints` | `touchpoint_date` | `canonical_channel_id` |
| `mta_journeys` | `conversion_date` | `conversion_event` |
| `mta_path_frequencies` | `conversion_date` | `conversion_event` |

## GA4 compiler

Preferred policy: `session_traffic_source_last_click` via `ga4_sessions_last_click_v1`.  
Fallback asset: `ga4_sessions_collected_fallback_v1`. Runs pin schema/policy/asset fingerprints.

Do not claim live proof that did not run. Record job IDs and resource names in the
completion report when executed.
