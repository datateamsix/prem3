# MMM FINAL_MODEL runbook

Canonical production path only:

Cloud Tasks → OIDC → prem3-api internal launch → `prem3-meridian-model-worker`

Do not use a direct manual Cloud Run Job as the canonical final proof.

## Before enqueue

1. Human `ModelDecision` for identifiability (if iterating a failed spec)
2. Successor ModelVersion and fingerprinted ModelPlan
3. `MeridianPreFitValidationReceipt.status=PASS` on the exact ModelPlan
4. New prior-validation receipt bound to ModelVersion / ModelPlan / PriorSpec /
   ModelReady fingerprint
5. New `FitPlan` with `fit_purpose=FINAL_MODEL`
6. Human `FitApproval` bound to ModelVersion, ModelPlan, pre-fit, prior, and
   FitPlan fingerprints

Default MCMC remains 7 / 1000 / 500 / 1000 unless a human explicitly approves
another final plan. Do not reduce MCMC as a workaround.

CPU is valid for official final-model execution. GPU may accelerate. Do not
block analytical validity on GPU quota.

## Dispatch

Same approved fit → same canonical dispatch/task identity. A conflicting
FitPlan with the same idempotency key must fail.

The worker receives server-owned exact execution authority. It may not decide
knots, treatment removal, priors, MCMC reduction, geo scope, or model
acceptance. Request JSON is not authority.

## After the job

Reuse M3-03B failure semantics: `FAILED_PRE_FIT`, `FAILED_RUNTIME`,
`FAILED_POSTERIOR`, `FAILED_REVIEW`, or canonical success. Preserve where the
workflow actually stopped.

`RESOURCE_EXHAUSTED` / `TIMEOUT` route to a compute/runtime decision. Do not
mutate the ModelSpec to resolve infrastructure capacity.

If posterior succeeds: official Meridian serde save → immutable GCS → SHA-256 →
read back → official serde load. Then official ModelReviewer and Summarizer
with exact PASS / REVIEW / FAIL semantics.

A successful Cloud Run Job is not `MODEL_ACCEPTED`. Only an authorized human
records `ModelAcceptanceApproval`. Official FAIL and convergence FAIL block
acceptance. Official REVIEW requires human acknowledgment.

Until posterior exists: no ROI, mROI, incremental outcome, contribution,
response curves, or `MMMResultsSnapshot`.
