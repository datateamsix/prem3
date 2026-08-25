# MMM Results Architecture (M4-00)

PreM3 converts official Meridian model output into typed, durable investment
evidence. This document describes the post-fit results boundary.

## Pipeline

```
Completed FitRun + model artifact SHA
        ↓
Meridian180ResultsAdapter (google-meridian==1.8.0)
        ↓
typed MMMResultsSnapshot
        ↓
GCS compact JSON + BigQuery prem3_modeling ledger + Firestore pointers
        ↓
MMMDecisionIntelligenceBrief (separate contract)
        ↓
frontend-ready GET read models
```

## Package

`app/modeling/mmm/results/`

- `contracts.py` — frozen result + advisor models
- `adapter_meridian_180.py` — version-specific Analyzer extraction
- `validation.py` — VALUE / ZERO / NOT_AVAILABLE / INVALID
- `builder.py` — raw → snapshot
- `store.py` — idempotent extract + pointers
- `ledger.py` — BigQuery result tables
- `intelligence.py` — Decision Intelligence compiler
- `read_models.py` — API presentation
- `fixtures.py` — clearly labeled synthetic fixtures

## Meridian 1.8.0 methods used

| Method | Metric |
|---|---|
| `Analyzer.roi` | ROI |
| `Analyzer.incremental_outcome` | Incremental outcome |
| `Analyzer.marginal_roi` | Marginal ROI |
| `Analyzer.summary_metrics` | `pct_of_contribution`, spend, intervals |
| `Analyzer.response_curves` | Response curve points |
| `Analyzer.get_historical_spend` | Spend fallback |

Unsupported / unused:

- `Analyzer.contribution()` — **not** a public 1.8.0 method
- `BudgetOptimizer` / Scenario Planner — out of scope for M4-00

Missing official methods → `availability=NOT_AVAILABLE`, value `null`.
No fabrication.

## Status

`MMMResultStatus`: `NOT_AVAILABLE` | `FIT_COMPLETE_REVIEW_PENDING` |
`REVIEWED_NOT_ACCEPTED` | `ACCEPTED` | `SUPERSEDED`

Eligibility: `PRE_ACCEPTANCE_RESULTS` vs `ACCEPTED_MODEL_RESULTS`.

## Persistence

| Store | Content |
|---|---|
| Firestore | Compact metadata + latest/accepted pointers only |
| GCS | `mmm_results_snapshot.json`, channel JSON, brief JSON |
| BigQuery `prem3_modeling` | `mmm_result_snapshots`, `mmm_channel_results`, `mmm_response_curve_points`, fit evidence, limitations, DI findings |

Views (contract): `mmm_results_latest_fit`, `mmm_results_current_accepted`.

## Music Center

Until a real posterior completes: `status=NOT_AVAILABLE`,
`reason=FIT_NOT_COMPLETE`. Synthetic fixtures are never production proof.
