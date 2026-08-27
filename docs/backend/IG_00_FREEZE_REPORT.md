# IG-00 freeze report

**Date:** 2026-08-26  
**Status:** Architecture freeze complete on an isolated worktree. Not pushed. Not merged.

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-00` |
| Branch | `feature/prem3-ig-00-marketing-identity-graph` |
| Base SHA | `7204315f5483489237164b8fb7f2152ae116338f` (`feature/prem3-m5-01a-bq-provisioning-channel-governance`) |
| HEAD | same as base until commit (working tree dirty with IG-00 files) |
| Commits | none yet |
| Push | not requested |

M5-02A remains closed at `206da3880ab3624cb0823351bcaeb77013da9def` on `prem3-m5-02a` / `prem3-m5-02`. DP6 runtime and Cloud E2E were not reopened.

The previous `206da38` IG worktree/branch was removed and recreated from `7204315` per the freeze spec.

## B. Domain placement

Bounded package: `app/identity_graph/`

| File | Role |
|---|---|
| `enums.py` | Node/edge types, status, tracking, resolution, topology, authority, capability |
| `ids.py` | `cmp_` and graph-local IDs via `{prefix}_{uuid4().hex[:20]}` |
| `contracts.py` | Campaign, bindings, topology, policies, future seams |
| `fingerprint.py` | Canonical SHA-256 fingerprints |
| `relationships.py` | `MarketingIdentityEdge` |
| `resolution.py` | Precedence + hierarchy cycle checks |
| `store.py` | Protocol + in-memory store; reserved Firestore path |
| `service.py` | `CampaignIdentityService` |
| `privacy.py` | Person/budget/event field rejection |
| `errors.py` | `IdentityGraphError` |

API: `app/service/routers/identity_graph.py`, `app/service/identity_graph_models.py`. Wired in `app/service/app.py`.

Not placed in `app/modeling/mta/`, `app/business_iq/`, or `app/investment_planning/`.

Clerk `/v1/me` remains `app/service/routers/identity.py`.

Section 0 addendum (docs + enum/schema reservation only): `PERSONA`/`AUDIENCE` nodes and audience/persona edges are reserved; `CanonicalCampaign.persona_ids`/`audience_ids` default empty; privacy rejects hashed PII and audience membership. No Audience/Persona persistence or CRUD.

## C. Identity ontology

**Nodes:** `MARKET`, `CHANNEL`, `CAMPAIGN`, `PROVIDER`, `EXTERNAL_CAMPAIGN`, `GA4_PROPERTY`, `GA4_STREAM`, `BIGQUERY_GA4_SOURCE`.

**Reserved nodes (no persistence/CRUD):** `PERSONA`, `AUDIENCE`.

**Edges:** `CAMPAIGN_CHILD_OF`, `CAMPAIGN_TARGETS_MARKET`, `CAMPAIGN_USES_CHANNEL`, `CAMPAIGN_BOUND_TO_EXTERNAL`, `CAMPAIGN_TRACKED_BY`, `GA4_PROPERTY_COVERS_MARKET`, `GA4_STREAM_BELONGS_TO_PROPERTY`, `BIGQUERY_SOURCE_EXPORTS_PROPERTY`.

**Reserved edges:** `AUDIENCE_REPRESENTS_PERSONA`, `CAMPAIGN_TARGETS_AUDIENCE`, `CAMPAIGN_TARGETS_PERSONA`, `AUDIENCE_AVAILABLE_IN_MARKET`, `AUDIENCE_BOUND_TO_EXTERNAL`.

## D. Campaign contract

- ID: server-generated `cmp_<opaque>`, URL-safe, not derived from name/provider/market/channel, never reused in-store.
- Hierarchy: same project, no self-parent, cycle rejected, parent/child IDs stable.
- Scope: `market_ids[]` = BIQ market IDs; `channel_ids[]` = Channel Registry IDs; reserved empty `persona_ids[]` / `audience_ids[]` (not members).
- Status: `PLANNED` · `ACTIVE` · `PAUSED` · `COMPLETE` · `ARCHIVED`. Status does not change identity.
- No budget, attribution, or platform metrics on `CanonicalCampaign`.

## E. Tracking

`create_campaign` always creates `utm_id=<campaign_id>` (`PREM3_UTM_ID`).  
`CampaignTrackingInstructions` returns `utm_id`, display `utm_campaign`, and query parameters. Implementation status starts at `GENERATED`. No provider activation writes.

## F. External bindings

Uniqueness key: `(provider_id, external_account_id, external_campaign_id)`.  
`provider_id` must match the canonical provider registry exactly. Same external ID on `google_ads` vs `meta_ads` is not a collision. External name changes do not change `campaign_id`.

## G. Resolution

1. Exact active PreM3 `utm_id`  
2. Exact confirmed external binding  
3. Exact approved custom identifier  
4. User-confirmed manual mapping  
5. `UNRESOLVED`

Conflicting exact campaign IDs → `REVIEW_REQUIRED`. No `FUZZY_NAME_MATCH` authority.

## H. GA4 topology

Kinds: `SINGLE_MASTER_PROPERTY`, `PROPERTY_PER_MARKET`, `MULTI_PROPERTY_SHARED_MARKETS`, `MASTER_PLUS_REGIONAL`, `CUSTOM`.  
`bq_location` is required. Cross-location is not `direct_union_ready`.  
`MASTER_PLUS_REGIONAL` without overlap policy → `OVERLAP_POLICY_REQUIRED`.  
`DEDUPE_REQUIRED` means not analytically ready; no dedupe implementation.

## I. Market resolution

Policy allow-list of methods. Evidence carries `method` as provenance. Geo mapping is not implicit. Unresolved stays unresolved.

## J. Persistence / privacy

In-memory IG-00. Reserved path: `tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/...`.

Prohibited: email, phone, `user_pseudo_id`, `user_id`, CRM person ID, device ID, IP, cookie ID, budget/spend fields, event-scale GA4 rows.

## K. API / contracts

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `b0a52d064e1437ae4ef3dc8f6072c5ce7b24639e5aef3562de7792c965ea6959`.

Routes:

- `GET /v1/projects/{project_id}/identity-graph`
- `GET|POST /v1/projects/{project_id}/identity-graph/campaigns`
- `GET /v1/projects/{project_id}/identity-graph/sources`
- `GET /v1/projects/{project_id}/identity-graph/markets`
- `GET /v1/projects/{project_id}/identity-graph/mappings`

Tenant is never a client input. No fake data endpoints.

## L. Tests

```text
uv run --extra dev pytest tests/unit/identity_graph -q
```

**40 passed** (all spec-named tests in `tests/unit/identity_graph/`).

## M. Regressions

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py -q
# 91 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py tests/unit/identity_graph
# All checks passed
```

