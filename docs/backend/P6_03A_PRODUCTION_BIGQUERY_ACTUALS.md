# P6-03A production BigQuery actuals

P6-03A supplies production rows to the existing P6-03 actual-spend contract. It does not invent a new financial model, portfolio state, or grain.

## Path

```text
Data Foundation SourceBinding
        ↓
server-authorized BigQuery query (actual_spend_bq_query/v1)
        ↓
normalized RawActualSpendRow
        ↓
existing rollup_raw_actuals → ActualSpendAllocation
        ↓
existing ActualSpendQuery / portfolio assembler
```

`BigQueryActualSpendAdapter` implements `ActualSpendRowSource`. `DataFoundationActualSpendAdapter` remains the `ActualSpendQuery` implementation. `TestOnlyActualSpendAdapter` stays TEST_ONLY and is never installed in production.

## Query authority

The client may not supply SQL, table path, project override, dataset override, or column expressions. The server compiles a bounded query from the bound `ResourceIdentity` and `SourceContract`:

- identifiers validated
- required columns only
- `@start_date` / `@end_date` / `@timezone` parameters
- `GROUP BY date, market_id, channel_id, currency` with `SUM(spend)`
- fiscal-quarter mapping remains in `rollup_raw_actuals` (`fiscal_year_x_quarter/v1`)

Workspace `BigQueryWorkspaceBinding` authorizes project and dataset. Table location must match the workspace binding location. Cross-location queries fail closed (`BQ_LOCATION_MISMATCH`). No region copy.

## Frozen P6-03 semantics

- `PortfolioCoverageState`: `NEITHER` / `PLAN_ONLY` / `PLAN_AND_ACTUALS` / `ACTUALS_ONLY`
- grain: Fiscal Year × Quarter × `market_id` × `channel_id`
- `MISSING != ZERO` (no Cartesian zero grid)
- Decimal `ROUND_HALF_EVEN` to 2 places
- no FX; currency mismatch is `CURRENCY_REVIEW_REQUIRED`
- stale sources still assemble rows but are not labeled current (`STALE` / `STALE_ACTUALS_SOURCE`)

Canonical identity:

- `market_id` → Identity Graph
- `channel_id` → Channel Registry

Unknown identities fail closed as `ACTUALS_MARKET_MAPPING_REQUIRED` / `ACTUALS_CHANNEL_MAPPING_REQUIRED`.

## Receipt and privacy

`ActualSpendQueryReceipt` is metadata only: receipt id, source fingerprint, period, template version, mapping fingerprint, row count, status, issues. Amounts are never persisted to Firestore, logs, MEL, or the receipt.

`GET /v1/projects/{project_id}/investment-portfolio` consumes the production adapter automatically when a governed binding exists. Response remains `Cache-Control: private, no-store`.

See [ACTUAL_SPEND_QUERY_AUTHORITY.md](ACTUAL_SPEND_QUERY_AUTHORITY.md).
