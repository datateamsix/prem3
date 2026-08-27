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
| `persona_ids[]` / `audience_ids[]` | Reserved empty scope refs; not members; no CRUD in IG-00 |

Status changes do not change identity. Hierarchy is execution detail for later Planning; IG-00 does not aggregate causal return by parent/child.

Persona = strategic/durable business archetype. Audience = operational/targetable segment definition. Campaign = governed marketing initiative/execution identity. None of these persist people.

## Campaign Ledger V1 (IG-02)

See architecture doc. IG-02 should treat `name`, `status`, `market_ids[]`, and `channel_ids[]` as required. Planned dates are strongly recommended. Budget, spend, impressions, conversions, attribution, ROAS, and person-level identity stay out.

## Default tracking

`CampaignIdentityService.create_campaign` always mints:

- `parameter_name = utm_id`
- `parameter_value = <campaign_id>`
- `tracking_kind = PREM3_UTM_ID`

`CampaignTrackingInstructions` returns `utm_id`, optional display `utm_campaign`, and query parameters. `utm_campaign` is not canonical identity.

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
- `GET /v1/projects/{project_id}/identity-graph/mappings`

Tenant is never accepted from the client. `campaign_id` is never client-supplied on create.
