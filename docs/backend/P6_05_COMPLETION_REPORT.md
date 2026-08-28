# P6-05 completion report

Native Meridian fixed-budget optimization on the isolated P6-05 worktree. Flexible budget, CVaR, proposal approval, and Drive plan mutation are out of scope. Production BigQuery actuals remain fail-closed.

## A. Git isolation

| Item | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-05` |
| Branch | `feature/prem3-p6-05-native-meridian-fixed-budget-optimization` |
| P6-04 base SHA | `8d46b50dcc28c5f18bcdfc925a0df836289e1962` |
| Final HEAD | This checkpoint on the P6-05 branch |
| Status | `uv.lock` left untracked |

Did not start from this Cursor M3 checkout, dirty P6-04, P6-03A, IG, or M5. No push.

## B. Native API discovery

Installed `google-meridian==1.8.0`. `BudgetOptimizer.optimize` exists with `fixed_budget`, `budget`, `pct_of_spend`, `spend_constraint_lower/upper`, `gtol=0.0001`, `use_posterior`. `OptimizationResults.optimized_data` exposes `spend` plus optional outcome variables. `meridian_serde.load_meridian` exists; schema extra is required at load time (fit worker image already installs `[schema]`). Recorded in [NATIVE_MERIDIAN_FIXED_BUDGET_OPTIMIZATION.md](NATIVE_MERIDIAN_FIXED_BUDGET_OPTIMIZATION.md). `MERIDIAN_OPTIMIZER_API_REVIEW_REQUIRED` is reserved if the class cannot be imported.

## C. OptimizationRun

`OptimizationRun` (`orun_`) is metadata: kind `FIXED_BUDGET`, status/phase, readiness/input/model/mapping/snapshot refs + fingerprints, `runtime_version=1.8.0`, worker_ref, artifact refs, result fingerprint, failure class/stage/retry semantics, execution key, created_by. No amounts. Not `OptimizationExecutionPlan.proposal_id`.

## D. Budget authority

Re-resolved via `APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`. Client arrays, Firestore, actuals, and MTA cannot supply the fixed budget. Unapproved plans fail closed. `OptimizerBudgetVector` is process-only.

## E. Dispatch revalidation

Receipt must be `OPTIMIZATION_READY`. Portfolio/mapping/input/model fingerprints are re-checked. Consumption projection is rebound with `bind_projection_to_accepted_model`. Stale → `OPTIMIZATION_READINESS_STALE`. MMM acceptance/FitPlan/Drive bytes are not mutated.

## F. Native adapter

`NativeMeridianFixedBudgetAdapter.optimize_fixed_budget` calls `BudgetOptimizer.optimize(use_posterior=True, fixed_budget=True, budget=<float>, pct_of_spend=<approved shares>, spend_constraint_lower=0.3, spend_constraint_upper=0.3, gtol=0.0001)`. Flexible/CVaR remain on `UnimplementedMeridianBudgetOptimizerAdapter`. Unit tests use `ScriptedFixedBudgetOptimizer` and assert the production import path.

## G. Numeric invariant

Planning `ROUND_HALF_EVEN` to 2 places. Residual cents to the largest recommended optimizable line (amount desc, then `model_variable_id`). After reconcile `|sum(rec) - fixed| == 0`. Pre-round drift beyond `max(0.01, gtol * budget)` → `OPTIMIZER_BUDGET_INVARIANT_FAILED`.

## H. Result validation

Expected mapped variables only. Unknown/missing rejected. NaN/inf rejected. Negatives rejected in V1. Zero ≠ missing. Fixed unchanged. Excluded not reallocated.

## I. Artifact + read-back

Immutable GCS `optimization_result_{run_id}`. Read-back verifies existence, schema `p6-05/v1`, key set, fingerprint, Decimal total. Failed read-back never `COMPLETE`.

## J. Labels

`MODEL_RECOMMENDED` for spends. `MODEL_ESTIMATE` for optional Meridian outcome fields when present. Never `APPROVED_PLAN`.

## K. HTTP

```text
POST   /v1/projects/{project_id}/investment-portfolio/optimizations   202
GET    /v1/projects/{project_id}/investment-portfolio/optimizations
GET    /v1/projects/{project_id}/investment-portfolio/optimizations/{optimization_run_id}
GET    /v1/projects/{project_id}/investment-portfolio/optimizations/{optimization_run_id}/result
```

Entitlement `Feature.BUDGET_OPTIMIZATION`. Result is private/no-store. `/investment-optimizations` stays unregistered.

## L. Worker

Sibling `app/tools/meridian_optimizer_worker.py`. Reconstructs from `optimization_run_id`. Rejects untrusted path/tenant/image keys. Does not modify `execute_approved_fit`.

## M. Home overlay

Latest run `OPTIMIZATION_RUNNING` / `OPTIMIZATION_COMPLETE` after an accepted model. No accepted model still `REQUIRES_ACCEPTED_MMM_MODEL`.

## N. Persistence privacy

`assert_optimization_metadata_only` rejects budget/allocation arrays on runs and result refs. FakeFirestore dumps contain no amount arrays.

## O. P6-03A

P6-03A production fetch is implemented independently. PLAN_ONLY fixed-budget works without actuals.

## P. Tests

Required names in `tests/unit/investment_optimization/test_p6_05_optimization_run.py` and `test_p6_05_privacy_http.py`, plus Home overlay in `test_project_architecture.py`. P6-00/P6-04 files kept.

Regression: `pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py` passed.

## Q. Contracts

- `contracts/openapi.yaml` sha256 `e0da0cfdefe6466bf0cb26db81f4056a51199704708bcf9e646415a31e42181c`
- `contracts/schema/planning.schema.json` sha256 `35a3315ed745ecc0b3bbf8533cf6f9dcfce6c21c45bab1c3f6c1aa41f6a95e40`

## R. ADRs

`ADR-P6-037` … `ADR-P6-048` in [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md).

## S. Explicit non-goals (held)

Plan revision, proposal approval, flexible budget, P6-07 min/max, CVaR, frontier, forecasts, campaign/audience grain, provider writes, frontend, Identity Graph, MMM state-machine changes, production BQ actuals, modifying official fit worker behavior.

## War room

1. Isolation: P6-05 worktree at `8d46b50`, branch renamed to spec name.
2. Native API: `BudgetOptimizer.optimize` + `load_meridian` confirmed on 1.8.0.
3. Run record: `OptimizationRun`, not proposal_id.
4. Budget: Drive approved plan only.
5. Revalidate: stale fingerprints refuse.
6. Adapter: native fixed-budget; flexible/CVaR unimplemented.
7. Invariant: Decimal reconcile to exact fixed budget.
8. Artifact: immutable GCS + read-back.
9. Labels: MODEL_RECOMMENDED / MODEL_ESTIMATE.
10. HTTP: portfolio `/optimizations`, 202, private result.
11. Worker: sibling entrypoint; fit worker untouched.
12. Home: running/complete overlay; accepted-model gate kept.
13. Privacy: Firestore metadata only.
14. P6-03A: production fetch is implemented independently; missing/unauthorized sources stay fail-closed.
15. Tests: required names + P6-00/P6-04 green.
16. OpenAPI/schema exported.
17. ADRs 037–048.
18. Docs created/updated.
19. No Drive writes / no P6-06 routes.
20. `SHARED_MERIDIAN_WORKER_CHANGE_REQUEST`: a second Cloud Run Job name is required for production optimizer dispatch; do not reuse `execute_approved_fit`. Optimizer worker image must include `google-meridian[schema]==1.8.0` like the fit worker. No push.
