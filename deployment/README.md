# Deployment — MVP

Target Google Cloud project: `modelready-m3` (configuration-driven; do not hard-code inside application logic).

## prem3-api (Mission 2 product API)

Distinct Cloud Run service. Do **not** deploy it over historical `modelready-m3`.

See `deployment/prem3_api/README.md`.

```powershell
py -3.13 scripts/provision_prem3_api_cloud.py --execute
py -3.13 scripts/deploy_prem3_api.py --execute
py -3.13 scripts/qualify_prem3_api_cloud.py --execute --write-evidence
```

The API container starts Uvicorn only. It does not include ADK, Meridian, or the frontend.

## prem3-evaluation-worker (M2-13)

Cloud Run Job for durable Evaluation execution. Cloud Tasks queue
`prem3-evaluation-dispatch` only launches the job.

See `deployment/prem3_evaluation_worker/README.md`.

```powershell
py -3.13 scripts/provision_evaluation_dispatch_cloud.py --execute
py -3.13 scripts/deploy_evaluation_worker.py --execute
py -3.13 scripts/qualify_evaluation_dispatch_cloud.py --execute --write-evidence
```

Do not merge this job with `meridian-eda-worker`. Do not deploy it over `modelready-m3`.

## Current milestone

**PRE_MODELING_GOLDEN** — PreM3 on private Cloud Run inspects a GCS Dataset A package, selects AUTO_SAFE remediations, verifies BigQuery model consumption, runs official Meridian EDA, and reaches evidence-backed `MODEL_READY`.

Already proven: **CLOUD_ALIVE**.

Not yet: Eventarc, ambient triggers, MEL, Dataset B/C, Meridian execution.

## MVP deployment path

**PRIMARY:** ADK CLI → Cloud Run API server (no `--with_ui`).

**FALLBACK:** custom `gcloud`/Docker deployment only if ADK CLI has a concrete blocker.

```text
Developer / deployer
    ↓ deploys
Cloud Run (us-central1, private)
    ↓
m3-runtime@modelready-m3.iam.gserviceaccount.com
    ↓ metadata server credentials
ADK / PreM3
    ↓
Vertex AI (GOOGLE_CLOUD_LOCATION=global) / Gemini
    ↓
deterministic tools (proof) and cloud_runtime_probe (identity)
```

Do not copy local ADC into the image. Do not set `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_API_KEY`. Do not create a service-account JSON key.

## Region split

| Concern | Value |
|---|---|
| Cloud Run / GCS / BigQuery jobs | `GOOGLE_CLOUD_REGION=us-central1` |
| Vertex AI / Gemini | `GOOGLE_CLOUD_LOCATION=global` |

