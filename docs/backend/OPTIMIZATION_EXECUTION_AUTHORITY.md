# Optimization execution authority

Execution is not proposal approval.

## Who may dispatch

Authenticated human POST (`require_human_approver`). Service accounts cannot dispatch. Entitlement: `Feature.BUDGET_OPTIMIZATION`. Readiness: `OPTIMIZATION_READY` after dispatch-time fingerprint revalidation.

## What the client may send

`readiness_receipt_id` and optional `idempotency_key`. Tenant, GCS/BQ/Drive/model paths, budget arrays, and variable maps are rejected.

## What is never mutated

- `MMMModelVersion` / FitPlan / acceptance
- Customer Drive plan bytes
- Production BigQuery actuals (P6-03A retrieves them; they are not mutated here and are not the fixed budget)

## Budget authority

`OptimizationInputContract.budget_resolution_path = APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`. Drive plan → transient `PortfolioView` → selected fiscal period. Actuals and MTA are not the fixed budget.

## Worker

`app/tools/meridian_optimizer_worker.py` reconstructs from `optimization_run_id` only. Untrusted request keys (`tenant_id`, `storage_path`, `model_path`, `budget_array`, container/image fields) are rejected. This process does not call `execute_approved_fit`.
