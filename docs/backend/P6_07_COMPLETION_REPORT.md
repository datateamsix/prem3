# P6-07 completion report

Flexible budget, future assumptions, and advanced constraints on native Meridian 1.8.0. P6-04/05/06 remain the fixed-budget, readiness, and proposal path.

## Isolation

| Field | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-07` |
| Branch | `feature/prem3-p6-07-flexible-budget-advanced-constraints` |
| Base HEAD | `e1a9477b9ce57719d56f0d522d3cb85540823362` (`feat(planning): add scenario and proposal governance`) |
| Team 2 P6-03A | not merged |
| Push | not done |

Final HEAD is the working tree at completion (commit only if asked).

## Native API proof

Documented in [FLEXIBLE_BUDGET_OPTIMIZATION.md](FLEXIBLE_BUDGET_OPTIMIZATION.md). Inspected `BudgetOptimizer.optimize` in `google-meridian==1.8.0`:

- Flexible: `fixed_budget=False` plus exactly one of `target_roi` / `target_mroi`
- No named `B_min` / `B_max`
- Spend box is `(1 ± constraint) * budget * allocation`
- `use_kpi=True` optimizes modeled KPI; `False` uses revenue
- Optional `new_data` `DataTensors`; `selected_geos`, `start_date`, `end_date`

P6-05 `optimize_fixed_budget` still contains `fixed_budget=True` and is used when no advanced inputs are supplied.

## Objective modes

- `MAX_EXPECTED_OUTCOME_FIXED_BUDGET` → existing fixed path / `fixed_budget=True`
- `TARGET_ROI_FLEXIBLE_BUDGET` → `fixed_budget=False`, `target_roi`
- `TARGET_MROI_FLEXIBLE_BUDGET` → `fixed_budget=False`, `target_mroi`
- `MAX_INCREMENTAL_CONTRIBUTION_VALUE` → native revenue path only with governed unit value

`PREM3_CVAR` remains deferred.

## Assumptions and constraint families

See [FUTURE_SCENARIO_ASSUMPTIONS.md](FUTURE_SCENARIO_ASSUMPTIONS.md) and [ADVANCED_OPTIMIZATION_CONSTRAINTS.md](ADVANCED_OPTIMIZATION_CONSTRAINTS.md). Feasibility and post-validation: [CONSTRAINT_VALIDATION_AND_FEASIBILITY.md](CONSTRAINT_VALIDATION_AND_FEASIBILITY.md).

## Proofs

- Feasibility refuses infeasible sets before dispatch
- Advanced readiness wraps P6-04 and stales when assumptions/constraints/objective/runtime change
- Fixed-budget P6-05 path unchanged (source inspection + regression tests)
- Firestore metadata has no amount arrays; amount HTTP is `private, no-store`; worker rejects constraint/assumption amount keys
- Artifact schema `p6-07/v1` for advanced results; fixed-only remains `p6-05/v1`

## HTTP

`POST/GET` assumption-sets, constraint-sets, `POST` constraint-sets/{id}/validate, `POST/GET` advanced-optimization-readiness. `POST /optimizations` remains backward compatible; optional `budget_mode`, `objective_mode`, `constraint_set_id`, `assumption_set_id`, `advanced_readiness_receipt_id`, `target_roi`, `target_mroi`.

OpenAPI/schema hashes (SHA-256 of committed UTF-8 bytes):

| Artifact | SHA-256 |
|---|---|
| `contracts/schema/planning.schema.json` | `13f0e80a8f01870b1709b464ae4b8c5338b800eef3bcf39b42c4f0c3a78aa6d1` |
| `contracts/schema/api.schema.json` | `8f7d98f9724edc42a9dd829728337023102e69a3e4038130ce8e5191b5329628` |
| `contracts/schema/manifest.json` | `ba8397bafa779fdb2ff04d4424bcdce3c652269b13bb5bb2adb8921e0f526069` |
| `contracts/openapi.yaml` | `b03d57d491e048ec4d0e33f6ee562b40ee6291f86a8e67c7dc437da084581421` |

Public schema exports refs and readiness (`ConstraintSetRef`, `ScenarioAssumptionSetRef`, `ConstraintValidationReceipt`, `AdvancedOptimizationReadinessReceipt`). Amount-bearing `FutureScenarioAssumptions` / `OptimizationConstraintSet` are not roots.

## Tests

```bash
uv run pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py
uv run python scripts/export_contracts.py --check
uv run python scripts/export_openapi.py --check
uv run ruff check app/investment_optimization tests/unit/investment_optimization app/service/routers/investment_portfolio.py app/service/investment_planning_models.py
```

Required suite: **332 passed** (2026-08-27). Ruff clean. Schema/OpenAPI `--check` clean.

Required P6-07 modules: `test_p6_07_assumptions.py`, `test_p6_07_constraints.py`, `test_p6_07_unsupported.py`, `test_p6_07_flexible.py`, `test_p6_07_privacy_http.py`.

## Native runtime proof (follow-up)

Isolated Python 3.12 interpreter with `google-meridian[schema]==1.8.0` (optimizer-worker pin family; same isolated runtime as P6-05/MMM, not the Python 3.13 ADK venv). Command:

```bash
PYTHONPATH=. .local/meridian312/Scripts/python.exe -m pytest tests/unit/investment_optimization/test_p6_07_native_meridian_runtime.py
```

`meridian.version.__version__ == 1.8.0`. Flexible kwargs omit `budget` (`_validate_budget`). Fixed path still sends `fixed_budget=True`, explicit `budget`, ±0.3, `gtol=0.0001`.

## Blockers

None for the P6-07 contract. Live Meridian 1.8.0 flexible dispatch still depends on an accepted-model optimizer artifact. Exposure/CVaR remain P6-08/P6-09. P6-03A is not integrated.
