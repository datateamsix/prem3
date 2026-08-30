# Portfolio-to-model mapping

P6-04 maps Marketing Investment Portfolio cells onto accepted MMM variables. Mapping lives in `app/investment_optimization/mapping.py`. Spreadsheet header mapping in `app/investment_planning/mapping.py` is unrelated.

## Grain

Portfolio cell: `fiscal year × quarter × market_id × channel_id`.

Model side: `ModelConsumptionContract` variables with optional **explicit** `canonical_channel_id` / `canonical_market_id`. Names and Meridian `media_channels` strings are not identity.

## Authority (only)

- `MODEL_CONTRACT_EXACT`
- `CANONICAL_CHANNEL_BINDING`
- `CANONICAL_MARKET_BINDING`
- `USER_CONFIRMED`
- `APPROVED_CUSTOM_MAPPING`

Rejected: `FUZZY_NAME`, string similarity, LLM inference.

Overrides may carry canonical IDs and cardinality policy. They must not carry amounts.

## Cardinality

| Kind | Rule |
|---|---|
| 1:1 | `AUTO_SAFE` when canonical IDs match |
| many-to-one | requires explicit `AGGREGATE_FOR_MODEL`; combined bucket only |
| one-to-many | requires `APPROVED_ALLOCATION_SPLIT` (bps sum 10000); else `ONE_TO_MANY_MAPPING_REQUIRES_SPLIT` / `REVIEW_REQUIRED` |
| many-to-many | `MANY_TO_MANY_MAPPING_UNSUPPORTED` / `NOT_SUPPORTED_V1` |

## Market compatibility

- `DIRECTLY_MODELED` — explicit `canonical_market_id` match
- `AGGREGATED_IN_MODEL` — national model covering portfolio markets without claiming market-level precision
- `NOT_MODELED` — market filtered / unmatched
- `REVIEW_REQUIRED` — geo without an explicit market bind, or national when market-level optimization is requested

Display labels are not identity. Cross-project and cross-tenant mapping fail closed.

## Persistence

`PortfolioModelMapping` is `CONTROL_PLANE_METADATA`. Firestore collection: `portfolio_model_mappings`. No amount fields.