M5-02A DP6/Cloud E2E was not run and was not modified. Planning was not touched.

## N. IG-01 readiness

Frozen for discovery to implement: `GA4PropertySourceBinding`, `GA4SourceTopology`, `GA4TopologyDiscoveryResult`, overlap/location rules. Data Foundation should discover/prove datasets; Identity Graph stores the governed topology.

## O. IG-02 readiness

Frozen for Campaign Ledger: `CanonicalCampaign`, default `utm_id` binding, external bindings, Firestore path, `CampaignIdentityService.create_campaign`. Real persistence/UI is IG-02.

## P. M5-03 handoff

`MTAIdentityTouchpointRefs`: `campaign_id?`, `parent_campaign_id?`, `market_id`, `campaign_identity_source`, `market_resolution_method`, `ga4_source_binding_id`. `mta_touchpoints` SQL was not changed.

## Q. Blockers

**BUSINESS_IQ_MARKET_IDENTITY_REQUEST:** BIQ `Market.market_id` is still client-supplied on the profile (no `new_market_id()`, no global index). IG-00 reuses those strings and fails closed when a profile is missing or the ID is unknown. A later BIQ mission should mint durable server-owned market IDs without mutating historical snapshots.

No `PROVIDER_REGISTRY_INTEGRATION_REQUEST` — exact `provider_id` lookup works.

No other blockers. Live GA4 discovery, ads writes, MTA SQL, frontend UI, and person identity remain explicitly out of scope.
