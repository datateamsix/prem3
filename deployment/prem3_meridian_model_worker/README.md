# prem3-meridian-model-worker

Dedicated Cloud Run Job image for approved Meridian posterior sampling.

## Pin

- `google-meridian[and-cuda,schema]==1.8.0`
- Python 3.12 (EDA-worker family; prem3-api remains 3.13)
- TensorFlow family comes from the pinned Meridian release
- The `[and-cuda]` extra installs `tensorflow[and-cuda]` so Cloud Run L4 GPUs
  are visible to TensorFlow. The CPU-only `google-meridian==1.8.0` pin does
  **not** enable GPU acceleration.
- The `[schema]` extra installs `mmm-proto-schema`, required by official
  `meridian.schema.serde`. Without it, `save_meridian` / `load_meridian` cannot
  import.

This image must not install `google-adk` and must not execute generated Python.

## Modes

| Arg / `PREM3_MMM_WORKER_MODE` | Purpose |
|---|---|
| `import-smoke` | Prove Meridian 1.8.0 imports and official classes |
| `cpu-smoke` | Tiny official `sample_prior` / `sample_posterior` / serde / reviewer / summarizer |
| `gpu-detect` | Require TensorFlow GPU devices (`PREM3_REQUIRE_GPU=false` for CPU hosts) |
| default | Restore `PREM3_MMM_FIT_DISPATCH_ID` from Firestore and execute the approved FitPlan |

FitPlan and FitRun bind the immutable image digest (`PREM3_WORKER_IMAGE_DIGEST`), never a floating tag.

## Deploy

```text
python scripts/provision_meridian_fit_dispatch_cloud.py --execute
python scripts/deploy_meridian_model_worker.py --execute
```

L4 qualification profile: 1 GPU, 4 CPU, 16Gi, zonal redundancy disabled, parallelism 1, max retries 0.

Service account: reuse `m3-runtime@modelready-m3.iam.gserviceaccount.com` (same GCS/Firestore/BQ/logging grant as the evaluation worker). No keys.
