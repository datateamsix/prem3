# Audience Ledger

`CanonicalAudience` is an operational **segment definition**. It is not members, size, match rate, or reach. `CUSTOMER_LIST` is a type, not stored members.

Server-generated identity: `aud_<opaque>`. Never derived from name, provider, or CRM segment. IDs are project-scoped, URL-safe, never reused, and stable across rename, status change, parent change, and archive.

## What it stores

- Name, optional description, status (`DRAFT` · `ACTIVE` · `INACTIVE` · `ARCHIVED`)
- Required `audience_type` and `source_kind`
- Optional `source_ref` (metadata pointer only — CRM/BQ/GA4/provider/BIQ ref, never SQL with identifiers)
- Optional canonical `market_ids[]` (empty = unspecified/global)
- Optional `persona_ids[]` (known same-project `per_` IDs; not required on create)
- Optional `parent_audience_id` (same project, no self-parent, no cycles)
- Optional `definition_summary` / `criteria_summary`, effective dates, `refresh_cadence`
- Optional owner metadata
- `audience_id_authority=PREM3_GENERATED`; source metadata `USER_DECLARED` or `BUSINESS_IQ_DEFINED` when `source_kind` is that

Default create status is `DRAFT`. Prefer archive. Hard delete is only for never-referenced drafts (no campaign refs, no children).

## What it does not store

Members, hashed member lists, membership snapshots, advertising IDs, estimated size, match rate, reach, budget, performance, or event rows.

## Hierarchy

Optional `parent_audience_id` uses campaign-style guards. A child does **not** imply a membership subset. `AUDIENCE_DERIVED_FROM` is reserved in the edge enum only; derivation graphs are not implemented.

## Readiness

Each audience has a fingerprinted `AudienceLedgerValidationReceipt`. Project component `audience_ledger_state`: `NOT_CONFIGURED` · `PARTIAL` · `READY` · `REVIEW_REQUIRED`.

This does **not** gate modeling or planning readiness.

## Persistence

`tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/current/audiences|audience_receipts/...`

Global index: `audience__{id}`. Metadata only.
