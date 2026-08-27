# Campaign identity and hierarchy

Canonical campaign identity is a PreM3-generated `cmp_<opaque>` ID. It is URL-safe, never reused, never derived from name, provider ID, market, or channel, and is project-scoped.

## Identity rules

- Server-generated only. Clients cannot supply `campaign_id` on create.
- Stable across rename, status change, parent change, and archive.
- Safe to use as `utm_id`.
- Names, `campaign_name_raw`, `utm_campaign`, and external names are display/source context, never join keys.

## Hierarchy

`parent_campaign_id` is optional.

Guards:

- Same project
- No self-parent
- No cycles

Read models:

- Children: campaigns whose `parent_campaign_id` equals this campaign
- Lineage: immediate parent, ancestor chain (nearest first, cycle-safe), and child IDs

Changing parent does not change `campaign_id`. Hierarchy is execution structure for later Planning; IG-02 does not aggregate causal return by parent/child.

## APIs

- `GET|POST /v1/projects/{project_id}/identity-graph/campaigns`
- `GET|PATCH /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/children`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/lineage`

Cross-project access is 404. Tenant is never accepted from the client.
