# Portfolio actuals integration

P6-03 consumes governed actual spend as execution evidence. It does not treat actuals as approved-plan authority.

## Source contract

`ActualSpendSourceRef` is Firestore metadata only: source identity, BigQuery refs, coverage window, as-of, currency, timezone, authority, status, and `source_fingerprint`. Raw spend rows are never stored.

`ActualSpendAllocation` is a transient Decimal row at `fiscal_year × quarter × market_id × channel_id`.

## Query port

`ActualSpendQuery` has two implementations:

- `TestOnlyActualSpendAdapter` — `source_kind=SYNTHETIC`, `authority=TEST_ONLY`. Never labeled customer-governed.
- `DataFoundationActualSpendAdapter` — reads an existing Data Foundation `SourceBinding` that already declares `date`, `market_id`, `channel_id`, `spend`, `currency`, and timezone. No second warehouse-discovery system.

`canonical_media` is MMM model-input grain and is not portfolio actual-spend authority.

Production BigQuery row fetch is not implemented:

`P6_03_PRODUCTION_ACTUALS_QUERY_PENDING`

A governed Data Foundation `SourceBinding` without a usable row source is `ACTUALS_SOURCE_UNAVAILABLE`. The assembler must not fabricate `ACTUALS_ONLY` or `PLAN_AND_ACTUALS`.

## Failure semantics

| Condition | Code / observation | Portfolio state |
|---|---|---|
| No governed binding | `ACTUALS_SOURCE_NOT_CONFIGURED` / `MISSING_ACTUALS_SOURCE` | Stay `PLAN_ONLY` if a plan exists; never fabricate `PLAN_AND_ACTUALS` |
| Binding exists, query fails | `ACTUALS_SOURCE_UNAVAILABLE` | Same; actuals are missing, not zero |
| Source stale but rows returned | `STALE_ACTUALS_SOURCE` | Assemble actuals; coverage `REVIEW_REQUIRED` |
| Unknown timezone / unmapped grain | `PERIOD_MAPPING_REQUIRED` | Fail closed |
| Currency mismatch or mixed currencies | `CURRENCY_REVIEW_REQUIRED` | Fail closed; no FX in P6-03 |

Daily/weekly/monthly rows roll into `fiscal_year × quarter` from `InvestmentPlan.fiscal_start_month` (default 1) in the source timezone. A week that spans a quarter boundary fails closed so periods are not double-counted.

Joins use `require_canonical_market_id` and `require_canonical_channel_id` only.
