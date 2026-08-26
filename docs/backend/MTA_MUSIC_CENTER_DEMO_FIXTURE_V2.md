# Music Center MTA Demo Fixture v2

| Field | Value |
|---|---|
| fixture_id | `music_center_mta_demo_v2` |
| fixture_version | `v2` |
| evidence_authority | `SYNTHETIC_DEMO` |
| source_type | `SYNTHETIC_GA4_BIGQUERY` |
| dataset | `modelready-m3.analytics_music_center_synthetic` |
| date range | `2024-09-01` – `2024-09-30` |
| seed | `20240901` |

June 2024 v1 shards (`2024-06-01`–`2024-06-07`) are not overwritten.

Generator: `app/modeling/mta/music_center_fixture_v2.py` and
`scripts/mta/music_center_demo_fixture_v2.py`.

Channels exercised: `search_paid`, `search_organic`, `social_paid`, `display`,
`email`, `direct`, `ai_search` (chatgpt.com / perplexity.ai / gemini.google.com).
One sparse SMS journey remains for LOW_OBSERVABILITY.

Roles and shares are derived from real DP6 outputs — not hardcoded.
