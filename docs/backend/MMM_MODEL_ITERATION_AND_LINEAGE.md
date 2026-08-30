# MMM model iteration and lineage

Never mutate a failed ModelVersion in place.

## Successor

After a human identifiability `ModelDecision`:

- `model_version_id` is new
- `predecessor_model_version_id` / `supersedes_model_version_id` = v1
- `iteration_reason=MODEL_SPEC_IDENTIFIABILITY_ERROR`
- `source_fit_run_id` and `source_model_decision_id` are set

v1 remains immutable: `FAILED_PRE_FIT` / `ITERATION_REQUIRED`.

The user must later inspect:

- Model v1 `FAILED_PRE_FIT` identifiability
- Model v2 successor outcome

Do not rewrite history as though v1 never existed.

## Spec changes

The successor ModelPlan fingerprints the exact treatment set, controls, knots,
priors, window, geo scope, media/RF configuration, and runtime-compatible
options, and references the human ModelDecision.

- A: retain `music_center_promo`, human-approved `n_knots < n_time`
- B: drop `music_center_promo`, retain approved knot strategy, record
  `PROMOTION_NOT_EXPLICITLY_MODELED`
- C: new governed source → Data Foundation → new ModelReady fingerprint →
  successor version. The current ModelReady artifact is not mutated. If source
  work is required, stop with a Data Foundation work request.

Old FitApproval never authorizes the successor.

## Artifacts

Successor GCS objects use a new immutable version prefix. Never overwrite v1.

## MEL

Record a local modeling episode: condition, official failure, human decision,
successor configuration, successor outcome. Do not auto-promote it globally.
