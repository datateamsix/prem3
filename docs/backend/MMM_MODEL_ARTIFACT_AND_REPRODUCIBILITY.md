# MMM model artifact and reproducibility

## Binary model

Canonical binary: `meridian_model.binpb`

Saved with current official `meridian.schema.serde.meridian_serde.save_meridian`.
Deprecated save APIs are not used. Storage is customer-owned GCS under
**server-resolved** versioned paths. Requests never accept raw paths.

`MeridianModelArtifactManifest` records `model_version_id`, `fit_run_id`,
Meridian version, worker image digest, input manifest ref + fingerprint,
model-plan and fit-plan fingerprints, binary ref, SHA-256, and created_at.

Read-back hash mismatch blocks completion. Fitted versions are immutable.
Iteration creates a new version; the predecessor binary is unchanged.

Binary models are **not** duplicated into Firestore. Firestore holds control-plane
metadata only.

## BigQuery ledger

Customer BigQuery holds queryable metadata/summary artifacts, not the binary:

- `mmm_model_versions`
- `mmm_fit_runs`
- `mmm_model_decisions`
- `mmm_model_health`
- `mmm_model_channel_summary`

Writes are versioned/run-scoped and must be read-back verified. Mission 3 ships
the typed table set and an in-memory ledger; live customer-project writes follow
the GPU execution qualification.

## Official review artifacts

Worker runs `reviewer.ModelReviewer` (convergence first, then Baseline,
BayesianPPP, GoodnessOfFit, PriorPosteriorShift, ROIConsistency when
appropriate) and persists exact official status `PASS` / `REVIEW` / `FAIL`.

`summarizer.Summarizer` produces `results_summary.html` (or current official
equivalent) plus structured values. Requested and effective result date ranges
are recorded. No silent clipping policy. HTML is presentation; typed results are
authoritative.

## Reproducibility

`MMMReproducibilityManifest` binds Project, Cycle, Track, BusinessProfile
snapshot, ModelReady manifest, ModelPlan, decision IDs, Meridian version,
external knowledge asset versions, worker image digest, fit configuration,
model artifact hash, review artifacts, and acceptance approval.

ModelPlan fingerprint covers at least: MODEL_READY input fingerprint, model
window, semantic mappings, ModelSpec, PriorSpec, MCMC plan, Meridian runtime
version.

## Receipts

Design, Decision, Prior Validation, Fit Approval, Fit, Health, Review, and
Acceptance receipts are concise proof, not raw logs. MEL may record them as
evidence and may not mutate an active plan.
