# Optimization result contract

Recommended amounts are **not** an approved plan. They are a model output.

## Labels

| Kind | Meaning |
|---|---|
| `MODEL_RECOMMENDED` | Quantized Meridian spend after budget reconcile |
| `MODEL_ESTIMATE` | Optional outcome fields (`roi`, `mroi`, `incremental_outcome`, …) copied only when `OptimizationResults` exposes them |

Never `APPROVED_PLAN`. Approval of a recommendation is P6-06.

## Firestore (`OptimizationResultRef`)

Metadata only: result id, run id, tenant/project, GCS bucket/object/generation, result fingerprint, schema version, runtime `1.8.0`, `is_current`. No allocation arrays.

## GCS artifact (`optimization_result_{run_id}`)

Immutable (`if_generation_match=0`). Schema version `p6-05/v1`. Rows carry Decimal strings for baseline, recommended, absolute change, and optional percent change (`null` + `percent_change_unavailable` when baseline is 0). Fingerprint is over the body excluding the fingerprint field.

## Private HTTP

`GET .../optimizations/{optimization_run_id}/result` is amount-bearing and `Cache-Control: private, no-store`. Incomplete runs do not return a result.
