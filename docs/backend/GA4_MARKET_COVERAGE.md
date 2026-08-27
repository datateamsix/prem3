# GA4 market coverage

**Mission:** IG-01 Phase B  
**Contracts:** `GA4MarketCoverage`, `GA4TopologyReadinessReceipt`

Coverage is a deterministic read model. No percentage completeness unless a later mission can prove it.

## GA4MarketCoverage

| Field | Rule |
|---|---|
| `market_id` | Canonical Identity Graph ID |
| `source_binding_ids[]` | Bindings that declared this market |
| `coverage_status` | `COMPLETE` · `PARTIAL` · `MISSING` · `REVIEW_REQUIRED` · `UNKNOWN` |
| `date_start` / `date_end` | Optional coverage window |
| `freshness_state` | Optional |
| `resolution_method` | Optional provenance |
| `issues[]` | Fail-closed notes |

## Topology readiness receipt

Component receipt. Does **not** broaden `DATA_FOUNDATION_READY`.

States:

- `GA4_TOPOLOGY_READY`
- `GA4_TOPOLOGY_REVIEW_REQUIRED`
- `GA4_TOPOLOGY_INCOMPLETE`

READY requires:

- canonical market identities present
- sources discovered or configured
- BQ locations known or explicitly unresolved
- market coverage declared
- market resolution policy valid when required
- overlap policy valid
- no unresolved conflicting source authority

`CANONICAL_MARKETS_REQUIRED` or missing topology → `INCOMPLETE`. Cross-location, overlap review, dedupe-required, or `MARKET_RESOLUTION_REQUIRED` → `REVIEW_REQUIRED`.
