# MMM GPU execution runtime

## Path

```text
API
    ↓
dispatch record
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

## Worker image

`deployment/prem3_meridian_model_worker/`

Pin: `google-meridian==1.8.0`, Python 3.12 (EDA-worker family; prem3-api remains
3.13), TensorFlow family resolved by the pinned Meridian release.

Receipts record `python_version`, `meridian_version`, `tensorflow_version`,
`worker_image_digest`.

## Worker authority

The worker restores trusted SERVICE `TenantContext`, Project, Cycle, Track,
ModelVersion, and FitPlan from durable **server-owned** state.

Never accepted as agent/user authority: tenant, project, storage path, BigQuery
destination, Cloud Run job name, service account, container image, arbitrary
Python.

Known path: load approved model-ready input → verify fingerprint → build
InputData from pinned mapping → compile approved PriorDistribution + ModelSpec →
`Meridian.sample_posterior(exact FitPlan)` → serde save → official ModelReviewer
→ official summary → typed receipts. No generated script execution.

If the artifact no longer matches the ModelReady fingerprint:
`STALE_INPUT` / `CONTRACT_MISMATCH`. Return to Pre-Modeling/Foundation. Do not
repair data inside modeling.

## Compute profiles

Server-owned only: `CPU_TEST`, `GPU_STANDARD`, `GPU_LARGE`.

Initial production preference: `GPU_STANDARD` on L4 where qualified. Agents and
users cannot request arbitrary accelerators.

CI remains CPU-based with tiny fixtures (`FakeMeridianRuntime`). Tiny draws prove
execution compatibility only, not statistical adequacy.

## Safeguards

- Entitlement checks on MMM modeling
- Max concurrent fits: 1 per Project, 2 per tenant
- Approved compute profiles only
- Idempotent POST fit against the exact approved FitPlan
- Concurrent duplicates launch one fit
- Job timeout and cost/resource metadata are server-controlled

Safe cancellation via the current execution adapter is **P1** if not yet
supported by the Cloud Tasks / Cloud Run Job adapter.

## Live proof

Authorized L4 qualification (worker start, GPU visible, Meridian import, tiny
prior + posterior, serde, reviewer, artifact verification) is runtime proof, not
statistical adequacy.

Until that job is run: `LIVE_GPU_PROOF_BLOCKED` after an attempted
`gcloud run jobs describe prem3-meridian-model-worker --region=us-central1`.
Current blocker: the job does not exist in `modelready-m3` / `us-central1`
(only `meridian-eda-worker` and `prem3-evaluation-worker` are listed).
Do not report `NOT_RUN` merely because the adapter stopped before an attempt.
