# IG-01 completion report

**Date:** 2026-08-26  
**Status:** Phase A gate + Phase B topology/coverage implemented on an isolated worktree. Not pushed. Not committed (working tree dirty pending user commit).

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-01` |
| Branch | `feature/prem3-ig-01-market-ga4-topology` |
| IG-00 base HEAD | `53f62b5891f22976d58b7df65bd191f07d5ddd1e` |
| Final HEAD | same SHA until commit; working tree dirty with IG-01 files |
| Push | not requested |

M5-02A, MTA runtime, MMM, and P6 worktrees were not modified.

## B. IG-00 addendum

Completed before IG-01 branched (on `prem3-ig-00`, committed as `53f62b5`):

- `docs/backend/MARKETING_IDENTITY_GRAPH_ARCHITECTURE.md` — Foundation tree, Persona/Audience/Campaign definitions, Campaign Ledger V1 fields
- `docs/backend/IDENTITY_GRAPH_PRIVACY_BOUNDARY.md` — hashed PII and audience membership prohibited
- `docs/backend/CAMPAIGN_IDENTITY_AND_TRACKING_CONTRACT.md` — reserved `persona_ids[]` / `audience_ids[]`
- `docs/backend/IG_00_FREEZE_REPORT.md` — Section 0 reservation
- Enum/schema reservation only: `PERSONA`, `AUDIENCE` nodes and audience/persona edges; no CRUD/persistence

Audience and Persona remain reserved only.

## C. Canonical market identity

- Contract: `CanonicalMarket`
- ID: server-generated `mkt_<opaque>` (`uuid4().hex[:20]`), URL-safe, project-scoped, never reused, not derived from display name or ISO country
- Kinds: `COUNTRY` · `REGION` · `MULTI_COUNTRY_REGION` · `SUBNATIONAL` · `GLOBAL` · `CUSTOM`
- Custom regions (DACH, North America, US East, Global, Enterprise North America) are representable

## D. BIQ bridge

- Contract: `BusinessMarketBinding`
- `business_market_ref` = exact BIQ `Market.market_id` string
- Idempotent on `(tenant, project, snapshot_id, business_market_ref)`
- Mapping methods: `SERVER_CREATED_FROM_BUSINESS_IQ` · `USER_CONFIRMED` · `EXACT_EXISTING_BINDING` · `MIGRATED_LEGACY_REF` · `UNRESOLVED`
- Historical profile snapshots are not mutated (proven by `test_historical_business_profile_not_mutated`)
- Display-name-only never merges; ambiguity → `REVIEW_REQUIRED`

## E. Blocker closure

`BUSINESS_IQ_MARKET_IDENTITY_REQUEST` is **resolved by IG-01**. The IG-00 historical record is retained in `IG_00_FREEZE_REPORT.md` and `MARKET_RESOLUTION_POLICY.md`.

## F. GA4 topology

Representable and tested:

1. Single master property
2. Property per market
3. Multiple properties, one BQ project
4. Properties across multiple BQ projects
5. Master + regional
6. Cross-location datasets

Discovery consumes caller-supplied DF/BQ table metadata. Empty `tables` → `DISCOVERY_NOT_CONFIGURED` (not invented READY).

## G. Market resolution

Allow-list: `PROPERTY_BOUND` · `STREAM_BOUND` · `CUSTOM_DIMENSION` · `HOSTNAME_MAPPING` · `GEO_MAPPING` · `USER_CONFIRMED_RULE` · `UNRESOLVED`.

`geo.country` is not implicit. Missing policy + `GEO_MAPPING` → `GEO_MAPPING_NOT_IMPLICIT_DEFAULT`. Master covering several markets without a policy → `MARKET_RESOLUTION_REQUIRED`.

## H. Market coverage

`GA4MarketCoverage` statuses: `COMPLETE` · `PARTIAL` · `MISSING` · `REVIEW_REQUIRED` · `UNKNOWN`.

`GA4TopologyReadinessReceipt` states: `GA4_TOPOLOGY_READY` · `GA4_TOPOLOGY_REVIEW_REQUIRED` · `GA4_TOPOLOGY_INCOMPLETE`.

Does not broaden `DATA_FOUNDATION_READY`.

## I. Source overlap

`DISJOINT` · `MASTER_AUTHORITATIVE` · `REGIONAL_AUTHORITATIVE` · `PARTITIONED_BY_MARKET` may be ready when other requirements pass.

`DEDUPE_REQUIRED` and `REVIEW_REQUIRED` are not analytically ready. No silent UNION.

## J. BigQuery location

Recorded on each source. Topology class: `SAME_LOCATION` · `CROSS_LOCATION` · `UNKNOWN_LOCATION`.

Cross-location → `CROSS_LOCATION_REVIEW_REQUIRED`, not `direct_union_ready`. Unknown location → not ready for unified compilation. No replication in IG-01.

## K. Persistence / privacy

In-memory store. Reserved Firestore path unchanged.

May store: CanonicalMarket, BusinessMarketBinding, source/topology/policy metadata, coverage/readiness receipts, fingerprints.

Must not store: raw events, `user_id` / `user_pseudo_id` / device IDs, audience members, budget values.

## L. APIs / contracts

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `3cbd34ac7e3a8d5c5f8889fa690c2d82e9485813be5e10d007abebf9376ef001`.

Routes (tenant never client-supplied):

- `GET|POST /v1/projects/{project_id}/identity-graph/markets`
- `GET|POST /v1/projects/{project_id}/identity-graph/sources`
- `POST /v1/projects/{project_id}/identity-graph/sources/discover`
- `GET /v1/projects/{project_id}/identity-graph/ga4-topology`
- `POST /v1/projects/{project_id}/identity-graph/ga4-topology/validate`

No fake success handlers.

## M. Tests

```text
uv run --extra dev pytest tests/unit/identity_graph -q
```

**77 passed** (includes spec-named tests in §32–38).

## N. Regressions

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py -q
# 128 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py tests/unit/identity_graph
# All checks passed
```

