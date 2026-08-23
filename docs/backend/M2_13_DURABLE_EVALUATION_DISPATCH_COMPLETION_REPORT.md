# M2-13 — Durable Evaluation Dispatch + Cloud-Authorized ADK Execution

## A. Baseline

| Field | Value |
|---|---|
| SOURCE_BRANCH | `feature/prem3-m2-canonical-google-qualification` |
| SOURCE_SHA | `56116b74372a5a96a441fedc7d3d8411abf79299` |
| M13_BRANCH | `feature/prem3-m2-durable-evaluation-dispatch` |
| FINAL_SHA | *(set after commits)* |

Do not branch from `origin/main`. Do not merge automatically.

## B. Dispatch

| Field | Value |
|---|---|
| DISPATCH_MODEL | frozen `EvaluationDispatch` + `DispatchStatus` |
| DISPATCH_STORE | InMemory + Firestore `tenants/.../evaluations/{run_id}/dispatches/{dispatch_id}` plus index `evaluation_dispatches/{dispatch_id}` |
| CLOUD_TASKS_QUEUE | `prem3-evaluation-dispatch` / `us-central1` |
| CLOUD_TASK_RETRY_POLICY | max_attempts=8, min_backoff=10s, max_backoff=300s, max_concurrent=8, rate=5/s, per-task dispatch_deadline=60s |
| IDEMPOTENCY | same Idempotency-Key → same Evaluation/`run_id`/`dispatch_id` |
| ORPHAN_RECOVERY | enqueue failure → 503 `EVALUATION_DISPATCH_UNAVAILABLE` + `FAILED_RETRYABLE`; retry re-enqueues the same dispatch. No cron reconciler. Exhausted Cloud Run retries are operator/new-Evaluation, not a silent second run. |

`EvaluationStatus` remains `ACCEPTED`. Dispatch statuses: `PENDING`, `QUEUED`, `LAUNCHING`, `RUNNING`, `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_TERMINAL`. `MODEL_READY` is not a dispatch status.

Cloud Tasks is the launcher only. ADK does not run inside the Cloud Task HTTP request.

## C. Internal auth

| Field | Value |
|---|---|
| TASK_SERVICE_ACCOUNT | `prem3-evaluation-dispatcher@modelready-m3.iam.gserviceaccount.com` |
| OIDC_AUDIENCE | `{prem3-api-url}/internal/v1/evaluation-dispatches` |
| WRONG_IDENTITY_NEGATIVE | PASS (unit) |
| CUSTOMER_IDENTITY_NEGATIVE | PASS (unit; Clerk bearer denied) |

`X-CloudTasks-*` headers are metadata only.

## D. Cloud Run Job

| Field | Value |
|---|---|
| JOB_NAME | `prem3-evaluation-worker` |
| IMAGE | sibling digest from same `app/` source + `app/requirements.txt` (ADK). Not slim `prem3-api`. |
| SERVICE_ACCOUNT | `m3-runtime@modelready-m3.iam.gserviceaccount.com` |
| TASK_TIMEOUT | 7200 seconds |
| MAX_RETRIES | 2 |
| TASKS / PARALLELISM | 1 / 1 |
| CPU / MEMORY | 2 / 4Gi |
| REGION | `us-central1` |
| ENTRYPOINT | `python -m app.workers.evaluation_worker` |

Override: `PREM3_EVALUATION_DISPATCH_ID` only. Isolated `meridian-eda-worker` is unchanged.

## E. Execution authority

| Field | Value |
|---|---|
| SERVICE_TENANT_BINDING | `TenantContext(auth_state=SERVICE)` after loading the trusted dispatch |
| WORKSPACE_BINDING | worker binds `WorkspaceContext`; executor re-binds |
| EXECUTION_CONTEXT_BINDING | `EvaluationExecutor` derives from Evaluation |
| ENTITLEMENT_SNAPSHOT | frozen Evaluation snapshot; no Stripe on the worker |
| MODEL_AUTHORITY_REGRESSION | PASS (`tests/unit/test_execution_authority.py`) |

## F. Run read model

Public `EvaluationExecutionView`: `run_id`, `evaluation_status`, `dispatch_status`, timestamps, `current_stage`, `terminal`, `outcome`, `model_ready`, `approval_required`, `issue_count`, receipt flags.

Hidden: `package_uri`, GCS paths, Cloud Task name, Cloud Run LRO, tenant authority, raw exceptions.

Polling contract: `GET /v1/runs/{run_id}`. No SSE.

