# Flexible-budget optimization (P6-07)

P6-07 extends native Meridian `BudgetOptimizer` beyond fixed-budget allocation. There is no custom flexible-budget solver. Group-sum constraints that Meridian cannot encode are feasibility-checked and post-validated; they are not solved by PreM3.

Pinned package: `google-meridian==1.8.0`. Source of truth for this mission: `meridian/analysis/optimizer.py` at tag `v1.8.0` (class `BudgetOptimizer.optimize` and `_validate_budget`). `DataTensors` lives in `meridian.analysis.tensors`.

## Inspected `BudgetOptimizer.optimize` interface

```text
BudgetOptimizer(meridian | analyzer).optimize(
    new_data=None,                 # optional DataTensors
    use_posterior=True,
    selected_geos=None,
    selected_times=None,           # deprecated; use start_date/end_date
    start_date=None,               # inclusive yyyy-mm-dd
    end_date=None,                 # inclusive yyyy-mm-dd
    fixed_budget=True,
    budget=None,                   # center of spend box; historical default — PreM3 never uses that default
    pct_of_spend=None,             # n_paid_channels, sums to 1
    spend_constraint_lower=None,   # float or per-channel list in [0, 1]
    spend_constraint_upper=None,   # float or per-channel list, >= 0
    target_roi=None,               # flexible only; XOR target_mroi
    target_mroi=None,              # flexible only; XOR target_roi
    gtol=0.0001,
    use_optimal_frequency=True,
    max_frequency=None,
    use_kpi=False,                 # False => revenue; True => modeled KPI
    confidence_level=...,
    batch_size=...,
    optimization_grid=None,
) -> OptimizationResults
```

### Flexibility rules (native)

- `fixed_budget=True`: `target_roi` and `target_mroi` must be unset.
- `fixed_budget=False`: exactly one of `target_roi` or `target_mroi` is required. Both set is invalid.
- Native does **not** expose named `B_min` / `B_max`.
- `_validate_budget` also forbids passing `budget` when `fixed_budget=False`. Flexible total bounds are PreM3 feasibility + post-result hard checks, not a native kwarg.

### Spend-box semantics (native)

Channel spend bounds:

```text
lower_i = (1 - spend_constraint_lower_i) * budget * allocation_i
upper_i = (1 + spend_constraint_upper_i) * budget * allocation_i
```

Defaults: `0.3` for fixed budget, `1.0` for flexible (`spend_constraint_lower` must be in `[0, 1]`).

Native flexible search does not take a total `budget`. PreM3 compiles line min/max, locks, and movement to per-channel `spend_constraint_lower`/`upper` versus the approved mix (`pct_of_spend`). `B_min`/`B_max` are not sent as kwargs; they are proven in feasibility and re-checked on the result. If a hard line bound cannot be encoded with native `L_i` in `[0, 1]`, dispatch fails `FLEXIBLE_BUDGET_API_UNSUPPORTED`.

### `new_data` / `DataTensors` (native)

Optimizer docstring fields: `media`, `reach`, `frequency`, `media_spend`, `rf_spend`, `revenue_per_kpi`, `time`.

- `new_data.media` (or reach/frequency) overrides **flighting and** cost per media unit.
- `new_data.spend` / `media_spend` (or `rf_spend`) overrides **cost per media unit only**.
- `new_data.revenue_per_kpi` overrides unit value for revenue-mode optimization.
- Flighting pattern is held constant during optimization (does not depend on assigned channel budget).
- Adstock/carryover crosses `start_date`/`end_date`; PreM3 does not independently optimize quarters unless the accepted model contract permits decomposition.

### Output schema (native)

`OptimizationResults.optimized_data` / `nonoptimized_data` are `xarray.Dataset` with coordinate `channel` and variables including `spend`, `pct_of_spend`, `roi`, `mroi`, `cpik`, `incremental_outcome`, `effectiveness`. Attributes include `budget`, `fixed_budget`, `total_incremental_outcome`, `total_roi`, `total_cpik`.

PreM3 maps `spend` to `MODEL_RECOMMENDED` amounts. Outcome fields copy as `MODEL_ESTIMATE` only when present. ROI/mROI/ROMI are never fabricated.

## Objective modes

| Mode | Native call |
|---|---|
| `MAX_EXPECTED_OUTCOME_FIXED_BUDGET` | Existing P6-05 path: `fixed_budget=True`, pinned ±30% unless a constraint set compiles tighter channel bounds |
| `TARGET_ROI_FLEXIBLE_BUDGET` | `fixed_budget=False`, `target_roi`, `use_kpi` per governed conversion |
| `TARGET_MROI_FLEXIBLE_BUDGET` | `fixed_budget=False`, `target_mroi` |
| `MAX_INCREMENTAL_CONTRIBUTION_VALUE` | Revenue path (`use_kpi=False`) only when governed `revenue_per_kpi` or contribution margin exists |

Missing financial conversion: `FINANCIAL_VALUE_ASSUMPTION_REQUIRED`. Optimize original KPI and report cost per incremental KPI (`cpik` when native provides it).

## Fixed-budget compatibility

`NativeMeridianFixedBudgetAdapter.optimize_fixed_budget` remains `BudgetOptimizer.optimize(fixed_budget=True, ...)`. P6-05 tests that inspect that source stay valid. Advanced requests choose `FIXED` or `FLEXIBLE` explicitly.

## What P6-07 does not do

- Custom flexible-budget / group-sum solver
- Exposure/viewability/IVT/frequency constraints (P6-08)
- CVaR / efficient frontier (P6-09)
- Proposal approval (P6-06 reused)
- Provider budget writes