`adk deploy cloud_run --region` must be `us-central1`, never `global`. The running container must still receive `GOOGLE_CLOUD_LOCATION=global` via Cloud Run env vars (this overrides ADK's generated Dockerfile, which otherwise sets location to the Cloud Run region).

## Identities

| Identity | Who | Used for |
|---|---|---|
| Deployer | human `gcloud` account | `adk deploy`, attaching the runtime SA, private invocation tests |
| Build | Cloud Build / Cloud Run source deploy | packaging the image |
| Runtime | `m3-runtime@modelready-m3.iam.gserviceaccount.com` | Vertex, GCS, BigQuery from the running service |

Local development continues to use Application Default Credentials. Cloud Run uses the attached service account and the metadata server.

## ADK package shape

The agent folder is `app/` so Python imports stay `from app...`.

- ADK API app id (folder name / `/list-apps`): `app`
- Gemini agent name (`M3_AGENT_NAME`): `modelready_m3`

Do not pass `--app_name=modelready_m3`; ADK copies the agent folder under that name and `from app...` would fail.

Required files:

```text
app/__init__.py
app/agent.py          # root_agent
app/requirements.txt  # runtime deps only; aligned with pyproject.toml
```

## Deploy (private API)

From a machine with working `gcloud` and the repo venv:

```powershell
$envVars = @(
  "GOOGLE_CLOUD_PROJECT=modelready-m3",
  "GOOGLE_CLOUD_LOCATION=global",
  "GOOGLE_CLOUD_REGION=us-central1",
  "GOOGLE_GENAI_USE_VERTEXAI=true",
  "M3_GEMINI_MODEL=gemini-2.5-flash",
  "M3_AGENT_NAME=modelready_m3",
  "M3_RUNTIME_SA=m3-runtime@modelready-m3.iam.gserviceaccount.com",
  "MODELREADY_CLOUD_RUN_SERVICE=modelready-m3",
  "MODELREADY_ORGANIZATION_ID=music-center",
  "MODELREADY_WORKSPACE_ID=mmm-demo",
  "MODELREADY_RAW_BUCKET=modelready-m3-912257136465-raw",
  "MODELREADY_ARTIFACT_BUCKET=modelready-m3-912257136465-artifacts",
  "MODELREADY_BQ_OPS_DATASET=modelready_ops",
  "MODELREADY_BQ_EXPERIENCE_DATASET=modelready_experience",
  "MODELREADY_BQ_MODELS_DATASET=modelready_models",
  "MODELREADY_ENV=demo",
  "MODELREADY_LOG_LEVEL=INFO",
  "MODELREADY_EDA_JOB=meridian-eda-worker",
  "MODELREADY_EDA_JOB_TIMEOUT=3300",
  "MODELREADY_DOMAIN_VIEW_REGISTRY_GS_URI=gs://modelready-m3-912257136465-artifacts/experiments/cloud_first_learning_cycle_001/domain_view_registry/"
) -join ","

.\.venv\Scripts\adk.exe deploy cloud_run `
  --project=modelready-m3 `
  --region=us-central1 `
  --service_name=modelready-m3 `
  --app_name=app `
  app `
  -- `
  --service-account=m3-runtime@modelready-m3.iam.gserviceaccount.com `
  --no-allow-unauthenticated `
  --min-instances=0 `
  --max-instances=2 `
  --set-env-vars=$envVars
```

Do not add `--with_ui` or `--trigger_sources` for this milestone.

Grant the deployer (not `allUsers`) `roles/run.invoker` on the service so authenticated smoke tests work:

```bash
gcloud run services add-iam-policy-binding modelready-m3 \
  --project=modelready-m3 \
  --region=us-central1 \
  --member="user:<DEPLOYER_EMAIL>" \
  --role=roles/run.invoker
```

## Authenticated test flow

```text
GET  /list-apps                         → ["app"]
POST /apps/app/users/<user>/sessions/<id>
POST /run_sse                           → Gemini
POST /run_sse  (cloud_runtime_probe)    → m3-runtime + GCS + BigQuery
```

Repeatable check (does not persist tokens):

```bash
python scripts/smoke_cloud_run.py --write-evidence
```

Expected terminal status: `CLOUD_ALIVE`.

Evidence is written to gitignored `artifacts/deployment/cloud_runtime_proof.json`.

## Guardrails

- Cloud Run scales to zero (`min-instances=0`, `max-instances=2`).
- Unauthenticated `/list-apps` must return 401/403.
- Runtime probe is read-only and never returns tokens.
- Reusing a `run_id` with the same package fingerprint resumes; a different fingerprint fails closed. Completed runs return existing `MODEL_READY` evidence and do not duplicate transforms.
- `MODEL_READY` is still owned by deterministic receipts, not by Cloud Run being alive.

## CLOUD_TASKMASTER

The deployed agent uses six run-level tools (`initialize_dataset_run`, `inspect_dataset_run`, `apply_safe_remediations`, `validate_and_publish_run`, `run_meridian_eda`, `complete_dataset_run`). Low-level mutating file tools stay in the library and are not registered on `root_agent`. Official google-meridian is **not** installed in the ADK Cloud Run image.

Increase the ADK Cloud Run request timeout when redeploying for Dataset A plus EDA (Gemini tool loops + isolated job wait). Pass after `--`:

```text
--timeout=3600
--memory=1Gi
```

## Isolated Meridian EDA Cloud Run Job

Python 3.12 + `google-meridian==1.8.0`. Same runtime SA. This is compute, not a second agent.

```powershell
gcloud builds submit `
  --config=deployment/meridian_eda_worker/cloudbuild.yaml `
  --project=modelready-m3 `
  --timeout=3600s

gcloud run jobs deploy meridian-eda-worker `
  --project=modelready-m3 `
  --region=us-central1 `
  --image=us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/meridian-eda-worker:1.8.0 `
  --service-account=m3-runtime@modelready-m3.iam.gserviceaccount.com `
  --memory=8Gi `
  --cpu=2 `
  --task-timeout=3300 `
  --max-retries=0 `
  --set-env-vars="GOOGLE_CLOUD_PROJECT=modelready-m3,GOOGLE_CLOUD_REGION=us-central1"

gcloud run jobs add-iam-policy-binding meridian-eda-worker `
  --project=modelready-m3 `
  --region=us-central1 `
  --member="serviceAccount:m3-runtime@modelready-m3.iam.gserviceaccount.com" `
  --role=roles/run.invoker
```

Do not add Eventarc, Pub/Sub, or `--trigger_sources`.

Do not add `--with_ui` or `--trigger_sources`.

Repeatable cloud proof:

```bash
python scripts/smoke_cloud_run.py --write-evidence
python scripts/stage_dataset_a_gcs.py --package-id dataset-a-v1
python scripts/run_cloud_dataset_a.py --package-uri gs://<raw-bucket>/music-center/mmm-demo/dataset-a/packages/dataset-a-v1/ --timeout 3600
```

Expected terminals: `CLOUD_ALIVE`, then `PRE_MODELING_COMPLETE` and `MODEL_READY`.

Evidence is gitignored under `artifacts/deployment/` (`cloud_taskmaster_proof.json`, `pre_modeling_taskmaster_proof.json`).

## Next

`AMBIENT_TASKMASTER` / Eventarc only after CLOUD_TASKMASTER stays green. Do not configure Eventarc in this milestone.