## G. Cloud proof

Filled by `scripts/qualify_evaluation_dispatch_cloud.py` after deploy.

| Proof | Value |
|---|---|
| CLOUD_API_ALIVE | *(qualify)* |
| CLOUD_DURABLE_EVALUATION_DISPATCH | *(qualify)* |
| CLOUD_EVALUATION_JOB_LAUNCHED | *(qualify)* |
| CLOUD_AUTHORIZED_ADK_EXECUTION | *(qualify)* |
| CLOUD_MODEL_READY_EVALUATION | false / EXTERNAL_DEPENDENCY unless official EDA completes |
| CLOUD_EVALUATION_RETRY_PROOF | local PASS; cloud NOT_RUN unless a controlled fault is executed |
| DUPLICATE_DISPATCH_FAIL_CLOSED | local PASS |

## H. Golden regression

| Field | Value |
|---|---|
| DATASET_A_FINGERPRINT | `7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f` |
| DATASET_A | unchanged |
| DATASET_B | approval-required / WAITING_FOR_APPROVAL where applicable |
| DATASET_C | SEALED_HOLDOUT / HOLDOUT_QUALIFICATION_ONLY |
| MEL | uncontaminated |

## I. Deferred live provider proofs

All remain `DEFERRED_UI_PROVIDER_QUALIFICATION`:

- LIVE_CLERK_CLOUD_IDENTITY_PROOF
- LIVE_GOOGLE_OAUTH_PROOF
- LIVE_GOOGLE_DRIVE_CONNECTION_PROOF
- LIVE_GOOGLE_BIGQUERY_CONNECTION_PROOF
- LIVE_DRIVE_MATERIALIZATION_PROOF
- LIVE_BIGQUERY_MATERIALIZATION_PROOF
- LIVE_DRIVE_PUBLISH_PROOF
- LIVE_BIGQUERY_PUBLISH_PROOF

## J. IAM

| Principal | Resource | Role | Reason |
|---|---|---|---|
| `m3-runtime@...` | queue `prem3-evaluation-dispatch` | `roles/cloudtasks.enqueuer` | enqueue launch tasks |
| `m3-runtime@...` | SA `prem3-evaluation-dispatcher@...` | `roles/iam.serviceAccountUser` | specify OIDC identity on createTask |
| `prem3-evaluation-dispatcher@...` | none beyond token mint | Cloud Tasks OIDC identity only | invoke internal launch; app verifies token |
| `m3-runtime@...` | job `prem3-evaluation-worker` | `roles/run.jobsExecutorWithOverrides` | start one job with dispatch_id override |
| `m3-runtime@...` | existing Firestore/GCS/BQ/Vertex/EDA | unchanged | worker execution identity |

No Owner. No Editor. No Cloud Run Admin.

## K. Tests

| Gate | Result |
|---|---|
| RUFF | PASS |
| SCHEMA_DRIFT | PASS |
| OPENAPI_DRIFT | PASS (internal launch excluded) |
| UNIT_TESTS | PASS |
| INTEGRATION_TESTS | PASS (`data_foundation -k not meridian_eda`; `integration -k not bigquery and not meridian_eda`) |
| REGRESSION_TESTS | PASS |
| PRECLOUD_CHECK | READY_FOR_CLOUD_RUN |
| FRONTEND_LINT | PASS |
| FRONTEND_TYPECHECK | PASS |
| FRONTEND_TEST | PASS (84) |
| FRONTEND_BUILD | PASS |
| NEW_FAILURES_FROM_THIS_MISSION | 0 |

## L. Change boundary

| Field | Value |
|---|---|
| NEW_BUSINESS_IQ_CAPABILITY | 0 |
| NEW_DATA_FOUNDATION_CAPABILITY | 0 |
| NEW_GOOGLE_INTEGRATION_CAPABILITY | 0 |
| RUN_BASED_BILLING | 0 |
| ADK_HTTP_ENDPOINT_ADDED | false |
| MODEL_AUTHORITY_EXPANDED | false |

## Recovery contract

If Evaluation and dispatch persist but Cloud Task enqueue fails:

1. API returns 503, not 202.
2. Dispatch is `FAILED_RETRYABLE`.
3. Client retry with the same idempotency key reuses `run_id` and `dispatch_id`.
4. A new queue attempt is created (or AlreadyExists converges).
5. No cron reconciler in this mission.

## Next

M2-14 — Mission 2 Acceptance Freeze. Do not start it in this mission.
