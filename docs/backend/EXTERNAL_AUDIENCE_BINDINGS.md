# External audience bindings

Provider audience IDs are provenance for a canonical `audience_id`. They never replace it.

One canonical Audience may map to many provider implementations. That does **not** mean identical membership. There is no `membership_identical` field and no member list.

## Fields

`binding_id`, `tenant_id`, `project_id`, `audience_id`, `provider_id`, `external_account_id`, `external_audience_id`, optional name and `audience_implementation_type`, effective dates, `mapping_method`, `status`, `authority`, confirmation metadata, `source_ref`, fingerprint, timestamps.

## Lifecycle

New `CONFIRMED` / `ACTIVE` bindings against an `ARCHIVED` audience fail closed (`ARCHIVED_TARGET`). Edges: `AUDIENCE_BOUND_TO_EXTERNAL`.

## Coverage

`AudienceBindingCoverage` is count-based: binding counts, `providers[]`, status, issues. No size, match rate, reach, or eligible users.

## Discovery

`discover_audiences` is interface-only (`DISCOVERY_NOT_CONFIGURED`). Manual bind/confirm is the V1 workflow.
