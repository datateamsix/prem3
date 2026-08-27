# Portfolio snapshot and transient view

`PortfolioSnapshotRef` is durable metadata.

`PortfolioView`, `PortfolioSummary`, `PortfolioAllocationView`, `QuarterlyPortfolioView`, and `PortfolioComparisonView` are transient Decimal views.

Amount kinds: `PLANNED`, `APPROVED`, `COMMITTED`, `FLEXIBLE`, `ACTUAL`, `FORECAST_AT_COMPLETION`, `REMAINING`, `RECOMMENDED`.

`MISSING` is not `ZERO`.

Baselines:

- `APPROVED_PLAN` — governed Drive Investment Plan
- `ACTUAL_YTD` / `GOVERNED_ACTUALS` — observed spend; never labeled an approved budget
- `FORECAST_AT_COMPLETION`
- `TRANSIENT_SCENARIO`

Planning, actuals, measurement evidence, and optimization share this grain. MTA may attach coverage; it must not replace MMM response curves.

P6-03 adds `actuals_source_id` on `PortfolioSnapshotRef`. Fingerprint includes the actuals source fingerprint and as-of. `ACTUALS_ONLY` uses baseline `ACTUAL_YTD`.
