# MMM live proof runbook

Reproduce Mission 3 qualification without chat history. Primary project:
`modelready-m3`, region `us-central1`. Do not deploy over historical
`modelready-m3` or `meridian-eda-worker`.

Keep three artifacts separate:

- `evaluation/meridian_official_cpu_smoke.json`
- `evaluation/meridian_cloud_runtime_qualification.json`
- Music Center final fit (OFFICIAL_CPU or OFFICIAL_GPU + FINAL_MODEL + human acceptance)

## 0. Lineage

- M3-00: `e6fc551273f940571f5ce2bb371c83f7a1685506`
- M3-01: `3204c3d9957560c60ae2d27bc1cf2037953123a6`
- M3-02: `981642e9e64b5657c0573de97173e4d535479d7b`
- Branch: `feature/prem3-m3-meridian-modeling-runtime`
- Parent until merge: PR 18 `feature/prem3-project-architecture-enablement`
- Restack required after PR 18 merges onto `main`

## 1. Unit / FAKE_TEST

```text
py -3.13 -m ruff check app tests scripts
py -3.13 -m pytest tests/unit
py -3.13 scripts/export_contracts.py
py -3.13 scripts/export_openapi.py
```

Ordinary CI must not require a GPU or `google-meridian`.

## 2. Build the exact worker image

No local Docker is required. Cloud Build uses the Dockerfile.

```text
py -3.13 scripts/deploy_meridian_model_worker.py --execute
```

Pin: `google-meridian[and-cuda,schema]==1.8.0`. `[and-cuda]` pulls
`tensorflow[and-cuda]<2.22,>=2.21.0`. `[schema]` is required for official serde.

Record: source SHA, image URI, digest, Python, Meridian, TensorFlow.

If Cloud Build smoke fails, stop. Do not deploy a known-broken image.

Proven digest (M3-02 working tree):

`us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/prem3-meridian-model-worker@sha256:e4bda7be5bb6ec92dc1576d076f7800745c0c16e071e0d74964d65dfb25a930e`

## 3. GPU vs CPU deploy

Preferred:

```text
gcloud run jobs deploy prem3-meridian-model-worker \
  --project=modelready-m3 --region=us-central1 \
  --image=IMAGE_DIGEST_URI \
  --service-account=m3-runtime@modelready-m3.iam.gserviceaccount.com \
  --tasks=1 --parallelism=1 --task-timeout=3600 --max-retries=0 \
  --cpu=4 --memory=16Gi --gpu=1 --gpu-type=nvidia-l4 \
  --no-gpu-zonal-redundancy
```

Observed 2026-08-24:

- No zonal redundancy: no quota (`NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`)
- With zonal redundancy: Cloud Run Jobs cannot offer GPU zonal redundancy (capacity)

Then deploy CPU-only with the same digest (4 CPU / 16Gi). Do not relabel CPU as GPU.

## 4. GPU detection

```text
gcloud run jobs execute prem3-meridian-model-worker \
  --region=us-central1 --project=modelready-m3 \
  --args=gpu-detect --update-env-vars=PREM3_REQUIRE_GPU=false --wait
```

On a CPU job, TensorFlow GPU devices may be empty. Music Center posterior
sampling must not start until a GPU job lists at least one device.

## 5. Dispatch path

```text
py -3.13 scripts/provision_meridian_fit_dispatch_cloud.py --execute
```

Identities reused: `m3-runtime@...` (worker) and
`prem3-evaluation-dispatcher@...` (Cloud Tasks OIDC). Roles:
`roles/cloudtasks.enqueuer`, `roles/iam.serviceAccountUser`,
`roles/run.jobsExecutorWithOverrides`. No keys.

Production path is API → FitApproval → FitDispatch → Cloud Tasks →
`POST /internal/v1/mmm-fit-dispatches/{dispatch_id}/launch` → Cloud Run Job.

Live `prem3-api` (Mission 10 revision) currently 404s that route. Do not
overwrite the live API unless an operator explicitly deploys an M3 revision.

```text
py -3.13 scripts/qualify_mmm_live_cloud.py --execute
```

That script proves live Firestore round-trip + new-process reload +
cross-tenant denial, GCS hash + immutable overwrite reject, BigQuery ledger
write/read-back + history, and Cloud Tasks duplicate-name `AlreadyExists`.

Duplicate identical fit requests must return the same FitRun. Firestore
`claim_canonical_dispatch` is the authority, not an in-process lock.

## 6. Human acceptance

Do not self-approve as `m3-runtime@...gserviceaccount.com`.
Stop at `AWAITING_MODEL_REVIEW` or `AWAITING_MODEL_ACCEPTANCE` until an
authorized human member accepts the exact artifact, review pack, fit run, and
ModelPlan fingerprints.

`MODEL_ACCEPTED` also requires `FitPurpose.FINAL_MODEL` and
`runtime_mode=OFFICIAL_GPU`.
