# P6-03 completion report

Governed actual-spend integration, four-state portfolio assembly, evidence coverage, and deterministic observations on the isolated P6-03 worktree.

## A. Git isolation

| Item | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-03` |
| Branch | `feature/prem3-p6-03-actuals-coverage-observations` (renamed in place from `feature/prem3-p6-03-actuals-measurement-coverage`) |
| P6-02 base SHA | `c1823dd42b9c1916f96ca08fb9421cb30e2be379` |
| Final HEAD | This checkpoint commit on `feature/prem3-p6-03-actuals-coverage-observations` |
| Status | `uv.lock` left untracked |

Read-only surfaces (`app/modeling/mmm/**`, `app/modeling/mta/**`, workers, `app/identity_graph/**`) were not modified. No push.

## B. Actuals source

- `ActualSpendSourceRef` — Firestore metadata only (ids, BQ refs, window, as-of, currency, timezone, authority, status, `source_fingerprint`). No rows.
- `ActualSpendAllocation` — transient Decimal row. Type-rejected by `assert_metadata_only`.
- `ActualSpendQuery` port:
  - `TestOnlyActualSpendAdapter` — `SYNTHETIC` / `TEST_ONLY`; cannot be labeled customer-governed.
  - `DataFoundationActualSpendAdapter` — existing `SourceBinding` with `date` + `market_id` + `channel_id` + `spend` + `currency` + timezone. Consumes DF freshness/quality. Production BigQuery fetch is `BigQueryActualSpendAdapter` (`actual_spend_bq_query/v1`; see P6-03A).

Missing binding → `ACTUALS_SOURCE_NOT_CONFIGURED`. Query failure → `ACTUALS_SOURCE_UNAVAILABLE`. Never fabricate `PLAN_AND_ACTUALS` / `ACTUALS_ONLY`. `canonical_media` is not actual-spend authority.

## C. Portfolio state

| State | Proof |
|---|---|
| `NEITHER` | `test_neither_when_no_plan_no_actuals`; HTTP empty portfolio |
| `PLAN_ONLY` | P6-02 HTTP preserved; `test_plan_only_when_approved_plan_no_actuals` |
| `PLAN_AND_ACTUALS` | `test_http_plan_and_actuals_and_actuals_only` with TEST_ONLY adapter |
| `ACTUALS_ONLY` | same HTTP test; baseline `ACTUAL_YTD` |

`GOVERNED_ACTUALS` remains in `ACTUAL_SPEND_BASELINES`. Actuals never become `APPROVED_PLAN`.

Plan present + actuals outage stays `PLAN_ONLY` with `MISSING_ACTUALS_SOURCE`; actuals are not zero-filled.

## D. Canonical grain

Join is `require_canonical_market_id` × `require_canonical_channel_id` × `fiscal_year × quarter`. Display labels, ISO codes, and unknown IDs fail closed.

## E. Period alignment

Rule `fiscal_year_x_quarter/v1`. Daily rows map by source timezone. Weekly rows that span a quarter boundary raise `PERIOD_MAPPING_REQUIRED`. Fiscal calendar uses `InvestmentPlan.fiscal_start_month` (default 1). Unknown timezone or grain fails closed.

## F. Currency

Plan currency must match actuals. Mixed currencies without governed FX raise `CURRENCY_REVIEW_REQUIRED`. P6-03 does not implement FX.

## G. Missing vs zero

No row → missing. Explicit `0` → zero. Unavailable source → error/observation, not zero. Remaining/variance require both inputs.

## H. Portfolio math

`remaining = approved - actual`. `variance = actual - approved`. Percent only when plan known and non-zero. `Decimal` `ROUND_HALF_EVEN` to 2 places. `ACTUALS_ONLY` omits approved/remaining/variance (unavailable, not zero).

## I. Evidence coverage

Categories with real refs: `DATA_FOUNDATION`, `MMM`, `MTA`, `EXPERIMENT`, `BRAND`, `EXPOSURE_INTEGRITY`. Scope `PROJECT` / `MARKET` / `CHANNEL` / `MARKET_CHANNEL_PERIOD`. Status `COVERED` / `PARTIAL` / `MISSING` / `REVIEW_REQUIRED` / `NOT_APPLICABLE` / `UNKNOWN`. MTA `causal=False`. Accepted MMM `causal=True`. No `OPTIMIZATION_READY`. No campaign/audience grain.

## J. Portfolio observations

Implemented types: `ACTUAL_EXCEEDS_PLAN`, `ACTUAL_BELOW_PLAN`, `ACTUAL_WITHOUT_PLAN`, `PLAN_WITHOUT_ACTUALS`, `MISSING_ACTUALS_SOURCE`, `STALE_ACTUALS_SOURCE`, `MEASUREMENT_COVERAGE_MISSING`, `MEASUREMENT_COVERAGE_PARTIAL`. Identity/currency/period failures raise rather than silently observe. No amount arrays in Firestore. Observations do not mutate the Investment Plan.

## K. Privacy

`Cache-Control: private, no-store`. Firestore stores source ref, snapshot (`actuals_source_id`), coverage metadata, observation metadata. Rejects `PortfolioView` and `ActualSpendAllocation`.

## L. APIs

Canonical `GET /v1/projects/{project_id}/investment-portfolio`. Hidden workspace alias. `Feature.PORTFOLIO_VIEW`. Optional `fiscal_year` query only. No client actual rows.

- `contracts/openapi.yaml` sha256 `3677b08a76d663049564f2eb1b2f61ff7f465c43cb9247f5c1e40e35e4b7665b`
- `contracts/schema/planning.schema.json` sha256 `e0315ce91459b561a8b9c14ff9d9f1b43696a95ece799a892d4a76d8849a218a`

## M. Tests

Named cases from spec §§50–61 live in:

- `tests/unit/investment_planning/test_p6_03_actuals.py`
- `tests/unit/investment_planning/test_p6_03_coverage_observations.py`
- `tests/unit/investment_planning/test_p6_03_privacy_http.py`

## N. Regressions

```text
uv run --extra dev python -m pytest tests/unit/investment_planning tests/unit/identity_graph tests/unit/data_foundation tests/unit/test_prem3_drive_governance.py tests/unit/test_prem3_api_openapi.py
uv run --extra dev python scripts/export_openapi.py --check
```

Result: **227 passed**. OpenAPI `--check` matches. Ruff is clean on P6-03 files; pre-existing P6-01 line-length findings were not rewritten.

## O. P6-04 handoff

Optimization Readiness may consume:

- `PortfolioSnapshotRef` (metadata, `actuals_source_id`, fingerprint including actuals as-of)
- `PortfolioCoverageState` / `PortfolioBaselineKind` (`ACTUAL_YTD` for actuals-only)
- `PortfolioEvidenceCoverage` items (explicit scope/status; MTA not causal)
- `PortfolioObservation` metadata (no amounts)
- Transient `PortfolioView` remaining/variance only when both plan and actual exist

P6-04 still owns `OPTIMIZATION_READY`, portfolio-to-model mapping, and Meridian `BudgetOptimizer`. P6-03 does not load response curves.

## P. Blockers

Production BigQuery actual-spend fetch is closed on P6-03A (`feature/prem3-p6-03a-production-bq-actuals`). A governed DF binding without a usable/authorized source stays fail-closed (`PRODUCTION_ACTUALS_SOURCE_NOT_READY` / `BQ_*`) and does not fabricate `ACTUALS_ONLY` or `PLAN_AND_ACTUALS`. Live customer-cloud query proof is not a P6-03 closeout gate.
