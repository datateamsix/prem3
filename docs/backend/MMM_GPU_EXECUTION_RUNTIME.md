# MMM GPU execution runtime

## Path

```text
API
    ↓
FitApproval verification
    ↓
canonical FitDispatch
    ↓
Cloud Tasks
    ↓
Cloud Run Job (prem3-meridian-model-worker)
    ↓
known worker (serde + ModelReviewer + Summarizer)
    ↓
typed artifacts / receipts
```

Fitting is outside `prem3-api`. Cloud Run Jobs with GPU are the preferred first
production fit path. A later Vertex AI CustomJob adapter may implement the same
execution interface; Vertex is not added in Mission 3 for architecture elegance.

Direct `gcloud run jobs execute` is infrastructure smoke only. Production
orchestration is Cloud Tasks → internal launch → Cloud Run Job.

## Worker image

`deployment/prem3_meridian_model_worker/`

Pin: `google-meridian[and-cuda,schema]==1.8.0`, Python 3.12 (EDA-worker family;
prem3-api remains 3.13).

Official Meridian Linux GPU install uses the CUDA extra, which pulls
`tensorflow[and-cuda]<2.22,>=2.21.0`. The CPU-only `google-meridian==1.8.0`
wheel does not enable GPU acceleration even if Cloud Run attaches an L4.

Official serde (`meridian.schema.serde`) requires the `schema` extra
(`mmm-proto-schema`). Image import smoke failed closed without it.

Receipts record `python_version`, `meridian_version`, `tensorflow_version`,
`worker_image_digest`. FitPlan/FitRun bind the digest, not a floating tag.

## Worker authority

The worker restores trusted SERVICE `TenantContext`, Project, Cycle, Track,
ModelVersion, and FitPlan from durable **server-owned** state.

Never accepted as agent/user authority: tenant, project, storage path, BigQuery
destination, Cloud Run job name, service account, container image, arbitrary
Python, CPU, memory, GPU, region.

Known path: load approved model-ready input → verify fingerprint → build
InputData from pinned mapping → compile approved PriorDistribution + ModelSpec →
`Meridian.sample_posterior(exact FitPlan)` → serde save → official ModelReviewer
→ official summary → typed receipts. No generated script execution.

If the artifact no longer matches the ModelReady fingerprint:
`STALE_INPUT` / `CONTRACT_MISMATCH`. Return to Pre-Modeling/Foundation. Do not
repair data inside modeling.

## Compute profiles

Server-owned only: `CPU_TEST`, `GPU_STANDARD`, `GPU_LARGE`.

Initial qualification profile for L4: 1 GPU, 4 CPU, 16 GiB, GPU zonal redundancy
disabled, parallelism 1. Do not silently increase compute after a failed fit.

Agents and users cannot request arbitrary accelerators.

CI remains CPU-based with tiny fixtures (`FakeMeridianRuntime`). Tiny draws prove
execution compatibility only, not statistical adequacy.

## Fit purpose

| FitPurpose | Meaning |
|---|---|
| `RUNTIME_QUALIFICATION` | Infrastructure/API proof. Not eligible for `MODEL_ACCEPTED`. |
| `MODEL_ITERATION` | Real modeling evidence. Not automatically final. |
| `FINAL_MODEL` | Exact approved production configuration. Eligible for review/acceptance. |

Official MCMC guidance (`n_chains=7`, `n_adapt=1000`, `n_burnin=500`,
`n_keep=1000`) is a recommendation bound into a FitPlan after human approval.

## Safeguards

- Entitlement checks on MMM modeling
- Max concurrent fits: 1 per Project, 2 per tenant
- Approved compute profiles only
- Idempotent POST fit against the exact approved FitPlan
- Concurrent duplicates launch one fit
- Job timeout and cost/resource metadata are server-controlled
- Cloud Run `max-retries=0` so infrastructure retry cannot mint a second FitRun

Safe cancellation via the current execution adapter is **P1**.

## Live GPU deploy attempt (2026-08-24)

Attempted `gcloud run jobs deploy prem3-meridian-model-worker` in
`modelready-m3` / `us-central1` with `--gpu=1 --gpu-type=nvidia-l4 --cpu=4
--memory=16Gi`.

1. `--no-gpu-zonal-redundancy` → `spec.template.spec.parallelism: You do not
   have quota for using GPUs without zonal redundancy.` Quota ID
   `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`. Increase eligibility:
   `NOT_ENOUGH_USAGE_HISTORY`.
2. `--gpu-zonal-redundancy` → `Currently Cloud Run jobs are unable to offer GPU
   enabled instances with zonal redundancy due to capacity limitations.`

CPU-only job `prem3-meridian-model-worker` was then created (4 CPU / 16Gi /
timeout 3600s / parallelism 1 / max-retries 0) on digest
`sha256:e4bda7be5bb6ec92dc1576d076f7800745c0c16e071e0d74964d65dfb25a930e`.

GPU-detect execution `prem3-meridian-model-worker-zxl49` (CPU job,
`PREM3_REQUIRE_GPU=false`): Meridian 1.8.0 imports; TensorFlow GPU devices
`[]`; `cuInit` UNKNOWN ERROR (303). This is not GPU proof.

Do not relabel this CPU job as OFFICIAL_GPU.

GPU remains preferred production compute. `MODEL_ACCEPTED` requires
`OFFICIAL_MERIDIAN_RUNTIME` (`OFFICIAL_CPU` or `OFFICIAL_GPU`) plus
`fit_purpose=FINAL_MODEL`, not GPU hardware.

