# MMM Result Authority and Provenance (M4-00)

## Authority classes

| Class | Owner | May authorize investment action? |
|---|---|---|
| `VERIFIED` | Official Meridian / deterministic typed evidence | No — evidence only |
| `INTERPRETATION` | PreM3 | No |
| `RECOMMENDATION` | PreM3 advisor (accepted models only by default) | Advisory only |
| `DECISION_REQUIRED` | Human | Yes — human governs |

Meridian calculates. PreM3 interprets. PreM3 may recommend. Humans decide.

## Missing vs zero vs invalid

| State | Meaning |
|---|---|
| `NOT_AVAILABLE` | Official API did not produce a value |
| `ZERO` | Finite numeric zero |
| `VALUE` | Finite non-zero |
| `INVALID` | NaN/Inf or failed interval ordering |

Never coerce missing/invalid to zero.

## Provenance (mandatory)

Every snapshot resolves to:

- ModelReady fingerprint
- BusinessProfile snapshot id
- Data Foundation fingerprint
- ModelPlan fingerprint
- ModelDecision ids
- FitPlan fingerprint
- FitApproval id
- FitRun id
- model artifact SHA-256
- review pack fingerprint
- Analyzer source methods

Result fingerprint binds at minimum:

`model_artifact_sha256`, `model_version_id`, `fit_run_id`,
`adapter_version`, `meridian_version`, `metric_extraction_policy_version`.

## Latest vs accepted

- `latest_result_snapshot_id` — most recent extracted fit
- `accepted_result_snapshot_id` — current accepted evidence for downstream planning

Unaccepted latest must never replace accepted current.

## Historical immutability

A snapshot binds one ModelVersion + FitRun + artifact SHA + extraction policy.
New fits create new snapshots. Prior-cycle evidence is never rewritten.
