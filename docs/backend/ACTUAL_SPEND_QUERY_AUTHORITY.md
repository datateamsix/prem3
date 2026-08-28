# Actual-spend query authority

Data Foundation proves where governed actual spend lives. P6-03A retrieves it. Planning interprets it. None of those layers may silently become the other.

## Ownership

Data Foundation owns:

- source existence
- authorization
- source location
- schema / mapping
- freshness
- quality
- canonical asset refs (`SourceBinding`)

Planning owns:

- interpretation of governed spend as portfolio actuals
- fiscal-quarter rollup (`fiscal_year_x_quarter/v1`)
- portfolio coverage state
- observations

P6-03A may not implement a second warehouse-discovery system. It consumes an existing governed `SourceBinding` that already declares `date`, `market_id`, `channel_id`, `spend`, `currency`, and timezone.

## Production query requirements

1. `binding_supports_portfolio_actuals` and `governance_import_ready`
2. `LocationType.BIGQUERY` with project / dataset / table on `ResourceIdentity`
3. Workspace `BigQueryWorkspaceBinding` → `DataFoundationContext.authorize_project`
4. Dataset in `source_dataset_ids` when that allow-list is present
5. Table/dataset location equals workspace binding location
6. Google access token from the bound connection (never from the client body)

Missing or unready binding: `ACTUALS_SOURCE_NOT_CONFIGURED` or `PRODUCTION_ACTUALS_SOURCE_NOT_READY`. Unauthorized project/dataset/token: `BQ_AUTHORIZATION_FAILED`. Missing table: `BQ_SOURCE_NOT_FOUND`. Cross-location: `BQ_LOCATION_MISMATCH`. Execution failure: `BQ_QUERY_FAILED`.

## What the client may not supply

- SQL
- table path
- `project_id` / dataset override
- column expressions

`GET /v1/projects/{project_id}/investment-portfolio` accepts only the existing `fiscal_year` query option.

## TEST_ONLY vs production

- `TestOnlyActualSpendAdapter` — synthetic rows for unit tests. Cannot carry customer-governed authority.
- Production bootstrap always uses `DataFoundationActualSpendAdapter` + `BigQueryActualSpendAdapter`.
- No production fallback to synthetic rows.

## Persistence barrier

Persisted:

- `ActualSpendSourceRef` (ids, BQ refs, fingerprints, as-of, currency, timezone)
- `ActualSpendQueryReceipt` (metadata; row_count; no amounts)

Never persisted:

- `ActualSpendAllocation`
- `PortfolioView`
- spend amounts in logs, traces, MEL, or analytics
