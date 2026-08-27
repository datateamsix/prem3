# Campaign Ledger

The Campaign Ledger is the persistent Foundation store for governed marketing campaign identity. It lives in `app/identity_graph/` and is Project-scoped (`tenant_id`, `project_id` where `project_id` aliases `workspace_id`).

It is not a performance ledger, a budget ledger, or a person-identity graph.

## What it stores

- `CanonicalCampaign` identity metadata
- Default `utm_id=<campaign_id>` tracking binding and copyable instructions
- Hierarchy edges (`CAMPAIGN_CHILD_OF`, market/channel targets)
- `CampaignLedgerValidationReceipt` per campaign

## What it does not store

Budget, planned/actual spend, impressions, conversions, attribution, ROAS, platform metrics, GA4 event rows, audience members, or person identifiers.

## Create

Create requires:

- `name`
- non-empty canonical `market_ids[]` (`mkt_<opaque>`, known in this project)
- non-empty Channel Registry `channel_ids[]`

Default status is `PLANNED`. Server mints `campaign_id` (`cmp_<opaque>`). `utm_id` equals `campaign_id` and is stable for the life of the campaign.

Create returns the campaign plus tracking instructions so the customer can copy parameters immediately. Instruction `implementation_status` is `NOT_IMPLEMENTED`.

## Update

PATCH semantics. `campaign_id` and `utm_id` never change. Name edits change `fingerprint` and `updated_at` and may refresh `recommended_utm_campaign`. Search-by-name is display-only and never identity resolution.

## Lifecycle

`PLANNED → ACTIVE → PAUSED|ACTIVE → COMPLETE → ARCHIVED`

Admin archive is allowed from earlier states. `ARCHIVED` is preferred over delete. Hard delete is only for never-referenced `PLANNED` drafts (no children, no external bindings, no extra tracking).

## Readiness

Each campaign has a fingerprinted `CampaignLedgerValidationReceipt` proving ID shape, project scope, known markets/channels, date order, parent/cycle, status, tracking instruction, and absence of prohibited fields.

Project component `campaign_ledger_state`: `NOT_CONFIGURED` · `PARTIAL` · `READY` · `REVIEW_REQUIRED`.

This component does not gate `BUSINESS_CONTEXT_READY`, `DATA_FOUNDATION_READY`, `MODEL_READY`, `MTA_INPUT_READY`, or `INVESTMENT_PLAN_READY`.

## Audience / Persona intended scope

`persona_ids[]` / `audience_ids[]` are optional resolvable refs to Identity Graph `per_` / `aud_` definition IDs. They describe intended campaign scope, not observed delivery. Empty lists remain valid. Unknown or cross-project IDs fail closed. Archived audiences/personas cannot be attached to a new or active campaign (`ARCHIVED_TARGET`) unless the campaign itself is already `ARCHIVED`.

See [PERSONA_LEDGER.md](PERSONA_LEDGER.md), [AUDIENCE_LEDGER.md](AUDIENCE_LEDGER.md), and [AUDIENCE_PERSONA_RELATIONSHIPS.md](AUDIENCE_PERSONA_RELATIONSHIPS.md).

## BUSINESS_IQ_OBJECTIVE_INTEGRATION_REQUEST

If `objective_ref` is supplied, IG-02 fail-closed matches it to a `MeasurementObjective.objective_id` (`obj_*`) on the current Business IQ profile snapshot.

BIQ objectives are profile-local statements, not a governed ontology. Do not treat them as a shared objective taxonomy. Omitting objective does not block campaign create. A later mission may introduce a governed objective catalog without migrating `campaign_id`.

## Persistence

`tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/current/{campaigns,campaign_tracking,campaign_tracking_instructions,campaign_receipts}/...`

`FirestoreIdentityGraphStore` in cloud; `InMemoryIdentityGraphStore` in CI/local.
