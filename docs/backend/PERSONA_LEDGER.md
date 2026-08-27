# Persona Ledger

`CanonicalPersona` is a durable **business archetype**. It is not a person, CRM contact, or membership list.

Server-generated identity: `per_<opaque>`. Never derived from name, market, or CRM segment. IDs are project-scoped, URL-safe, never reused, and stable across rename, status change, and archive.

## What it stores

- Name, optional description, status (`DRAFT` · `ACTIVE` · `INACTIVE` · `ARCHIVED`)
- Optional canonical `market_ids[]` (empty = unspecified/global scope)
- Optional `lifecycle_stage_refs[]`, `business_segment_ref`, `business_profile_snapshot_id`
- Optional owner metadata (`CampaignOwnerType`: `USER` · `TEAM` · `AGENCY` · `OTHER`)
- Fingerprint, timestamps, `persona_id_authority=PREM3_GENERATED`, `market_scope_authority=USER_DECLARED`

Default create status is `DRAFT`. Prefer archive. Hard delete is only for never-referenced drafts (no campaign or audience refs).

## What it does not store

People, emails, CRM person IDs, research-authoring prose (`needs_summary`, motivations, barriers, value proposition), budget, performance, or audience members.

## Markets

Empty `market_ids[]` is valid and means unspecified/global. Non-empty IDs must be known canonical `mkt_` markets. Display labels never join.

## Business IQ

Identity Graph owns V1 Persona. Business IQ has no implemented persona object.

**BUSINESS_IQ_PERSONA_INTEGRATION_REQUEST:** optional `business_profile_snapshot_id` / `business_segment_ref` are metadata pointers. If `business_profile_snapshot_id` is set, the snapshot must exist. Historical BIQ snapshots are not rewritten. Persona is not required on Audience create.

## Readiness

Each persona has a fingerprinted `PersonaLedgerValidationReceipt`. Project component `persona_ledger_state`: `NOT_CONFIGURED` · `PARTIAL` · `READY` · `REVIEW_REQUIRED`.

This does **not** gate `BUSINESS_CONTEXT_READY`, `DATA_FOUNDATION_READY`, `MODEL_READY`, `MTA_INPUT_READY`, or `INVESTMENT_PLAN_READY`.

## Persistence

`tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/current/personas|persona_receipts/...`

Global index: `persona__{id}`. Metadata only.
