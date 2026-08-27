# Market resolution policy

Market assignment is a governed, provenance-bearing decision. `geo.country` is **not** a universal default.

## Policy

`MarketResolutionPolicy.allowed_methods` is an ordered allow-list. Resolution outside the allow-list stays `UNRESOLVED`.

Methods:

- `PROPERTY_BOUND`
- `STREAM_BOUND`
- `CUSTOM_DIMENSION`
- `HOSTNAME_MAPPING`
- `GEO_MAPPING` — only when explicitly allowed
- `USER_CONFIRMED_RULE`
- `UNRESOLVED`

A missing policy does not imply geo mapping. That path records `GEO_MAPPING_NOT_IMPLICIT_DEFAULT`.

## Evidence

`MarketResolutionEvidence` records:

- `market_id` (BIQ market identity, or null)
- `method` (provenance — not optional)
- `source_ref` / `rule_ref`
- `authority`: `RESOLVED` · `REVIEW_REQUIRED` · `UNRESOLVED`
- `issues[]`

Do not use generic ML confidence scores for deterministic resolution.

## Campaign scope vs observed execution

Campaign `market_ids[]` are semantic declarations. They do not prove observed GA4 geo/source evidence and do not override topology policy.

## BUSINESS_IQ_MARKET_IDENTITY_REQUEST

BIQ `Market.market_id` is currently client-supplied on the Business Profile and is not a globally indexed server-owned ID. IG-00 **reuses** those strings and fails closed when they are absent or unknown. A later BIQ mission should mint durable `mkt_…` IDs and an index without mutating historical snapshots.
