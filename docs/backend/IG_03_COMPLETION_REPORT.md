# IG-03 completion report

**Date:** 2026-08-27  
**Status:** External bindings, observation, verification, and coverage implemented on an isolated worktree. Not pushed. Not committed unless requested.

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-03` |
| Branch | `feature/prem3-ig-03-external-bindings` |
| Base HEAD | `e0fc82d1068fb31593b8aa2acee3415c0a365b7f` |
| Final HEAD | uncommitted on `e0fc82d` (no commit requested) |
| Push | not requested |

M5-02A, MTA runtime, MMM, P6, and the M3 worktree were not modified. `uv.lock` left untracked.

## B. CampaignExternalBinding

Persisted with `tenant_id`, `project_id`, `authority`, `source_ref`, `updated_at`, optional `external_parent_id` / `external_campaign_status`. Namespace remains `(provider_id, external_account_id or "", external_campaign_id)`. Field name `external_account_id` kept. Effective dates remain `effective_start` / `effective_end`. Live `CONFIRMED`/`ACTIVE` against an archived campaign fails `ARCHIVED_TARGET`. Conflicts fail closed at resolution (`REVIEW_REQUIRED`, `CONFLICTING_EXACT_BINDINGS` / `BINDING_CONFLICT`). Historical non-overlapping dated bindings stay queryable.

## C. AudienceExternalBinding

CRUD persisted. Same canonical `audience_id` may map to many providers. No `membership_identical`. No member lists. Archived audience + new live binding → `ARCHIVED_TARGET`. Edge `AUDIENCE_BOUND_TO_EXTERNAL`.

## D. CampaignTrackingBinding

Default create still `PREM3_UTM_ID` / `utm_id=<campaign_id>`. Kinds: `PREM3_UTM_ID`, `PLATFORM_CAMPAIGN_ID`, `CUSTOM_EVENT_PARAM`, `CUSTOM_QUERY_PARAM`, `MANUAL_MAPPING`. Prefer `CampaignExternalBinding` over redundant provider-ID tracking rows.

## E. Custom identifier rules

`CustomCampaignIdentifierRule`: `canonical_role=CAMPAIGN_ID`; scopes `QUERY_PARAM` · `GA4_EVENT_PARAM` · `SESSION_FIELD` · `CUSTOM_SOURCE_FIELD`. Authoritative use requires `APPROVED`. `bind_custom_identifier` still rejects non-`APPROVED` with `CUSTOM_IDENTIFIER_NOT_APPROVED`.

## F. TrackingObservation

Metadata only: `source_ref` (required), `source_kind`, identifier snapshot, optional provider tuple, `candidate_campaign_id`, `evidence_fingerprint`. No event rows. No `put_events`. Walker rejects `ga4_events` / `event_rows`.

## G. Campaign resolution

`CampaignIdentityResolver` wraps `resolve_campaign_identity`. Precedence: exact active `utm_id` → confirmed/active external → approved custom rule + mapping → user-confirmed manual → unresolved. Dates respected. Fuzzy/`utm_campaign` never hit. Same campaign via several exact methods → `RESOLVED` with all `matched_binding_ids`. Distinct canonical IDs → `REVIEW_REQUIRED`.

## H. Verification

`TrackingVerificationReceipt`: `VERIFIED` · `OBSERVED_UNVERIFIED` · `NOT_OBSERVED` · `REVIEW_REQUIRED`. `VERIFIED` requires observation + unique match to the expected campaign. Instruction `OBSERVED`/`VERIFIED` is readable only with that evidence.

## I. Coverage

`IdentityCoverageReadModel` stores counts (`observed_identifier_count`, `resolved_identifier_count`, `unresolved_identifier_count`, `review_required_count`, `campaigns_total`, declared/observed/verified campaign counts). Explicit denominators; no tracking score. `AudienceBindingCoverage`: counts + `providers[]`.

## J. Provider discovery

`ProviderDiscovery` protocol + `UnconfiguredProviderDiscovery`. `discover_campaigns` / `discover_audiences` return `DISCOVERY_NOT_CONFIGURED`. No live Ads/Meta client.

## K. Provider writes

None. No create/edit/activate/upload/pause/budget routes.

## L. Persistence

Path: `tenants/{tid}/workspaces/{wid}/identity_graph/current/{campaign_external,audience_external,custom_identifier_rules,tracking_observations,identity_resolutions,tracking_verification_receipts,identity_coverage}/...`

Indexes: `campaign_binding__{id}`, `audience_binding__{id}`. Firestore metadata only.

## M. Privacy

Walker still rejects person, budget, event, and performance keys. Added `tracking_score` and `membership_identical`. Synthetic non-person IDs only.

## N. APIs

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `73585eac668d469a15043685fffef0182a73c8780916a7364e10b89fc34a0121`.

Added (tenant never client-supplied; cross-project 404):

- `GET|POST .../campaigns/{campaign_id}/bindings`
- `GET|PATCH .../campaign-bindings/{binding_id}`
- `GET|POST .../audiences/{audience_id}/bindings`
- `GET|PATCH .../audience-bindings/{binding_id}`
- `POST .../campaigns/{campaign_id}/tracking/bindings`
- `POST .../tracking/observe|resolve|verify`
- `GET .../tracking/coverage`
- `GET .../campaigns/{campaign_id}/verification`
- `GET .../audiences/{audience_id}/binding-coverage`

Kept `GET .../mappings` and `GET .../campaigns/{id}/tracking`.

## O. Tests

```text
uv run --extra dev pytest tests/unit/identity_graph -q
```

**220 passed** (IG-00/01/02/02A plus spec-named §§33–43: bindings, audience multi-provider, tracking/custom rules, observation, resolution, verification, coverage, privacy, declared-truth immutability, tenant/project authority, API, Firestore).

## P. Regressions

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py tests/unit/test_firestore_client.py tests/unit/data_foundation/test_durable_stores.py -q
# 286 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py app/service/product_stores.py app/control_plane/layout.py tests/unit/identity_graph
# All checks passed
```

## Q. IG-04 handoff

`CampaignIdentityHandoff`: `campaign_id`, `parent_campaign_id?`, `campaign_identity_source`, binding/tracking ids, `resolution_status`, `resolution_fingerprint`, optional provider/utm/custom provenance, `source_ref`, `audience_id?` only when a binding proves it. Do not materialize unified GA4 sessions here.

## R. M5-03 handoff

Consume `campaign_id` / `parent_campaign_id` / provenance. Do not change DP6.

## S. Exposure handoff

`audience_id` × provider binding as intended vs observed. No size, match rate, or IVT here.

## T. Blockers

None for IG-03 V1. Provider discovery is intentionally unconfigured. Planning grain is unchanged.

Not committed. Not pushed.
