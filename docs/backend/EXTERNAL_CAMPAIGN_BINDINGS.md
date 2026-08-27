# External campaign bindings

Provider campaign IDs enrich canonical PreM3 `campaign_id`. They never replace it.

`CampaignExternalBinding` is namespaced by `(provider_id, external_account_id or "", external_campaign_id)`. The same platform ID in two accounts or two providers is not a collision.

## Fields

`binding_id`, `tenant_id`, `project_id`, `campaign_id`, `provider_id`, `external_account_id`, `external_campaign_id`, optional name/parent/status, `effective_start` / `effective_end`, `mapping_method`, `status`, `authority`, confirmation metadata, `source_ref`, fingerprint, timestamps.

Keep `external_account_id` (not a second `provider_account_id` field). Keep `effective_start` / `effective_end`.

## Lifecycle

Live authoritative resolution uses `CONFIRMED` / `ACTIVE`. `PENDING`, `INACTIVE`, `REVIEW_REQUIRED`, and `ARCHIVED` are stored but do not resolve observed identity. New `CONFIRMED` / `ACTIVE` bindings against an `ARCHIVED` campaign fail closed (`ARCHIVED_TARGET`). Historical non-overlapping dated bindings remain queryable.

## Conflicts

Two live bindings of the same external tuple to different canonical campaigns fail closed at resolution (`REVIEW_REQUIRED`, `CONFLICTING_EXACT_BINDINGS` / `BINDING_CONFLICT`). The resolver does not silently pick one.

## Persistence

`tenants/{tid}/workspaces/{wid}/identity_graph/current/campaign_external/{binding_id}`

Global index: `campaign_binding__{id}`.

## Out of authority

No Google Ads / Meta / DV360 create, edit, pause, or budget writes.
