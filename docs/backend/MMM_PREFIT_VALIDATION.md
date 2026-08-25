# MMM official-runtime pre-fit validation

Catch invalid ModelSpec / model initialization with the real installed Meridian
runtime before expensive posterior sampling.

## Receipt

`MeridianPreFitValidationReceipt` binds:

- `model_version_id`
- `model_plan_fingerprint`
- `model_ready_fingerprint`
- runtime mode, Meridian / Python / TensorFlow versions
- `checks[]`
- `status=PASS|FAIL`

A changed ModelPlan invalidates the receipt. Stale reuse is forbidden.

## Gate

`MeridianPreFitValidationReceipt.status != PASS` blocks `FINAL_MODEL` FitApproval
and dispatch.

Pre-fit:

1. load the exact ModelReady input
2. construct `DataFrameInputDataBuilder` inputs
3. construct the exact successor ModelSpec
4. instantiate official Meridian
5. run `sample_prior` / compatibility path
6. confirm no pre-posterior exception

It must not run full posterior sampling.

## Early warning vs official authority

`GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS` may warn when a geo-invariant
non-media treatment is paired with `n_knots = n_time`. That warning is not
official Meridian compatibility authority. Official runtime still decides.

## Workflow

Model Design → official-runtime pre-fit → human FitApproval → expensive posterior.

Do not spend a full Cloud Run posterior job discovering a condition official
Meridian can reject during initialization.
