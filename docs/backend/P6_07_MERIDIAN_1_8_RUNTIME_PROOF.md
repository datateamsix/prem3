# P6-07 Meridian 1.8.0 runtime/API proof

Recorded 2026-08-30 on `feature/prem3-p6-07-flexible-budget-advanced-constraints` at parent `2d1a3b3cb0b18fb91cd8ba61cd419488871cfab7`. Synthetic fixture only. No customer-cloud model run.

## Environment

| Field | Observed value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-07` |
| Interpreter | `C:/Users/zroda/Desktop/prem3-p6-07/.local/meridian312/Scripts/python.exe` |
| Python | `3.12.12` (MSC v.1944 64-bit) |
| Package path | `C:/Users/zroda/Desktop/prem3-p6-07/.local/meridian312/Lib/site-packages/meridian/__init__.py` |
| Pin family | same isolated 3.12 runtime as P6-05 / MMM optimizer-worker (`google-meridian==1.8.0`), not the Python 3.13 ADK venv |

`pip show` is not available in this interpreter (`No module named pip`). Version was read from the imported package.

## Import proof

Command:

```powershell
cd C:/Users/zroda/Desktop/prem3-p6-07
.local/meridian312/Scripts/python.exe -c "import meridian; from meridian.analysis.optimizer import BudgetOptimizer; print(repr(meridian.__version__)); print(BudgetOptimizer)"
```

Result:

- `meridian.__version__ == '1.8.0'`
- `BudgetOptimizer` is `<class 'meridian.analysis.optimizer.BudgetOptimizer'>`
- `BudgetOptimizer.optimize` is a live function (not a mock)

TensorFlow/oneDNN deprecation warnings printed during import. They were not treated as API failures.

## Inspected API / signature

`inspect.signature(BudgetOptimizer.optimize)` on the installed 1.8.0 package:

```text
(self, new_data: DataTensors | None = None, use_posterior: bool = True,
 selected_geos: Sequence[str] | None = None,
 selected_times: tuple[str | None, str | None] | None = None,
 start_date: str | datetime | date | numpy.datetime64 | None = None,
 end_date: str | datetime | date | numpy.datetime64 | None = None,
 fixed_budget: bool = True, budget: float | None = None,
 pct_of_spend: Sequence[float] | None = None,
 spend_constraint_lower: float | Sequence[float] | None = None,
 spend_constraint_upper: float | Sequence[float] | None = None,
 target_roi: float | None = None, target_mroi: float | None = None,
 gtol: float = 0.0001, use_optimal_frequency: bool = True,
 max_frequency: float | None = None, use_kpi: bool = False,
 confidence_level: float = 0.9, batch_size: int = 100,
 optimization_grid: OptimizationGrid | None = None) -> OptimizationResults
```

Present (required for P6-07 compile/adapter): `new_data`, `use_posterior`, `selected_geos`, `start_date`, `end_date`, `fixed_budget`, `budget`, `pct_of_spend`, `spend_constraint_lower`, `spend_constraint_upper`, `target_roi`, `target_mroi`, `gtol`, `use_kpi`.

Absent: `B_min`, `B_max`.

`meridian.analysis.optimizer._validate_budget(fixed_budget, budget, target_roi, target_mroi)` observed rules:

- `fixed_budget=True` forbids `target_roi` / `target_mroi`; `budget` if set must be `> 0`
- `fixed_budget=False` forbids `budget`; requires exactly one of `target_roi` / `target_mroi`

## Test command

```powershell
cd C:/Users/zroda/Desktop/prem3-p6-07
$env:PYTHONPATH = "."
.local/meridian312/Scripts/python.exe -m pytest tests/unit/investment_optimization/test_p6_07_native_meridian_runtime.py -v
```

## Result

```text
platform win32 -- Python 3.12.12, pytest-9.1.1
collected 3 items
tests/unit/investment_optimization/test_p6_07_native_meridian_runtime.py ...
3 passed in 13.61s
```

These tests import real `google-meridian==1.8.0`, bind compiled kwargs to the live `BudgetOptimizer.optimize` signature, call real `_validate_budget`, and enter `NativeMeridianFixedBudgetAdapter`. `optimize` is spied so a customer `.binpb` is not required.

## Fixed-budget proof (P6-05 path)

`test_optimize_fixed_budget_remains_compatible` through `NativeMeridianFixedBudgetAdapter.optimize_fixed_budget`:

- reaches `BudgetOptimizer.optimize`
- `fixed_budget=True`
- `budget == 100.0`
- no `target_roi` / `target_mroi`
- `use_posterior=True`
- `spend_constraint_lower == 0.3`
- `spend_constraint_upper == 0.3`
- `gtol == 0.0001`
- adapter source still contains `fixed_budget=True`

## Flexible-budget proof (P6-07 path)

`test_optimize_flexible_budget_reaches_native_interface` through `compile_native_spec` + `NativeMeridianFixedBudgetAdapter.optimize_flexible_budget` with `TARGET_ROI_FLEXIBLE_BUDGET`:

- reaches `BudgetOptimizer.optimize`
- `fixed_budget=False`
- `budget` omitted (`_validate_budget` would raise if present)
- `target_roi == 2.0`
- `target_mroi` omitted
- `use_posterior=True`
- `gtol == 0.0001`
- `use_kpi=True`

`test_installed_meridian_flexible_interface_matches_compile_native` also bound the compiled flexible kwargs to the live signature and confirmed `DataTensors` annotations include `media_spend` and `revenue_per_kpi`.

## Differences found

None versus the adapter already committed at `2d1a3b3` (`fix(planning): align flexible budget kwargs with Meridian 1.8.0`). That commit already omitted `budget` when `fixed_budget=False`.

Live 1.8.0 also exposes `selected_times`, `use_optimal_frequency`, `max_frequency`, `confidence_level`, `batch_size`, and `optimization_grid`. P6-07 does not pass those kwargs. They were not required for signature bind or `_validate_budget`.

## Changes required

None. Adapter and compiler were not modified for this proof.

## Not claimed

- Live `BudgetOptimizer.optimize` on an accepted customer `.binpb`
- Cloud Run optimizer-worker dispatch
- `new_data` / `DataTensors` flighting wiring
- P6-03A integration (separate checkpoint)
