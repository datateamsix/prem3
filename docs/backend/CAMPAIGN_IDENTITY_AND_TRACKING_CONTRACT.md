# Campaign identity and tracking contract

Canonical campaign identity lives in Foundation (`app/identity_graph`), not MTA, Business IQ, or Planning.

## CanonicalCampaign

Metadata only. No budget, attribution, or platform metrics.

| Field | Rule |
|---|---|
| `campaign_id` | Server-generated `cmp_<opaque>`; URL-safe; never reused |
| `tenant_id` / `project_id` | Graph ownership |
| `parent_campaign_id` | Optional; same project; no self-parent; no cycles |
| `name` / `campaign_name_raw` | Display / source context, not join keys |
| `status` | `PLANNED` · `ACTIVE` · `PAUSED` · `COMPLETE` · `ARCHIVED` |
| `market_ids[]` | Canonical Identity Graph `market_id` (`mkt_<opaque>`); unknown IDs fail closed |
| `channel_ids[]` | Channel Registry IDs; unknown IDs fail closed |
| `persona_ids[]` / `audience_ids[]` | Empty is valid. Any submitted ID is unknown until IG-02A and is rejected. Not members. |
| `planned_start_date` / `planned_end_date` | Optional; end ≥ start when both set; evergreen = both absent |

Status changes do not change identity. Hierarchy is execution detail for later Planning; IG-02 does not aggregate causal return by parent/child.

Persona = strategic/durable business archetype. Audience = operational/targetable segment definition. Campaign = governed marketing initiative/execution identity. None of these persist people.

## Campaign Ledger V1 (IG-02)

See [CAMPAIGN_LEDGER.md](CAMPAIGN_LEDGER.md). `name`, `status`, `market_ids[]`, and `channel_ids[]` are required on create. Planned dates are optional. Owner and objective are optional metadata. Budget, spend, impressions, conversions, attribution, ROAS, and person-level identity stay out.

No `campaign_type` in V1.

## Default tracking

`CampaignIdentityService.create_campaign` always mints:

- `parameter_name = utm_id`
- `parameter_value = <campaign_id>`
- `tracking_kind = PREM3_UTM_ID`

`CampaignTrackingInstructions` returns `utm_id`, `parameter_name` / `parameter_value`, `recommended_utm_campaign`, query parameters, `implementation_status=NOT_IMPLEMENTED`, and a fingerprint. `utm_campaign` is not canonical identity. Rename does not change `utm_id`.

Customer-facing statuses: `NOT_IMPLEMENTED` · `DECLARED_IMPLEMENTED` · `OBSERVED` · `VERIFIED` · `REVIEW_REQUIRED`. `OBSERVED` / `VERIFIED` are IG-03+ with evidence. Internal provenance may still be `GENERATED`.

Tracking kinds: `PREM3_UTM_ID` · `PLATFORM_CAMPAIGN_ID` · `CUSTOM_EVENT_PARAM` · `MANUAL_MAPPING`.

Custom identifiers require an explicit `APPROVED` rule. No automatic provider writes.

## External bindings

`CampaignExternalBinding` identity key:

`(provider_id, external_account_id, external_campaign_id)`

Provider IDs resolve to the canonical registry (`google_ads`, `meta_ads`, …). The same external campaign ID on two providers is not a collision. Changing `external_campaign_name` does not change `campaign_id`.

## Resolution precedence

1. Exact active PreM3 `utm_id` tracking binding
2. Exact confirmed external campaign binding
3. Exact approved custom identifier binding
4. Explicit user-confirmed manual mapping
5. `UNRESOLVED`

If two exact bindings resolve to different campaigns: `REVIEW_REQUIRED`. Do not silently pick one.

`CampaignIdentitySource` has **no** `FUZZY_NAME_MATCH`. Names never deterministically resolve.

## API

- `POST /v1/projects/{project_id}/identity-graph/campaigns`
- `GET /v1/projects/{project_id}/identity-graph/campaigns`
- `GET|PATCH /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/children`
- `GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/lineage`
- `GET /v1/projects/{project_id}/identity-graph/mappings`

Tenant is never accepted from the client. `campaign_id` is never client-supplied on create.