M5-02A DP6/Cloud E2E was not run and was not modified. Planning/P6 was not touched.

## O. IG-02 handoff

Campaign Ledger may consume:

- `CanonicalCampaign.market_ids[]` = canonical `mkt_` IDs
- `channel_ids[]` = Channel Registry IDs
- reserved empty `persona_ids[]` / `audience_ids[]` (not members)
- documented V1 fields in `MARKETING_IDENTITY_GRAPH_ARCHITECTURE.md`

Do not persist budget, spend, attribution, or person identity on `CanonicalCampaign`.

## P. IG-04 handoff

Unified GA4 compiler may consume:

- `GA4SourceTopology.topology_id` / `topology_kind` / `source_binding_ids[]`
- `GA4PropertySourceBinding` (`ga4_source_binding_id`, BQ project/dataset/location, `declared_market_ids[]`)
- `MarketResolutionPolicy.policy_id`
- `GA4TopologyReadinessReceipt` (must be `GA4_TOPOLOGY_READY`)
- `location_class` — do not compile a direct union when `CROSS_LOCATION` or `UNKNOWN_LOCATION`

Do not assume one raw dataset. Do not UNION master+regional without overlap policy.

## Q. M5-03 handoff

`MTAIdentityTouchpointRefs`:

- `market_id` — canonical Identity Graph market ID
- `ga4_source_binding_id`
- `market_resolution_method`

`mta_touchpoints` SQL and DP6 were not changed.

## R. Blockers

None for IG-01 acceptance. Live BigQuery discovery against customer projects is not wired into the HTTP discover handler beyond caller-supplied table metadata; empty input is typed `DISCOVERY_NOT_CONFIGURED`, not fabricated READY.

Not committed. Not pushed.
