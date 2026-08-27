# GA4 market resolution

**Mission:** IG-01 Phase B  
**Contracts:** `MarketResolutionPolicy`, `MarketResolutionEvidence`

GA4 `geo.country` is **not** business-market authority unless an explicit `GEO_MAPPING` policy allows it.

## Methods (ordered allow-list)

1. `PROPERTY_BOUND` — exclusive property → canonical market (example: `analytics_us` → one `mkt_…`)
2. `STREAM_BOUND`
3. `CUSTOM_DIMENSION`
4. `HOSTNAME_MAPPING`
5. `GEO_MAPPING` — only when listed on the policy
6. `USER_CONFIRMED_RULE`
7. `UNRESOLVED`

`MarketResolutionEvidence.method` is required provenance.

## Master properties

A master property covering several markets needs an explicit policy (custom dimension, hostname, stream, approved geo mapping, or user-confirmed rule). Without one:

`MARKET_RESOLUTION_REQUIRED`

Market-specific analytical readiness fails closed.

## Overlap (never silent UNION)

- `DISJOINT`
- `MASTER_AUTHORITATIVE`
- `REGIONAL_AUTHORITATIVE`
- `PARTITIONED_BY_MARKET`
- `DEDUPE_REQUIRED` — not analytically ready; IG-01 does not implement dedupe
- `REVIEW_REQUIRED` — not ready

Ungoverned overlap stays `REVIEW_REQUIRED`.

## BigQuery location

Record exact `bq_location` per source. Classify the topology:

- `SAME_LOCATION`
- `CROSS_LOCATION` → `CROSS_LOCATION_REVIEW_REQUIRED`; not `direct_union_ready`
- `UNKNOWN_LOCATION` → not ready for unified compilation

IG-01 does not implement cross-location replication.
