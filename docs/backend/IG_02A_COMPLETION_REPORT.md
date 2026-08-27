# IG-02A completion report

**Date:** 2026-08-26  
**Status:** Audience + Persona Ledger implemented on an isolated worktree. Not pushed. Not committed unless requested.

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-02a` |
| Branch | `feature/prem3-ig-02a-audience-persona-ledger` |
| IG-02 base HEAD | `be0c6462d40569efe48d1df09ce3522458bef8c3` |
| Push | not requested |

M5-02A, MTA runtime, MMM, P6, and the M3 worktree were not modified. `uv.lock` left untracked.

## B. Reuse

Reused without forking:

- `_opaque()` ID minting (`per_` / `aud_`)
- Campaign hierarchy guards for optional `parent_audience_id`
- `CampaignOwnerType`
- Canonical market + privacy walker
- `IdentityGraphStore` / `FirestoreIdentityGraphStore` path layout
- Campaign `persona_ids[]` / `audience_ids[]` fields (now resolvable)

## C. Contract extensions

`CanonicalPersona`: archetype metadata, optional markets, optional BIQ snapshot/segment refs, owner metadata, `persona_id_authority=PREM3_GENERATED`.

`CanonicalAudience`: type/source, optional `source_ref`, optional markets/personas/parent, summaries, effective dates, refresh cadence, `audience_id_authority=PREM3_GENERATED`.

Receipts: `PersonaLedgerValidationReceipt` / `AudienceLedgerValidationReceipt`. Overview: `persona_ledger_state` / `audience_ledger_state` plus counts.

`AudienceExternalBinding` reserved as an IG-03 seam (no CRUD). `AUDIENCE_DERIVED_FROM` reserved in the edge enum only.

## D. IDs / enums

`new_persona_id()` → `per_<opaque>`. `new_audience_id()` → `aud_<opaque>`. Never reused. Name edits change fingerprint, not ID.

`AudienceType`, `AudienceSourceKind`, `AudienceRefreshCadence`, `PersonaStatus`, `AudienceStatus`. `IdentitySourceAuthority.BUSINESS_IQ_DEFINED` added for source metadata.

## E. Markets

Empty `market_ids[]` is unspecified/global. Non-empty IDs must be known canonical `mkt_` markets. Display labels never join.

## F. BIQ

**BUSINESS_IQ_PERSONA_INTEGRATION_REQUEST:** Identity Graph owns V1 Persona/Audience. Optional `business_profile_snapshot_id` fail-closed exists. Historical snapshots are not rewritten. Persona is not required on Audience create. Research-authoring fields are omitted.

## G. Campaign refs

Empty `persona_ids[]` / `audience_ids[]` remain valid. Known same-project IDs are accepted. Unknown/cross-project → `UNKNOWN_PERSONA` / `UNKNOWN_AUDIENCE`. Campaigns without those refs remain valid.

## H. Hierarchy

Optional `parent_audience_id`: same project, no self-parent, no cycles. Child does not imply membership subset. `AUDIENCE_DERIVED_FROM` is not implemented.

## I. Lifecycle / archived targeting

Statuses: `DRAFT` · `ACTIVE` · `INACTIVE` · `ARCHIVED`. Default create = `DRAFT`. Prefer archive. Hard delete only never-referenced drafts.

`ARCHIVED_TARGET` blocks new/active campaigns from targeting archived personas/audiences. Historical `ARCHIVED` campaigns may keep those refs.

## J. Persistence / privacy

Path: `tenants/{tid}/workspaces/{wid}/identity_graph/current/{personas,audiences,persona_receipts,audience_receipts}/...`

Global index: `persona__{id}`, `audience__{id}`. Metadata only.

Walker aliases added: `member_list`, `hashed_member_list`, `membership_snapshot`, `mobile_advertising_id`, `idfa`, `gaid`, `estimated_size`, `match_rate`. Rejection messages name fields, never values.

## K. APIs / contracts

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `f04b1804f0211b8d69fc2a8cb8fb8124807f6eb5f914eca394474bb3a908c457`.

Routes (tenant never client-supplied):

- `GET|POST /v1/projects/{project_id}/identity-graph/personas`
- `GET|PATCH /v1/projects/{project_id}/identity-graph/personas/{persona_id}`
- `GET /v1/projects/{project_id}/identity-graph/personas/{persona_id}/audiences`
- `GET /v1/projects/{project_id}/identity-graph/personas/{persona_id}/campaigns`
- `GET|POST /v1/projects/{project_id}/identity-graph/audiences`
- `GET|PATCH /v1/projects/{project_id}/identity-graph/audiences/{audience_id}`
- `GET /v1/projects/{project_id}/identity-graph/audiences/{audience_id}/personas|campaigns|children|lineage`

No provider/membership routes. Cross-project access is 404.

## L. Tests

```text
uv run --extra dev pytest tests/unit/identity_graph -q
```

**164 passed** (includes spec-named ID, markets, relationships, campaign refs, hierarchy, type/source/dates, privacy, no budget/performance/member-count, provider equivalence, API/OpenAPI, Firestore, plus existing IG-00/01/02 tests).

## M. Regressions

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py tests/unit/test_firestore_client.py tests/unit/data_foundation/test_durable_stores.py -q
# 230 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py app/service/product_stores.py app/control_plane/layout.py tests/unit/identity_graph
# All checks passed
```

## N. Docs / ADRs

Created: `PERSONA_LEDGER.md`, `AUDIENCE_LEDGER.md`, `AUDIENCE_PERSONA_RELATIONSHIPS.md`, `AUDIENCE_PRIVACY_BOUNDARY.md`, `AUDIENCE_PROVIDER_EQUIVALENCE.md`, this report.

Updated: `MARKETING_IDENTITY_GRAPH_ARCHITECTURE.md`, `CAMPAIGN_LEDGER.md`, `CAMPAIGN_IDENTITY_AND_TRACKING_CONTRACT.md`, `IDENTITY_GRAPH_PRIVACY_BOUNDARY.md`.

Recorded IG-ADR-035…046.

## O. IG-03 handoff

`AudienceExternalBinding` + `CampaignExternalBinding` without changing `CanonicalAudience` / `campaign_id`. Provider ID never replaces `audience_id`. Same canonical audience on multiple providers ≠ identical membership.

## P. IG-04 handoff

`source_kind` / `source_ref` are definition pointers, not unified-plane membership.

## Q. Exposure handoff

Consume `audience_id × campaign_id × market_id × channel_id` as intended scope vs observed evidence. Do not store size/match rate here.

## R. MTA / Planning handoff

Do not add audience/persona as DP6 states. Do not expand P6 grain beyond `market_id × channel_id × period`.

## S. Blockers

`BUSINESS_IQ_PERSONA_INTEGRATION_REQUEST` is recorded, not blocking: omitted snapshot/segment is valid; supplied snapshot_id fail-closed exists.

Not committed. Not pushed.
