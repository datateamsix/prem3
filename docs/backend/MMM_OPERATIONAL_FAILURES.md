# MMM operational failures

Worker and API modeling failures are classified. There is no silent fake
fallback onto `FakeMeridianRuntime` or `RecordingMeridianLibrary`.

| Class | Stage |
|---|---|
| `MERIDIAN_IMPORT_FAILED` | Worker import / `InstalledMeridianLibrary.load` |
| `GPU_NOT_VISIBLE` | TensorFlow listed no GPU devices when GPU was required |
| `INPUT_CONTRACT_MISMATCH` | ModelReady fingerprint, mapping, or EDA spec promotion |
| `PRIOR_VALIDATION_FAILED` | Official `sample_prior` |
| `FIT_RUNTIME_ERROR` | Official `sample_posterior` or worker restore |
| `RESOURCE_EXHAUSTED` | Memory, GPU, or concurrent-fit cap |
| `SERDE_ERROR` | Official `save_meridian` / `load_meridian` |
| `MODEL_REVIEW_FAILED` | Official ModelReviewer FAIL/missing checks |
| `GCS_PERSISTENCE_FAILED` | Artifact write/read/hash or immutable overwrite |
| `FIRESTORE_PERSISTENCE_FAILED` | Control-plane modeling documents |
| `BQ_LEDGER_FAILED` | Measurement Home write or read-back |

Structured logs should include `fit_run_id`, `model_version_id`, `cycle_id`,
`track_id`, `runtime_mode`, `fit_purpose`, worker image digest, Meridian
version, stage, duration, and `failure_class`. Do not log raw customer rows,
OAuth tokens, or credentials.

A Cloud Run infrastructure retry must not create a second canonical FitRun.
Job `max-retries` starts at 0 for qualification.

## Live GPU deploy

`LIVE_GPU_DEPLOY_BLOCKED` on 2026-08-24: L4 without zonal redundancy has no
project quota; L4 with zonal redundancy is not offered for Cloud Run Jobs.
CPU fallback job exists. Classify empty TensorFlow GPU lists as
`GPU_NOT_VISIBLE` when GPU is required.

