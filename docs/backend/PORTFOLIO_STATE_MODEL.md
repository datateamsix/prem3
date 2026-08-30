# Portfolio state model

Server-owned `PortfolioCoverageState`. The frontend does not infer state.

| Approved plan | Governed actuals | State | Baseline |
|---|---|---|---|
| no | no | `NEITHER` | none |
| yes | no | `PLAN_ONLY` | `APPROVED_PLAN` |
| yes | yes | `PLAN_AND_ACTUALS` | `APPROVED_PLAN` |
| no | yes | `ACTUALS_ONLY` | `ACTUAL_YTD` |

`GOVERNED_ACTUALS` remains in `ACTUAL_SPEND_BASELINES` so actuals still fail `actual_spend_is_not_approved_budget`. It is not the `ACTUALS_ONLY` baseline.

## Measures

- `remaining = approved - actual` when both known
- `variance = actual - approved` when both known
- `variance_percent = (actual - plan) / plan` only when plan is known and non-zero
- Missing inputs stay `missing=True`; they are never zero-filled

`ACTUALS_ONLY` returns actual rollups only. Approved, remaining, and variance are unavailable, not zero.

Outage with an approved plan stays `PLAN_ONLY` and emits `MISSING_ACTUALS_SOURCE` / unavailable provenance. Actuals are not zero-filled.

Amounts are `Decimal` with `ROUND_HALF_EVEN` to two places. Snapshot fingerprint includes the actuals source fingerprint and as-of. A new fingerprint creates a new `PortfolioSnapshotRef`; old refs are not mutated.
