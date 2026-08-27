# Portfolio observations

`PortfolioObservation` is a deterministic finding. It is not a recommendation, decision, or optimizer output. Gemini may explain an observation later; it does not own the truth state.

## Stored fields

type, severity (`INFO` / `REVIEW` / `WARNING` / `ERROR`), optional cell refs (`market_id`, `channel_id`, period), snapshot fingerprint, `message_key`.

No amount arrays in Firestore. Structured comparison state is enough.

## Types implemented in P6-03

| Type | Trigger |
|---|---|
| `ACTUAL_EXCEEDS_PLAN` | plan and actual known and actual > plan |
| `ACTUAL_BELOW_PLAN` | plan and actual known and actual < plan |
| `ACTUAL_WITHOUT_PLAN` | actual known, plan missing (valid in `ACTUALS_ONLY` and unmatched cells) |
| `PLAN_WITHOUT_ACTUALS` | plan cell known, actual missing, and a source *is* configured |
| `MISSING_ACTUALS_SOURCE` | source not configured or query unavailable |
| `STALE_ACTUALS_SOURCE` | freshness `STALE` / `REVIEW_REQUIRED` |
| `MEASUREMENT_COVERAGE_MISSING` | no MMM/MTA/experiment/brand/exposure ref |
| `MEASUREMENT_COVERAGE_PARTIAL` | coverage status `PARTIAL` |

`UNRESOLVED_MARKET`, `UNRESOLVED_CHANNEL`, `CURRENCY_MISMATCH`, and `PERIOD_MAPPING_REQUIRED` fail closed as Planning errors rather than silent observations.

Observations never mutate the approved Investment Plan or Drive plan bytes.
