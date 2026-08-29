# MTA Model Sensitivity

Policy version: `mta_sensitivity_policy_v1`.

Dispersion = `max_share − min_share` across completed models with `AVAILABLE` share.

| Label | Threshold |
|---|---|
| `LOW` | < 0.05 |
| `MODERATE` | 0.05–0.15 |
| `HIGH` | 0.15–0.30 |
| `VERY_HIGH` | ≥ 0.30 |

This range is model-assumption disagreement. It is not a confidence interval
and not posterior uncertainty.

Frontend model filters (`?models=`) change only the response view. They do not
mutate the snapshot, delete stored model evidence, or rerun attribution.
