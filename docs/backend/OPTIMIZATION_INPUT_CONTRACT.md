# Optimization input contract

`OptimizationInputContract` is Planning metadata that pins *how* P6-05 will re-resolve approved amounts. It does not store the total budget.

## What is stored

- `optimization_input_id` (`oinc_`)
- tenant / project (server-owned)
- `portfolio_snapshot_id`, `model_version_id`, `mapping_id`
- `baseline_kind=APPROVED_PLAN`
- period bounds, currency
- optimizable / fixed / excluded variable IDs
- plan / Drive refs and fingerprints
- `budget_resolution_path=APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`
- issues, status, fingerprint

Firestore collection: `optimization_input_contracts`. Class: `CONTROL_PLANE_METADATA`.

## What is not stored

Budget arrays, Decimal amounts, recommended allocations, spend vectors, or optimizer payloads. Store `put` raises `PersistenceBarrierError` if any field looks like an amount.

## Resolution path for P6-05

1. Authorized Drive plan bytes
2. Transient `PortfolioView` for the selected fiscal period
3. Mapping + consumption contract already pinned on this input

The fingerprint is content-addressed over snapshot, model, mapping content, period, currency, and variable sets. Generated resource IDs are not part of the fingerprint so equivalent authority hashes identically.
