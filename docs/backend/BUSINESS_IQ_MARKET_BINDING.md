# Business IQ market binding

**Mission:** IG-01 Phase A  
**Contract:** `BusinessMarketBinding`

Historical Business IQ snapshots are immutable. IG-01 binds existing profile markets additively. It does not rewrite `BusinessProfile` / `BusinessProfileSnapshot` strings or IDs.

## Binding

| Field | Rule |
|---|---|
| `binding_id` | Server-generated `igb_<opaque>` |
| `business_profile_snapshot_id` | Snapshot that owned the legacy ref |
| `business_market_ref` | Exact BIQ `Market.market_id` string as stored (may be client-supplied) |
| `market_id` | Canonical Identity Graph ID |
| `mapping_method` | See below |
| `status` | `CONFIRMED` or `REVIEW_REQUIRED` |

Idempotent key: `(tenant_id, project_id, snapshot_id, business_market_ref)`.

The same proven legacy ref always resolves to the same canonical `market_id`. Display-name-only matches never merge. If two legacy markets cannot be proven equivalent, resolution stays `REVIEW_REQUIRED`.

## Mapping methods

- `SERVER_CREATED_FROM_BUSINESS_IQ`
- `USER_CONFIRMED`
- `EXACT_EXISTING_BINDING`
- `MIGRATED_LEGACY_REF`
- `UNRESOLVED`

Fuzzy display-name matching is not deterministic authority.

## Migration

```text
existing BIQ profile market
        ↓
create or resolve CanonicalMarket
        ↓
persist BusinessMarketBinding
```

`CampaignIdentityService.bind_business_iq_markets` performs this for the current profile. Historical `Market.market_id` values remain on the snapshot.

## Blocker

IG-00 recorded `BUSINESS_IQ_MARKET_IDENTITY_REQUEST`. IG-01 **resolves** that blocker by minting server-owned canonical market IDs and additive bindings. The historical IG-00 record is kept; it is not deleted.
