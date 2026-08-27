# GA4 source topology contract

Identity Graph stores **governed source identity**, not GA4 event data. Data Foundation discovers datasets/properties/locations (IG-01). Identity Graph stores and serves the topology (`GA4TopologyDiscoveryResult` is the future ingest seam).

## GA4PropertySourceBinding

Required identity fields: `ga4_property_id`, `bq_project_id`, `bq_dataset_id`, **`bq_location`**.

`bq_location` is mandatory whenever known so later missions can distinguish:

- same-location union eligible
- cross-location review required

IG-00 does not copy data or issue cross-region queries.

Also records: `stream_ids[]`, `declared_market_ids[]`, coverage window, `source_authority`, `overlap_policy`.

## Topology kinds

Do not infer topology from dataset names.

- `SINGLE_MASTER_PROPERTY`
- `PROPERTY_PER_MARKET`
- `MULTI_PROPERTY_SHARED_MARKETS`
- `MASTER_PLUS_REGIONAL`
- `CUSTOM`

`MASTER_PLUS_REGIONAL` without an explicit overlap policy is `REVIEW_REQUIRED` and not `direct_union_ready`.

## Overlap policy

- `DISJOINT`
- `MASTER_AUTHORITATIVE`
- `REGIONAL_AUTHORITATIVE`
- `PARTITIONED_BY_MARKET`
- `DEDUPE_REQUIRED` — configuration is not analytically ready; IG-00 does not implement dedupe
- `REVIEW_REQUIRED`

Silent UNION of master + regional properties is forbidden.

Cross-location topologies set `direct_union_ready = false` and issue `CROSS_LOCATION_REVIEW_REQUIRED`.

## Source authority

`USER_DECLARED` · `PREM3_GENERATED` · `PROVIDER_DISCOVERED` · `DATA_FOUNDATION_DISCOVERED` · `USER_CONFIRMED` · `SYSTEM_VERIFIED`

`PROVIDER_DISCOVERED` cannot become `SYSTEM_VERIFIED` without deterministic confirmation.

## MTA

Leave `mta_touchpoints` and MTA routers unchanged. M5-03 consumes `MTAIdentityTouchpointRefs`.
