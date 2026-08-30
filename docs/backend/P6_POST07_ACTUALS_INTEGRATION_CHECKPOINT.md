# P6 post-07 actuals integration checkpoint

Team 1 closeout. This SHA is the only valid P6-08 base. Nothing pushed.

## A. P6-03A checkpoint

| Field | Value |
|---|---|
| worktree | `C:/Users/zroda/Desktop/prem3-p6-03a` |
| branch | `feature/prem3-p6-03a-production-bq-actuals` |
| final committed HEAD | `eced1acf144c0d469e2c3b316f5391398c879bd8` |
| git status --short | `?? uv.lock` |
| commit | `eced1ac feat(planning): add production BigQuery actuals adapter` |

Team 1 did not modify P6-03A.

## B. P6-07 implementation checkpoint

| Field | Value |
|---|---|
| worktree | `C:/Users/zroda/Desktop/prem3-p6-07` |
| branch | `feature/prem3-p6-07-flexible-budget-advanced-constraints` |
| implementation checkpoint HEAD | `9199895` |
| commit | `9199895 feat(planning): add flexible budget and advanced constraints` |

## C. Meridian 1.8 runtime proof

| Field | Observed |
|---|---|
| environment | `C:/Users/zroda/Desktop/prem3-p6-07/.local/meridian312/Scripts/python.exe` (Python 3.12.12) |
| installed package/version | `meridian.__version__ == '1.8.0'` at `.local/meridian312/Lib/site-packages/meridian` |
| import result | `from meridian.analysis.optimizer import BudgetOptimizer` succeeded |
| BudgetOptimizer interface | live `optimize(...)` includes `fixed_budget`, `budget`, `target_roi`, `target_mroi`, `use_kpi`, `new_data`; no `B_min` / `B_max` |
| fixed-budget result | adapter sends `fixed_budget=True`, `budget`, ±0.3, `gtol=0.0001`; `_validate_budget` accepts |
| flexible-budget result | adapter omits `budget`, sends `fixed_budget=False` + `target_roi`; `_validate_budget` accepts |
| adapter changes required | none (already aligned at `2d1a3b3`) |
| proof artifact | [P6_07_MERIDIAN_1_8_RUNTIME_PROOF.md](P6_07_MERIDIAN_1_8_RUNTIME_PROOF.md) |

Command: `PYTHONPATH=. .local/meridian312/Scripts/python.exe -m pytest tests/unit/investment_optimization/test_p6_07_native_meridian_runtime.py -v` → **3 passed**.

## D. P6-07 final checkpoint

| Field | Value |
|---|---|
| P6_07_FINAL_COMMITTED_HEAD | `be554242b8b64cc702545902949044b163db6030` |
| git status --short | `?? uv.lock` |
| commits | `9199895` impl; `2d1a3b3` kwargs align; `be55424 test(planning): prove Meridian 1.8 flexible optimization interface` |

## E. Ancestry proof

| Field | Value |
|---|---|
| P6-06 base | `e1a9477b9ce57719d56f0d522d3cb85540823362` |
| P6-03A descendant? | yes (`git merge-base --is-ancestor e1a9477 eced1ac`) |
| P6-07 descendant? | yes (`git merge-base --is-ancestor e1a9477 be55424`) |

## F. Integration

| Field | Value |
|---|---|
| integration worktree | `C:/Users/zroda/Desktop/prem3-p6-post07-actuals-integration` |
| integration branch | `integration/prem3-p6-post07-actuals` |
| base | `be554242b8b64cc702545902949044b163db6030` (`P6_07_FINAL_COMMITTED_HEAD`) |
| P6-03A commit(s) integrated | `eced1acf144c0d469e2c3b316f5391398c879bd8` via `git cherry-pick` → `a11c54344359f880418296de475b47b330b57cee` |
| conflicts | none (`app/service/app.py` auto-merged) |
| resolutions | verified both wirings kept: `BigQueryActualSpendAdapter` on `DataFoundationActualSpendAdapter` and `AdvancedOptimizationService` + `NativeMeridianFixedBudgetAdapter` |

Stale worktree at `fd37bdf` was removed and recreated. `feature/prem3-p6-08-exposure-risk-delivery-health` remains at `fd37bdf` and was not edited. Team 2 must rebase P6-08 onto this checkpoint.

## G. Combined proof

Exact test commands (integration worktree; interpreter `C:/Users/zroda/Desktop/prem3-p6-07/.venv/Scripts/python.exe`):

```text
python -m pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_channel_registry.py
python scripts/export_contracts.py --check
python scripts/export_openapi.py --check
python -m ruff check app/investment_optimization tests/unit/investment_optimization app/service/routers/investment_portfolio.py app/service/investment_planning_models.py app/service/app.py app/investment_planning/bigquery_actuals.py app/investment_planning/actuals.py tests/unit/investment_planning/test_p6_03a_production_bq_actuals.py tests/unit/investment_planning/test_p6_03_actuals.py
```

| Check | Result |
|---|---|
| test counts | **446 passed**, 3 skipped |
| OpenAPI --check | green |
| planning schema --check | green |
| Ruff | green on P6-03A / P6-07 / integration paths. Pre-existing P6-01 `firestore.py` UP047 and P6-01 E501/I001 were not rewritten |
| Meridian proof | retained from P6-07 (`be55424`); integration worktree has no `.local/meridian312` |

Committed UTF-8 SHA-256 (git blobs):

| Artifact | SHA-256 |
|---|---|
| `contracts/schema/planning.schema.json` | `13f0e80a8f01870b1709b464ae4b8c5338b800eef3bcf39b42c4f0c3a78aa6d1` |
| `contracts/openapi.yaml` | `b03d57d491e048ec4d0e33f6ee562b40ee6291f86a8e67c7dc437da084581421` |

No generated regeneration. Coexistence already covered by existing tests (P6-03A fail-closed actuals, P6-07 `p6-05/v1` vs `p6-07/v1` path selection).

## H. Final checkpoint

Recorded after this document is committed:

| Field | Value |
|---|---|
| P6_POST07_ACTUALS_INTEGRATION_READY_HEAD | *(this commit)* |
| git status --short | `?? uv.lock` |
| integration commit(s) | `a11c543` cherry-pick of P6-03A; this checkpoint doc |
| pushed? | no |

## War-room

- P6-03A FINAL — Production BigQuery Actuals (`eced1ac`)
- P6-07 FINAL — Flexible budget + Meridian 1.8 interface proof (`be55424`)
- P6-03A + P6-07 INTEGRATED — this HEAD
- P6-08 READY FOR TEAM 2 from this SHA only
