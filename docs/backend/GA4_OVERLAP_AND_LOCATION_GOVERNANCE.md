# GA4 overlap and location governance

**Mission:** IG-04  
**Enums:** IG-01 `GA4TopologyKind`, `BqLocationClass`, `SourceOverlapPolicy` — no second taxonomy.

## Location

Same-location only. `CROSS_LOCATION` / `UNKNOWN_LOCATION` → `CROSS_LOCATION_REVIEW_REQUIRED` / `BQ_LOCATION_INCOMPATIBLE`. There is no governed copy or replication in V1. Do not fabricate a unified table.

## Overlap

Never silent UNION of master + regional.

| Policy | Compile behavior |
|---|---|
| `DISJOINT` | Deterministic union of selected sources |
| `MASTER_AUTHORITATIVE` | Keep master; exclude regional rows sharing the property-scoped session key |
| `REGIONAL_AUTHORITATIVE` | Keep regional; exclude overlapping master rows |
| `PARTITIONED_BY_MARKET` | Keep a source row only when `market_id` is in that source's declared markets |
| `DEDUPE_REQUIRED` | Blocked (`DEDUPE_POLICY_REQUIRED` / `DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY`). No cross-property person stitching. |
| `REVIEW_REQUIRED` | Blocked |
| missing on `MASTER_PLUS_REGIONAL` | `OVERLAP_POLICY_REQUIRED` |

SQL templates live under `sql/identity_graph/overlap/`. Do not mutate `sql/mta/`.

## Settlement

Reuse `GA4SettlementPolicy`. Final compile requires `DAILY_SETTLED` unless the request is explicitly `PREVIEW_INTRADAY`. Do not mix `events_intraday_*` into settled artifacts (`INTRADAY_MIXED_INTO_SETTLED`).
