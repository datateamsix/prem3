# Optimization run lifecycle

P6-05 executes native Meridian fixed-budget optimization from a non-stale `OptimizationReadinessReceipt`.

```text
OPTIMIZATION_READY receipt
        ↓ revalidate fingerprints
APPROVED_PLAN transient PortfolioView
        ↓ OptimizerBudgetVector (in-memory)
BudgetOptimizer.optimize(fixed_budget=True)
        ↓ validate + Decimal reconcile
Firestore OptimizationRun metadata
        + immutable GCS artifact
        ↓ read-back verify
OPTIMIZATION_COMPLETE / MODEL_RECOMMENDED
        ↓ P6-06 proposal seam (not this mission)
```

## Status

`CREATED` · `QUEUED` · `DISPATCHED` · `RUNNING` · `VALIDATING` · `READBACK` · `COMPLETE` · `FAILED` · `STALE_REFUSED`

Running overlay statuses (`CREATED` through `READBACK`) surface as Home `OPTIMIZATION_RUNNING`. `COMPLETE` surfaces as `OPTIMIZATION_COMPLETE`. No accepted model still `REQUIRES_ACCEPTED_MMM_MODEL`.

## Identity

- Run: `orun_`
- Result ref: `ores_`
- Execution key: fingerprints of receipt, mapping, input contract, model, plan version, and pinned optimizer defaults
- Rerun always mints a new `optimization_run_id` and a new GCS object
- Optional `is_current` on `OptimizationResultRef` points at the latest **completed** result, not an approved recommendation

## Failure classes

Not-ready / review-required / stale receipts fail before a completed run. After dispatch: `MODEL_ARTIFACT_UNAVAILABLE`, `NATIVE_OPTIMIZER_FAILED`, `OPTIMIZER_RESULT_INVALID`, `OPTIMIZER_BUDGET_INVARIANT_FAILED`, `RESULT_READBACK_FAILED`. Retry semantics are `NOT_RETRYABLE`, `IDEMPOTENT_RETRY`, or `NEW_RUN_REQUIRED`.
