# Optimization readiness

P6-04 proves whether a governed portfolio can be mapped into an accepted MMM for later optimization. P6-05 consumes a non-stale `OPTIMIZATION_READY` receipt and runs native Meridian `BudgetOptimizer` (fixed budget only).

```text
PortfolioSnapshotRef + transient PortfolioView
        ↓
accepted MMMModelVersion
        ↓
ModelConsumptionContract
        ↓
PortfolioModelMapping
        ↓
compatibility + causal coverage
        ↓
OptimizationInputContract (metadata)
        ↓
OptimizationReadinessReceipt
```

## Receipt status

`OPTIMIZATION_READY` · `NOT_READY` · `REVIEW_REQUIRED` · `NOT_CONFIGURED` · `STALE`

P6-00 values `REQUIRES_ACCEPTED_MMM` and `REQUIRES_SUPPORTED_MAPPING` remain on `OptimizationReadinessStatus` so existing execution-plan tests construct. Receipt *status* uses the set above.

## Required checks (all must pass for READY)

`APPROVED_PLAN_AVAILABLE` · `PORTFOLIO_SNAPSHOT_VALID` · `MODEL_ACCEPTED` · `MODEL_CONSUMPTION_CONTRACT_VALID` · `MODEL_OPTIMIZER_ARTIFACTS_AVAILABLE` · `MARKET_COMPATIBLE` · `CHANNEL_MAPPING_COMPLETE` · `PERIOD_COMPATIBLE` · `CURRENCY_COMPATIBLE` · `SPEND_SEMANTICS_COMPATIBLE` · `OPTIMIZABLE_VARIABLES_VALID` · `NO_UNRESOLVED_MAPPING_CONFLICTS` · `INPUT_CONTRACT_FINGERPRINTED`

## Portfolio states (V1 baseline = APPROVED_PLAN)

| Coverage | Outcome |
|---|---|
| `PLAN_ONLY` | may become ready |
| `PLAN_AND_ACTUALS` | may become ready |
| `ACTUALS_ONLY` | `APPROVED_PLAN_REQUIRED` / `NOT_READY` |
| `NEITHER` | `NOT_CONFIGURED` |

`ACTUAL_YTD` never replaces the approved baseline.

## Observation blockers (from P6-03)

Blockers: `CURRENCY_MISMATCH`, `PERIOD_MAPPING_REQUIRED`, `UNRESOLVED_MARKET`, `UNRESOLVED_CHANNEL`.

Informative, not V1 blockers: `ACTUAL_EXCEEDS_PLAN` and similar pacing observations.

## Staleness

The receipt is immutable. A new evaluation is required if portfolio, model, mapping, or `policy_version` (`p6-04/v1`) fingerprints change.

## Project Home

Generated status feeds existing `BUDGET_OPTIMIZATION`. No accepted model still returns `REQUIRES_ACCEPTED_MMM_MODEL`. After an accepted model, overlay may be `OPTIMIZATION_READY` / `NOT_READY` / `REVIEW_REQUIRED` / `NOT_CONFIGURED`, or P6-05 `OPTIMIZATION_RUNNING` / `OPTIMIZATION_COMPLETE` from the latest run. `STALE` is presented as `NOT_READY` with a stale reason. No new entitlement `CapabilityFamily`.
