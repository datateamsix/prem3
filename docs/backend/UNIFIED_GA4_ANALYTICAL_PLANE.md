# Unified GA4 analytical plane

**Mission:** IG-04  
**Contracts:** `AnalyticalSourceSelection`, `UnifiedAnalyticsCompilation`, `UnifiedAnalyticsReadinessReceipt`, `M5_03AnalyticalHandoff`

IG-04 compiles proven Identity Graph identity into versioned customer-owned analytical artifacts. It does not invent `market_id`, `channel_id`, or `campaign_id` from display strings.

## Artifacts

Customer dataset: `prem3_modeling`. Compilation-scoped tables; never overwrite M5-01 operational `mta_touchpoints` / `mta_sessions`.

| Table | Grain |
|---|---|
| `ga4_sessions_unified_{compilation_id}` | property-scoped session |
| `mta_session_touchpoints_{compilation_id}` | MTA-compatible touchpoint, no credit |
| `mta_journeys_{compilation_id}` | project-scoped journey identity key |

Optional `_current` pointer only after schema + read-back succeed.

## Session key

`SHA256(ga4_property_id \| subject_key \| ga_session_id)` in BigQuery only. `ga_session_id` is not globally unique.

Journey identity key is project-scoped and deterministic. It is not a PreM3 person ID, not stored as a Firestore person field, and not returned as a person identifier on HTTP APIs.

`user_pseudo_id` / `user_id` may exist **only** as BQ analytical keys.

## Compiler phases

`SOURCE_VALIDATE` → `TOPOLOGY_VALIDATE` → `LOCATION_VALIDATE` → `OVERLAP_VALIDATE` → `SESSION_COMPILE` → `MARKET_RESOLVE` → `CHANNEL_RESOLVE` → `CAMPAIGN_RESOLVE` → `TOUCHPOINT_COMPILE` → `JOURNEY_COMPILE` → `SCHEMA_VALIDATE` → `READ_BACK_VERIFY` → `READY`

V1 execution is in-process against a fake/in-memory analytical adapter. Firestore stores refs, counts, and fingerprints only.

## APIs

`/v1/projects/{project_id}/identity-graph/analytics/*`

Responses are metadata (`compilation_id`, status, artifact refs, receipt, issues, fingerprint). No row payloads. Tenant is never client-supplied.

See [GA4_OVERLAP_AND_LOCATION_GOVERNANCE.md](GA4_OVERLAP_AND_LOCATION_GOVERNANCE.md), [CANONICAL_ANALYTICAL_IDENTITY_RESOLUTION.md](CANONICAL_ANALYTICAL_IDENTITY_RESOLUTION.md), and [MTA_INPUT_ANALYTICAL_CONTRACT.md](MTA_INPUT_ANALYTICAL_CONTRACT.md).
