# Mission 2 backend proof matrix

Canonical acceptance vocabulary. Tests may still say `PASS` internally.
This matrix never uses bare `PASS` as a cloud/provider claim.

Allowed proof states:

| State | Meaning |
|---|---|
| `PROVEN_LOCAL` | Deterministic tests or local fake-provider proof |
| `PROVEN_CLOUD` | Live Google Cloud resource / runtime proof |
| `IMPLEMENTED_NOT_LIVE_QUALIFIED` | Code exists; live provider/UI path not exercised |
| `DEFERRED_UI_PROVIDER_QUALIFICATION` | Architecture ready; interactive frontend/provider flow not run |
| `EXTERNAL_DEPENDENCY` | Correctness depends on an environment outside this freeze |
| `NOT_RUN` | Optional proof not executed |
| `FAILED` | Attempted and failed |

Do not upgrade a row because this freeze exists.

## Tenancy / auth

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| TenantContext from verified credential | Implemented | PROVEN_LOCAL | PROVEN_CLOUD (`/v1/me` AUTH_REQUIRED) | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `app/core/tenancy.py`, `tests/unit/test_prem3_api_auth.py` |
| Clerk runtime configured | Implemented | PROVEN_LOCAL (fake + fail-closed) | IMPLEMENTED_NOT_LIVE_QUALIFIED (secrets injected on `prem3-api-00008-br6`) | DEFERRED_UI_PROVIDER_QUALIFICATION | Clerk session UX | `docs/context/16_AUTH_BILLING_AND_ENTITLEMENTS.md` |
| Org membership authority | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `app/service/dependencies.py` |
| Firestore control plane | Implemented | PROVEN_LOCAL (InMemory twin) | PROVEN_CLOUD | — | — | `app/control_plane/firestore_repo.py` |

## Business IQ

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| Profile persistence | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | `app/business_iq/` |
| Snapshot | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | Business IQ snapshot routes |
| BUSINESS_CONTEXT_READY | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | `evaluateBusinessContextReady` |

## Data Foundation

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| Requirements / discovery / bindings / quality / coverage | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | `app/data_foundation/` |
| FOUNDATION_SOURCE_READY | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | `evaluateDataFoundationSourceReady` |
| DATA_FOUNDATION_READY | Implemented; workspace-level, distinct | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | — | — | `evaluateDataFoundationReady` |

## Google governance

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| OAuth architecture | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | Google consent | `app/integrations/google/` |
| KMS vault `aes-256-gcm+kms-v1` | Implemented | PROVEN_LOCAL | PROVEN_CLOUD (key + IAM) | — | — | M2-12Q report |
| Drive binding `prem3-modeling` | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | Drive binding routes |
| BQ binding `prem3_modeling` | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | BQ binding routes |
| IMPORT_READY | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `evaluate_import_readiness` |
| PUBLISH_READY | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | MODEL_READY evidence | `evaluate_publish_readiness` |

## Materialization

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| GCS_UPLOAD | Implemented | PROVEN_LOCAL | PROVEN_CLOUD (signed upload path) | — | — | Mission 10 upload proof |
| Drive materialization | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `MaterializationService` |
| BigQuery materialization | Implemented bounded 100000 | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | production-scale BQ | overflow → `MATERIALIZATION_LIMIT_EXCEEDED` |
| Stale-source rejection | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | source revalidation |

## Evaluation

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| DatasetUpload VERIFIED | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | upload complete |
| Evaluation ACCEPTED | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | `createEvaluation` 202 |
| Durable dispatch | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | `dsp_4898db7dd78d42568edf` |
| Cloud Run worker | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | `prem3-evaluation-worker` |
| Authorized ADK execution | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | worker SUCCEEDED + ADK tool schema |

## MODEL_READY

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| Historical Dataset A golden | Unchanged | PROVEN_LOCAL | PROVEN_CLOUD | — | — | historical `modelready-m3` / golden run |
| Durable-worker MODEL_READY | Gates unchanged | PROVEN_LOCAL (validators) | EXTERNAL_DEPENDENCY | — | official Meridian EDA | dispatch SUCCEEDED ≠ MODEL_READY |

## Publish

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| Drive publish adapter | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `PublishExecutionService` |
| BigQuery versioned publish | Implemented | PROVEN_LOCAL | IMPLEMENTED_NOT_LIVE_QUALIFIED | DEFERRED_UI_PROVIDER_QUALIFICATION | — | `model_ready_{dataset}_{run}` + `_current` |

## MEL

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| EXPERIENCE_LEARNED path | Unchanged | PROVEN_LOCAL | NOT_RUN | — | — | `app/mel/` |
| Dataset C EXPERIENCE_APPLIED / holdout | Unchanged | PROVEN_LOCAL | NOT_RUN | — | — | SEALED_HOLDOUT |
| Cloud learning-pair | Not claimed | — | NOT_RUN | — | — | no M2-13 artifact in training corpus |

## Dispatch safety

| Capability | Implementation | Local | Cloud | Live provider | External | Evidence |
|---|---|---|---|---|---|---|
| Duplicate dispatch fail-closed | Implemented | PROVEN_LOCAL | PROVEN_CLOUD (`attempt_count=1`) | — | — | claim tests + `dsp_4898db7dd78d42568edf` |
| Same-execution retry / reclaim | Implemented | PROVEN_LOCAL | NOT_RUN | — | — | `tests/unit/test_m2_13_evaluation_dispatch.py` |
| Launcher does not wait for Job LRO | Implemented | PROVEN_LOCAL | PROVEN_CLOUD | — | — | `test_cloud_run_launcher_does_not_wait_for_job_completion` |
