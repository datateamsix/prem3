# IG-02 completion report

**Date:** 2026-08-26  
**Status:** Campaign Ledger implemented on an isolated worktree. Not pushed. Not committed unless requested.

## A. Git isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-ig-02` |
| Branch | `feature/prem3-ig-02-campaign-ledger` |
| IG-01 base HEAD | `53b606a3b3bc529254816b8376d57c181b44a7ec` |
| Final HEAD | same SHA until commit; working tree dirty with IG-02 files |
| Push | not requested |

M5-02A, MTA runtime, MMM, P6, and the M3 worktree were not modified.

## B. Reuse

Reused without forking:

- `new_campaign_id()` / `cmp_<opaque>`
- Hierarchy guards (`set_parent`, cycle / self-parent / same-project)
- Default `utm_id=<campaign_id>` via `_default_utm_binding`
- Canonical market + Channel Registry fail-closed validation
- Privacy walker
- `CampaignExternalBinding` as a read-only seam (no provider discovery)

## C. Contract extensions

`CanonicalCampaign`: `planned_start_date` / `planned_end_date` (replaced `start_date` / `end_date`), `objective_ref` / `objective_label`, `owner_type` / `owner_ref` / `owner_label`, `campaign_id_authority=PREM3_GENERATED`, `market_scope_authority=USER_DECLARED`. Empty `persona_ids[]` / `audience_ids[]`. Extra-forbid already rejects budget/performance/PII.

`CampaignTrackingInstructions`: `parameter_name`, `parameter_value`, `recommended_utm_campaign`, customer-facing `implementation_status`, `generation_provenance=GENERATED`, `generated_at`, `fingerprint`.

`CampaignLedgerValidationReceipt`: fingerprinted proof of ID shape, project scope, markets/channels, date order, parent/cycle, status, tracking instruction, no prohibited fields.

No `campaign_type`.

## D. Required scope

Create fails closed unless `market_ids[]` and `channel_ids[]` are non-empty and known. Display-string markets are rejected. Custom-region markets are valid when they are canonical `mkt_` IDs.

## E. Flight

`planned_start_date` / `planned_end_date`. End ≥ start when both set. Evergreen = both absent. Date edits change fingerprint. No `actual_*` dates.

## F. Owner / objective

Owner is optional metadata and does not gate actions. Unknown `objective_ref` fails closed against the current BIQ profile. Omitted objective is allowed.

**BUSINESS_IQ_OBJECTIVE_INTEGRATION_REQUEST:** BIQ objectives are profile-local statements, not a governed ontology.

## G. Audience / Persona

Empty lists are valid. Any submitted ID is rejected (`UNKNOWN_AUDIENCE` / `UNKNOWN_PERSONA`). No members stored. Handoff: IG-02A.

## H. Tracking honesty

Create returns generated instructions with `NOT_IMPLEMENTED`. `OBSERVED` / `VERIFIED` are rejected. Intended vs observed QA is IG-03/IG-04.

## I. Lifecycle

Governed transitions: `PLANNED → ACTIVE → PAUSED|ACTIVE → COMPLETE → ARCHIVED` (admin archive allowed). Archived identity persists. Hard delete only for never-referenced `PLANNED` drafts.

## J. Persistence / privacy

`FirestoreIdentityGraphStore` behind `IdentityGraphStore`. Path `tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/...`. Wired in `create_app` the same way BIQ chooses Firestore vs memory.

May store: campaign metadata, tracking bindings/instructions, receipts, existing IG-01 market/source/topology metadata.

Must not store: people, budget, performance, event rows.

## K. APIs / contracts

OpenAPI regenerated: `contracts/openapi.yaml` sha256 `b4e88f243109d16bf1399e9a5a6b70481678800a17f6e1ed0ef74a63df1256e7`.

Routes (tenant never client-supplied):

- `GET|POST /v1/projects/{project_id}/identity-graph/campaigns`
- `GET|PATCH /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/children`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/lineage`

No fake provider/measurement routes. Cross-project access is 404.

## L. Tests

```text
uv run --extra dev pytest tests/unit/identity_graph -q
```

**118 passed** (includes spec-named ID, hierarchy, scope, flight, tracking, owner/objective, audience/persona, lifecycle, privacy, authority, API, and Firestore tests).

## M. Regressions

```text
uv run --extra dev pytest tests/unit/identity_graph tests/unit/test_project_architecture.py tests/unit/business_iq tests/unit/test_registry.py tests/unit/test_prem3_api_openapi.py tests/unit/test_channel_registry.py tests/unit/test_mmm_m5_00_mta.py tests/unit/test_firestore_client.py tests/unit/data_foundation/test_durable_stores.py -q
# 184 passed

uv run --extra dev pytest tests/unit/data_foundation tests/unit/test_mta_m5_01a_governance.py -q
# 99 passed

uv run ruff check app/identity_graph app/service/app.py app/service/routers/identity_graph.py app/service/identity_graph_models.py app/service/product_stores.py app/control_plane/layout.py tests/unit/identity_graph
# All checks passed
```

## N. Docs / ADRs

Created: `CAMPAIGN_LEDGER.md`, `CAMPAIGN_IDENTITY_AND_HIERARCHY.md`, `CAMPAIGN_TRACKING_INSTRUCTIONS.md`, `CAMPAIGN_LEDGER_PRIVACY_BOUNDARY.md`, this report.

Updated: `MARKETING_IDENTITY_GRAPH_ARCHITECTURE.md`, `CAMPAIGN_IDENTITY_AND_TRACKING_CONTRACT.md`.

Recorded IG-ADR-023…034.

## O. IG-02A handoff

Implement CanonicalAudience / CanonicalPersona. Keep `audience_ids[]` / `persona_ids[]` on campaigns. Do not migrate `campaign_id`.

## P. IG-03 handoff

`CampaignExternalBinding` + tracking statuses `OBSERVED` / `VERIFIED` with evidence. No provider writes in IG-02. Provider ID never replaces `campaign_id`.

## Q. IG-04 / M5-03 handoff

Consume `campaign_id`, `parent_campaign_id`, `utm_id` resolution. Do not change MTA SQL/DP6 here.

## R. Blockers

`BUSINESS_IQ_OBJECTIVE_INTEGRATION_REQUEST` is recorded, not blocking: omitted objective is valid; supplied `objective_ref` fail-closed against the current profile.

Not committed. Not pushed.
