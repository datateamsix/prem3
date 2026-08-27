# Native Meridian fixed-budget optimization

P6-05 executes official Meridian `BudgetOptimizer` for **fixed-budget** allocation. Flexible budget and CVaR remain unimplemented. Planning min/max constraint objects are P6-07 and are not used here.

## Installed runtime (required discovery)

Pinned package: `google-meridian==1.8.0` (`meridian.version.__version__ == "1.8.0"`).

### `BudgetOptimizer.optimize`

Module: `meridian.analysis.optimizer`

```text
BudgetOptimizer(meridian | analyzer).optimize(
    new_data=None,
    use_posterior=True,
    selected_geos=None,
    selected_times=None,          # deprecated
    start_date=None,
    end_date=None,
    fixed_budget=True,
    budget=None,                  # None => historical spend; PreM3 never uses that default
    pct_of_spend=None,            # None => historical mix; PreM3 passes approved-plan shares
    spend_constraint_lower=None,  # PreM3 pins 0.3
    spend_constraint_upper=None,  # PreM3 pins 0.3
    target_roi=None,              # flexible-budget only; unused
    target_mroi=None,             # flexible-budget only; unused
    gtol=0.0001,                  # PreM3 pins 0.0001
    use_optimal_frequency=True,
    max_frequency=None,
    use_kpi=False,
    confidence_level=...,
    batch_size=...,
    optimization_grid=None,
) -> OptimizationResults
```

P6-05 call: `use_posterior=True`, `fixed_budget=True`, explicit `budget=<float from approved plan>`, `pct_of_spend=<approved-plan shares>`, `spend_constraint_lower=0.3`, `spend_constraint_upper=0.3`, `gtol=0.0001`.

### `OptimizationResults`

Dataclass with `optimized_data` / `nonoptimized_data` as `xarray.Dataset`:

- Coordinates: `channel`
- Data variables: `spend`, `pct_of_spend`, `roi`, `mroi`, `cpik`, `incremental_outcome`, `effectiveness`
- Attributes include `budget`, `fixed_budget`, `total_incremental_outcome`, `total_roi`, `total_cpik`

PreM3 maps `spend` to recommended amounts. Outcome fields are copied as `MODEL_ESTIMATE` only when present. Missing outcome fields are omitted, not invented.

### Load path

```python
from meridian.schema.serde import meridian_serde
model = meridian_serde.load_meridian(path)
```

`load_meridian` accepts `.binpb` / `.txtpb` / `.textproto`. Importing `meridian.schema.serde` requires the `[schema]` extra (`mmm` proto package). The fit worker image already installs `google-meridian[and-cuda,schema]==1.8.0`. A second Cloud Run Job for this optimizer worker is a `SHARED_MERIDIAN_WORKER_CHANGE_REQUEST`; this mission does not change `execute_approved_fit`.

If `BudgetOptimizer` itself cannot be imported, stop with `MERIDIAN_OPTIMIZER_API_REVIEW_REQUIRED`. Discovery on this worktree found the class and signature; implementation proceeds.

## What P6-05 does not do

- Historical-spend default `budget`
- Flexible budget / CVaR / frontier
- P6-07 Planning min/max constraint sets
- Drive plan mutation or proposal approval (P6-06). P6-06 now owns scenario/proposal governance and plan-revision drafts.
- Production BigQuery actuals (`P6_03_PRODUCTION_ACTUALS_QUERY_PENDING` stays fail-closed)
