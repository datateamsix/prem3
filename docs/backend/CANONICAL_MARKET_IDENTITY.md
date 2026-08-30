# Canonical market identity

**Mission:** IG-01 Phase A  
**Owner:** Marketing Identity Graph (`app/identity_graph`)

Business IQ defines what a market *means*. Identity Graph owns the durable `market_id` used for cross-method joins. Data Foundation proves where evidence for that market lives. Planning, MTA, and MMM consume `market_id`; they do not mint `planning_market_id`, `mta_market_id`, or `ga4_market_id`.

```text
Business IQ semantics
        ↓
CanonicalMarket   (server-owned mkt_<opaque>)
        ↓
GA4 coverage / campaign / audience / planning / measurement
```

## CanonicalMarket

Metadata only. No spend, no marketing metrics, no person identity.

| Field | Rule |
|---|---|
| `market_id` | Server-generated `mkt_<opaque>`; URL-safe; never reused; not derived from display name or ISO country |
| `tenant_id` / `project_id` | Project-scoped ownership |
| `name` | Display; not identity |
| `description` | Optional |
| `market_kind` | `COUNTRY` · `REGION` · `MULTI_COUNTRY_REGION` · `SUBNATIONAL` · `GLOBAL` · `CUSTOM` |
| `status` | `ACTIVE` · `ARCHIVED` · `REVIEW_REQUIRED` |
| `country_codes[]` / `region_codes[]` | Semantic attributes, not identity authority |
| `fingerprint` | Canonical content hash |

Custom business regions (DACH, North America, US East, Enterprise North America, Global) are first-class. Markets are not forced into ISO countries.

`market_id` is stable for the market lifetime. Two markets may share a display name when business semantics differ.

## Cross-method keys (after Phase A)

- `channel_id` = Channel Registry ID
- `market_id` = Identity Graph canonical market ID

`CanonicalCampaign.market_ids[]` and `GA4PropertySourceBinding.declared_market_ids[]` must be canonical `mkt_` IDs. Unknown IDs fail closed.

See [BUSINESS_IQ_MARKET_BINDING.md](BUSINESS_IQ_MARKET_BINDING.md).
