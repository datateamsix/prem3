# GA4 source topology

**Mission:** IG-01 Phase B  
**Contracts:** `GA4SourceTopology`, `GA4PropertySourceBinding`, `GA4TopologyDiscoveryResult`

Identity Graph stores governed source identity. Data Foundation owns BigQuery authorization, discovery, and quality evidence. IG-01 does not create a second OAuth/BigQuery connection system and does not copy event rows. A discovered dataset is not a confirmed business-market mapping (`DATA_FOUNDATION_DISCOVERED` ≠ `SYSTEM_VERIFIED`).

PreM3 requires one governed analytical view of selected markets. IG-01 discovers/configures topology. IG-04 materializes the unified plane as compilation-scoped `ga4_sessions_unified_{compilation_id}` (see [UNIFIED_GA4_ANALYTICAL_PLANE.md](UNIFIED_GA4_ANALYTICAL_PLANE.md)).

## Representable topologies

Do not infer kind from dataset naming.

| Pattern | Kind |
|---|---|
| One master property covering all markets | `SINGLE_MASTER_PROPERTY` |
| One property per market | `PROPERTY_PER_MARKET` |
| Multiple properties in one BQ project | `MULTI_PROPERTY_SHARED_MARKETS` |
| Properties across multiple BQ projects | `CUSTOM` (distinct `bq_project_id`) |
| Master + regional properties | `MASTER_PLUS_REGIONAL` |
| Datasets in different BQ locations | any kind + `CROSS_LOCATION` |

## Discovery metadata (permitted)

BQ project ID, dataset ID, dataset location, GA4 property ID, event-table date range, stream IDs when deterministic, traffic-source field capability, freshness/coverage metadata.

If live tables are not supplied, `POST .../sources/discover` returns `DISCOVERY_NOT_CONFIGURED` — never invented `GA4_TOPOLOGY_READY`.

`declared_market_ids[]` must be canonical `market_id` values.

## Source authority

`USER_DECLARED` · `DATA_FOUNDATION_DISCOVERED` · `PROVIDER_DISCOVERED` · `USER_CONFIRMED` · `SYSTEM_VERIFIED`

`PROVIDER_DISCOVERED` cannot be silently promoted to `SYSTEM_VERIFIED`.

See [GA4_MARKET_RESOLUTION.md](GA4_MARKET_RESOLUTION.md), [GA4_MARKET_COVERAGE.md](GA4_MARKET_COVERAGE.md), and the IG-00 [GA4_SOURCE_TOPOLOGY_CONTRACT.md](GA4_SOURCE_TOPOLOGY_CONTRACT.md).
