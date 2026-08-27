# IG-04 completion report

**Date:** 2026-08-27  
**Status:** Unified GA4 analytical plane + canonical identity resolution implemented on an isolated worktree. Not pushed unless requested.

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-04` |
| Branch | `feature/prem3-ig-04-unified-ga4-identity-plane` |
| Base HEAD | `d30d4f79cd0fdbc109a77153cd65b20ad64e1e40` |
| Push | requested after implementation |

M5-02A, MTA runtime, MMM, P6, and the M3 worktree were not modified. `uv.lock` left untracked.

## B. Topology consumption

Compilation fails closed unless `GA4TopologyReadinessReceipt.state` is `GA4_TOPOLOGY_READY`. `topology_id` and topology fingerprint are pinned on `UnifiedAnalyticsCompilation`.

## C. Location

Same-location only. `CROSS_LOCATION` / `UNKNOWN_LOCATION` → `CROSS_LOCATION_REVIEW_REQUIRED` / `BQ_LOCATION_INCOMPATIBLE`. No copy/replication. No fabricated unified table.

## D. Overlap

Never silent UNION. `MASTER_PLUS_REGIONAL` without policy → `OVERLAP_POLICY_REQUIRED`. `DEDUPE_REQUIRED` stays blocked (`DEDUPE_POLICY_REQUIRED` / `DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY`). Documented exclusion SQL for disjoint, master-authoritative, regional-authoritative, and partitioned-by-market.

## E. Settlement

Imported `GA4SettlementPolicy`. Final compile is `DAILY_SETTLED` unless explicitly `PREVIEW_INTRADAY`. Mixing `events_intraday` into settled artifacts issues `INTRADAY_MIXED_INTO_SETTLED`.

## F. Market resolution

Reuses IG-01 `resolve_market`. Property-bound single declared market resolves. `geo.country` is never implicit `market_id`.

## G. Channel resolution

Channel Registry is authority. Exact approved source/medium binding → grouping-rule predicates → Direct preserved → `UNRESOLVED`. Provider is not channel. `DirectTreatmentPolicy` is compile config, not global delete.

## H. Campaign resolution

Calls IG-03 `CampaignIdentityResolver` only. `utm_campaign` never resolves. Conflicts stay `campaign_id=NULL` + `REVIEW_REQUIRED`. `parent_campaign_id` is metadata. Unresolved campaign does not globally block `READY` unless `campaign_slice_required`.

## I. Audience

`audience_id` only when `AudienceExternalBinding` matches a proven provider audience identifier. Multi-provider ≠ membership.

## J. Session / journey keys

Session: `SHA256(ga4_property_id | subject_key | ga_session_id)` (BQ). Journey identity key is project-scoped, not a person ID, not Firestore, not API person fields. `MULTI_MARKET_JOURNEY` is explicit.

## K. Artifacts

Dataset `prem3_modeling`. Tables `ga4_sessions_unified_{compilation_id}`, `mta_session_touchpoints_{compilation_id}`, `mta_journeys_{compilation_id}`. Optional `_current` after schema + read-back. Does not overwrite M5-01 operational MERGE tables.

## L. Execution

In-process fingerprinted SQL/plan + `InMemoryAnalyticalAdapter`. No new Cloud Run Job. No fabricated live BQ success. No row-scale HTTP ingest.

## M. Persistence

`tenants/{tid}/workspaces/{wid}/identity_graph/current/{analytics_compilations,analytics_receipts,analytics_artifacts}/...`

Metadata, refs, counts, fingerprints only. No `put_events`. No `user_pseudo_id` in Firestore docs.

## N. Privacy

Walker still rejects person, budget, event, and performance keys on control-plane payloads. Row schemas use hashed `session_id` / `subject_key`. `user_pseudo_id` / `user_id` documented as BQ-only.

## O. APIs

Prefix `/v1/projects/{project_id}/identity-graph`:

- `GET .../analytics`
- `POST .../analytics/compile`
- `GET .../analytics/readiness`
- `GET .../analytics/artifacts`
- `GET .../analytics/issues`

Tenant never from client. Cross-project 404. No row payloads. No provider writes.

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `d6d253cc4815fa83dd26af27c4d6fb06d90600ac192f61ddf7681b68ccf89446`.

## P. Tests

Spec-named §§65–77: topology, overlap, market, channel, campaign, audience, session keys, privacy, settlement, artifacts/fingerprint, readiness, API + fake-BQ, Firestore.

**244 passed** (IG-00/01/02/02A/03 plus IG-04).

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py tests/unit/test_firestore_client.py tests/unit/data_foundation/test_durable_stores.py -q
# 310 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py app/service/product_stores.py tests/unit/identity_graph
# All checks passed
```

## Q. Docs / ADRs

Created: `UNIFIED_GA4_ANALYTICAL_PLANE.md`, `GA4_OVERLAP_AND_LOCATION_GOVERNANCE.md`, `CANONICAL_ANALYTICAL_IDENTITY_RESOLUTION.md`, `MTA_INPUT_ANALYTICAL_CONTRACT.md`, `IG_04_COMPLETION_REPORT.md`.

Updated: `MARKETING_IDENTITY_GRAPH_ARCHITECTURE.md` (IG-ADR-061…075), `GA4_SOURCE_TOPOLOGY.md`, `CAMPAIGN_IDENTITY_RESOLUTION.md`.

## R. Isolation

Did not edit `app/modeling/**` except importing existing MTA enums. Did not edit `sql/mta/manifest.yaml`, DP6, `investment_planning/**`, or Meridian. New SQL under `sql/identity_graph/`.

## S. M5-03 handoff

`M5_03AnalyticalHandoff`: artifact refs, topology/identity fingerprints, available market/channel/campaign IDs, coverage counts, issues. `mta_result_ready=False`. Campaign-level Markov validity remains M5-03 preflight. Do not change DP6.

## T. Exposure handoff

Resolved market/channel/campaign/optional audience + provider provenance. No metrics.

## U. Planning handoff

Coverage metadata only. Do not expand P6 grain.

## V. Blockers

V1 does not execute live BigQuery. `DEDUPE_REQUIRED` remains not analytically ready. Provider discovery remains the IG-03 stub. No activation routes.
