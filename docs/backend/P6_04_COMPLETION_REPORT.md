# P6-04 completion report

Optimization readiness, Model Consumption Contract compilation, and governed portfolio-to-model mapping on the isolated P6-04 worktree. No optimizer execution. Production BigQuery actuals remain fail-closed.

## A. Git isolation

| Item | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-04` |
| Branch | `feature/prem3-p6-04-optimization-readiness` |
| P6-03 base SHA | `3998521264a28b38db904dab38e207e17cfe8078` |
| Final HEAD | This checkpoint commit on `feature/prem3-p6-04-optimization-readiness` |
| Status | `uv.lock` left untracked |

Read-only surfaces (`app/modeling/mmm/**` state machine, `app/modeling/mta/**`, Identity Graph, workers) were not modified. No push.

## B. Accepted-model authority

Eligible: `MMMModelVersion.accepted is True` **and** `state is MODEL_ACCEPTED`.

Ineligible: `MODEL_READY`, `ITERATION_REQUIRED`, `FAILED`, `FAILED_PRE_FIT`, designing/configuring/fitting/review-pending stages. Acceptance is never inferred.

Selection: 0 accepted → `NO_ACCEPTED_MODEL`; 1 accepted → that `model_version_id`; 2+ without explicit Project-scoped `model_version_id` → `MULTIPLE_ACCEPTED_MODELS`. No `CURRENT_ACCEPTED_MODEL_POINTER`. Cross-project / cross-tenant mapping fails.

## C. Model Consumption Contract

Planning compiles or caches a `ModelConsumptionContract` (`omcc_`) **projection** from accepted version + ModelPlan / acceptance / artifact **refs**. MMM remains canonical. Fields: `model_version_id`, `model_plan_fingerprint`, `model_acceptance_ref`, `meridian_version` (pinned `1.8.0`), `runtime_mode`, modeled window, geo semantics, KPI, currency, variables (`model_variable_id`, role, eligibility, optional explicit `canonical_channel_id` / `canonical_market_id`, spend-semantics), optimizer/response artifact refs, `fingerprint`.

Missing required fields → `MODEL_CONSUMPTION_CONTRACT_INCOMPLETE`. A projection that diverges from the accepted `MMMModelVersion` identity, plan fingerprint, or window → `MODEL_CONSUMPTION_PROJECTION_STALE`. Canonical channel IDs are never inferred from Meridian `media_channels` names. `app/tools/model_consumption.py` remains the MODEL_READY BigQuery view registry.

## D. Portfolio-to-model mapping

`PortfolioModelMapping` / `PortfolioModelMappingEntry` (`pmap_`, `ment_`). Authority: `MODEL_CONTRACT_EXACT`, `CANONICAL_CHANNEL_BINDING`, `CANONICAL_MARKET_BINDING`, `USER_CONFIRMED`, `APPROVED_CUSTOM_MAPPING`. Fuzzy/similarity/LLM rejected.

## E. Channel compatibility

1:1 `AUTO_SAFE` on canonical IDs. Many-to-one requires `AGGREGATE_FOR_MODEL` (combined bucket). One-to-many requires `APPROVED_ALLOCATION_SPLIT` (10000 bps). Many-to-many → `NOT_SUPPORTED_V1`.

## F. Market compatibility

`DIRECTLY_MODELED` / `AGGREGATED_IN_MODEL` / `NOT_MODELED` / `REVIEW_REQUIRED`. National + multiple markets is aggregated, not market-level precision. Geo without explicit market bind is `REVIEW_REQUIRED`. Display labels are not identity.

## G. Period compatibility

Fiscal horizon vs modeled window. Future horizon allowed only when `future_horizon_allowed`. Failure: `PERIOD_COMPATIBILITY_REVIEW_REQUIRED`. P6-03 `PERIOD_MAPPING_REQUIRED` observations remain blockers.

## H. Currency / spend semantics

Plan currency must match contract currency (`CURRENCY_COMPATIBILITY_REVIEW_REQUIRED`). Compatible spend tags: `APPROVED_MEDIA_SPEND`, `NET_MEDIA_SPEND`. Mismatch → `SPEND_SEMANTICS_MISMATCH` / `NOT_READY`.

## I. Variable eligibility

Existence ≠ optimizable. Control / organic / context / outcome never auto-optimizable. Unmapped treatments: fixed-at-zero, fixed-baseline, excluded, review-required.

## J. Causal coverage

`OptimizationEvidenceCoverage` (`oecov_`). Accepted MMM + response artifact refs are causal. MTA is tactical context only (`MTA_NOT_CAUSAL_AUTHORITY`); cannot satisfy `MODEL_ACCEPTED` or artifact checks.

## K. OptimizationInputContract

Metadata (`oinc_`): snapshot/model/mapping IDs, `baseline_kind=APPROVED_PLAN`, period bounds, currency, variable ID sets, fingerprints, `budget_resolution_path=APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`. No total budget. P6-05 re-resolves Drive plan → transient `PortfolioView` → selected fiscal period.

## L. Readiness receipt

Immutable `OptimizationReadinessReceipt` (`oready_`). Status: `OPTIMIZATION_READY` / `NOT_READY` / `REVIEW_REQUIRED` / `NOT_CONFIGURED` / `STALE`. Thirteen required checks. Content-addressed fingerprint over checks, issues, and pinned authority fingerprints. New evaluation if plan/model/mapping/policy change. Policy version `p6-04/v1`.

V1 baseline: `PLAN_ONLY` and `PLAN_AND_ACTUALS` may be ready; `ACTUALS_ONLY` → `APPROVED_PLAN_REQUIRED`; `NEITHER` → `NOT_CONFIGURED`.

## M. Project capability

Existing `BUDGET_OPTIMIZATION`. No accepted model still `REQUIRES_ACCEPTED_MMM_MODEL`. Accepted + generated overlay: `OPTIMIZATION_READY` / `NOT_READY` / `REVIEW_REQUIRED` / `NOT_CONFIGURED`. `STALE` presented as `NOT_READY` with a stale reason. No new `CapabilityFamily`.

## N. APIs

```text
POST/GET  /v1/projects/{project_id}/investment-portfolio/model-mapping
GET       /v1/projects/{project_id}/investment-portfolio/model-mapping/{mapping_id}
GET       /v1/projects/{project_id}/investment-portfolio/optimization-readiness
POST      /v1/projects/{project_id}/investment-portfolio/optimization-readiness/evaluate
```

Entitlement: `Feature.PORTFOLIO_VIEW`. Tenant from credential. No optimizer execution route.

- `contracts/openapi.yaml` sha256 `f9dca9867abdb90937a36f19d36be7b4dfffac0dddad4f7581f6d80256dda213`
- `contracts/schema/planning.schema.json` sha256 `4a64123be72d30456745dac46711c51044db2f88ae3ec62dc53e8bd8af893bcd`

## O. Tests

Named cases from spec §§65–75 live in:

- `tests/unit/investment_optimization/test_p6_04_accepted_model.py`
- `tests/unit/investment_optimization/test_p6_04_mapping.py`
- `tests/unit/investment_optimization/test_p6_04_compatibility.py`
- `tests/unit/investment_optimization/test_p6_04_readiness.py`
- `tests/unit/investment_optimization/test_p6_04_privacy_http.py`

Home overlay: `test_budget_optimization_surfaces_generated_readiness_when_model_accepted`.

## P. Regressions

```text
uv run pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py
uv run python scripts/export_openapi.py --check
uv run python scripts/export_contracts.py --check
uv run ruff check app/investment_optimization tests/unit/investment_optimization tests/unit/test_project_architecture.py app/service/routers/investment_portfolio.py app/service/investment_planning_models.py app/tools/schema_export.py app/project/home.py app/service/app.py
```

Result: **198 passed**. OpenAPI/schema `--check` match. Ruff clean on P6-04 files.

`tests/unit/test_mmm_modeling.py` has two pre-existing vendored-skill SHA mismatches on this checkout (`skills/meridian_model_building/SKILL.md`). Not repaired (unrelated MMM asset pinning).

## Q. P6-05 handoff

To execute native Meridian fixed-budget optimization, P6-05 needs:

- `OptimizationReadinessReceipt.status == OPTIMIZATION_READY` (not stale)
- pinned `portfolio_fingerprint`, `model_fingerprint`, `mapping_fingerprint`, `input_contract_fingerprint`, `model_consumption_contract_fingerprint`, `policy_version=p6-04/v1`
- `OptimizationInputContract.budget_resolution_path == APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`
- `ModelConsumptionContract.optimizer_artifact_ref` and `response_evidence_ref`
- mapping `COMPLETE` with optimizable variable IDs

Do not persist amounts. Re-resolve approved totals from Drive via transient `PortfolioView`. Keep `UnimplementedMeridianBudgetOptimizerAdapter.optimize` unimplemented until P6-05.

## R. Blockers

`P6_03_PRODUCTION_ACTUALS_QUERY_PENDING` was the P6-04-era fail-closed gap. P6-03A implements production fetch; P6-04 contracts are unchanged. Production consumption source is empty unless a complete contract is injected — incomplete → not ready.

## War-room checkpoint

```text
P6-00  ✅ Architecture Freeze
P6-01  ✅ Drive-native Investment Plan
P6-02  ✅ Portfolio Snapshot
P6-03  ✅ Actuals + Coverage + Observations
P6-03A ✅ Production BigQuery actuals (`actual_spend_bq_query/v1`) on `feature/prem3-p6-03a-production-bq-actuals`
P6-04  ✅ Optimization Readiness + Portfolio-to-Model Mapping
P6-05  ⏭ Native Meridian Fixed-Budget Optimization
```

- Final committed HEAD: this P6-04 checkpoint on `feature/prem3-p6-04-optimization-readiness`
- Uncommitted: `uv.lock` (local `uv sync`; left untracked)
- Environment: none blocking P6-04. Production actuals are implemented on P6-03A; missing/unauthorized sources stay fail-closed.
- Next executable mission: **P6-05 Native Meridian Fixed-Budget Optimization**
