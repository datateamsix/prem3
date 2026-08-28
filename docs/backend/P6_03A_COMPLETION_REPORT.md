# P6-03A completion report

Production BigQuery actual-spend adapter behind the existing P6-03 `ActualSpendQuery` / `DataFoundationActualSpendAdapter` path. No new financial semantics, portfolio states, or grain.

## A. Git isolation

| Item | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-03a` |
| Branch | `feature/prem3-p6-03a-production-bq-actuals` |
| P6-06 base SHA | `e1a9477b9ce57719d56f0d522d3cb85540823362` |
| Final HEAD | Uncommitted P6-03A work on that base (checkpoint not requested) |
| Status | `uv.lock` left untracked |

Team 1 `prem3-p6-07` was not touched. Did not implement in `prem3-ig-04`. No push. P6-06 history was not rewritten.

## B. Binding consumed

Production fetch requires a governed Data Foundation `SourceBinding`:

- `binding_supports_portfolio_actuals` (`date`, `market_id`, `channel_id`, `spend`, `currency`, timezone)
- `governance_import_ready`
- `LocationType.BIGQUERY` with project / dataset / table on `ResourceIdentity`

Workspace `BigQueryWorkspaceBinding` becomes `DataFoundationContext`. Cross-project and dataset allow-list failures are `BQ_AUTHORIZATION_FAILED`. Table location must match the workspace binding location (`BQ_LOCATION_MISMATCH`). OAuth uses `GoogleConnectionService.user_access_token`.

`TestOnlyActualSpendAdapter` stays TEST_ONLY and is never installed in production (`test_test_adapter_never_used_as_prod`).

## C. Query authority

`BigQueryActualSpendAdapter` implements `ActualSpendRowSource`. It does not replace `DataFoundationActualSpendAdapter` and does not invent a second `ActualSpendQuery`.

Template `actual_spend_bq_query/v1`:

- identifiers from the bound resource + contract only
- `@start_date` / `@end_date` / `@timezone`
- `GROUP BY date × market_id × channel_id × currency` with `SUM(spend)`
- fiscal-quarter mapping remains `rollup_raw_actuals()` (`fiscal_year_x_quarter/v1`)

The client cannot supply SQL, table path, project, dataset, or expressions (`test_client_cannot_supply_bq_table`, `test_client_cannot_supply_sql`). Portfolio HTTP still accepts only `fiscal_year`.

`P6_03_PRODUCTION_ACTUALS_QUERY_PENDING` remains a historical constant. Production no longer raises it; unready sources use `PRODUCTION_ACTUALS_SOURCE_NOT_READY`.

## D. Normalization / period / currency

| Proof | Test |
|---|---|
| BQ rows → `ActualSpendAllocation` | `test_bq_rows_normalize_to_actual_spend_allocation` |
| Decimal amounts | `test_amount_uses_decimal` |
| Canonical `market_id` / `channel_id` | `test_market_id_canonical`, `test_channel_id_canonical` |
| Duplicate source grain rejected | `test_duplicate_grain_rejected` |
| Explicit `0` ≠ missing | `test_zero_distinct_from_missing` |
| Daily → fiscal quarter | `test_daily_to_quarter_period_mapping` |
| Timezone policy | `test_timezone_policy_pinned` |
| Missing fiscal year fails closed | `test_missing_fiscal_policy_fails` |
| Currency match / mismatch | `test_currency_match`, `test_currency_mismatch_review_required` |

Empty BQ result is no rows (MISSING). Explicit `0` after SUM is ZERO. No Cartesian zero grid.

## E. Portfolio states

| State | Proof |
|---|---|
| `PLAN_AND_ACTUALS` | `test_plan_plus_prod_actuals_is_plan_and_actuals` |
| `ACTUALS_ONLY` | `test_prod_actuals_only_is_actuals_only` |
| Unavailable source stays `PLAN_ONLY` | `test_unavailable_prod_source_does_not_fabricate_actuals` |
| Stale source still assembles, not current | `test_stale_source_not_current_actuals` |

Missing binding: `ACTUALS_SOURCE_NOT_CONFIGURED` / `PRODUCTION_ACTUALS_SOURCE_NOT_READY`. Auth/query failures: `BQ_*` observed as `MISSING_ACTUALS_SOURCE`. Identity and duplicate-grain errors re-raise.

## F. Privacy

`ActualSpendQueryReceipt` is `_META` (receipt id, fingerprints, period, template version, row_count, status, issues). No amounts. Persisted only after `assert_metadata_only`. `ActualSpendAllocation` stays in `AMOUNT_BEARING_MODELS`.

| Proof | Test |
|---|---|
| Receipt has no amounts | `test_query_receipt_has_no_amounts` |
| Store rejects actual rows | `test_firestore_has_no_actual_rows` |
| Logs have no spend values | `test_logs_have_no_spend_values` |
| Portfolio `Cache-Control: private, no-store` | `test_portfolio_amount_response_private_no_store` |

## G. APIs / OpenAPI

Canonical `GET /v1/projects/{project_id}/investment-portfolio` is unchanged: optional `fiscal_year` only. No client actual-row upload.

`uv run --extra dev python scripts/export_openapi.py --check` green. Generated output was not regenerated.

- `contracts/openapi.yaml` sha256 `0324631abcc75edb788fee3613cd3dc7adbc7d58f77d977bb53c111fb74d368e`
- `contracts/schema/planning.schema.json` sha256 `2dc39c9e438e889d484d6c2ad2cdc0c60e660fac077c9a620683b0ee610fc464`

## H. Tests

Required names §§23–27 in `tests/unit/investment_planning/test_p6_03a_production_bq_actuals.py` (26 tests). Existing `tests/unit/investment_planning/test_p6_03_*.py` remain green.

Regression (all passed):

```text
uv run --extra dev python -m pytest tests/unit/investment_planning tests/unit/investment_optimization tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_prem3_api_openapi.py
```

Ruff green on P6-03A paths (`app/investment_planning/actuals.py`, `bigquery_actuals.py`, contracts/errors/enums/ids/observations/service/store, `app/integrations/google/adapters.py`, `app/service/app.py`, P6-03A tests). Pre-existing `firestore.py` UP047 was not rewritten.

## I. Remaining blockers

Live customer-cloud BigQuery actuals query was not run and is not a closeout gate. Fake BQ + in-memory DF store close the adapter. Clerk/Stripe SaaS proofs, durable Evaluation dispatch, and P6-07 constraints are unchanged.

## J. Docs

- [P6_03A_PRODUCTION_BIGQUERY_ACTUALS.md](P6_03A_PRODUCTION_BIGQUERY_ACTUALS.md)
- [ACTUAL_SPEND_QUERY_AUTHORITY.md](ACTUAL_SPEND_QUERY_AUTHORITY.md)
- Pending-blocker language removed from [PORTFOLIO_ACTUALS_INTEGRATION.md](PORTFOLIO_ACTUALS_INTEGRATION.md) and [P6_03_COMPLETION_REPORT.md](P6_03_COMPLETION_REPORT.md)
