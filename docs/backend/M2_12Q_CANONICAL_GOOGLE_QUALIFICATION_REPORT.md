# M2-12Q — Canonical Google I/O qualification

Integration + vault hardening. Live provider proofs remain a separate level.

## A. Baseline

| Field | Value |
|---|---|
| PR15_MERGE_SHA | `a098e2cdb36b11d1c9f81790be941b913be117c6` |
| PR15_HEAD | `a610c5e359a53c8212211958e2b0d1d10642e7dc` |
| PR15_FREEZE | `foundational-intake-freeze-2026-08-22-v1` |
| M12_ORIGINAL_COMMIT | `19d77902f00de5098209556c526cf184a8162586` |
| M12_SAFETY_REF | `backup/prem3-m2-materialization-publish-19d779` |
| INTEGRATION_BRANCH | `feature/prem3-m2-canonical-google-qualification` |
| INTEGRATION_METHOD | cherry-pick `19d7790` onto cleaned post-PR15 baseline |
| M12_INTEGRATION_COMMIT | `e0df4f4` |

## B. Inherited baseline repair

| Field | Value |
|---|---|
| BASELINE_RUFF_ERROR_COUNT | 79 |
| BASELINE_RUFF_RULES | E501, I001, UP035, F401, UP012 |
| BASELINE_RUFF_REPAIR | PASS (`9a26574` `chore: restore lint gate after BIQ Data Foundation merge`) |
| POST_PR15_BASELINE_TESTS | PASS before Mission 12 apply (ruff, contracts, OpenAPI, unit `-k not meridian_eda`, DF integration, regression, precloud, frontend lint/typecheck/test/build) |
| Dataset A official Meridian | existing EXTERNAL_DEPENDENCY, not a regression |

Do not rewrite history to pretend main was green before this mission.

## C. Canonical Data Foundation

| Field | Value |
|---|---|
| PRODUCTION_DF_STORE | `build_product_stores(repo)` → Firestore or InMemory `DataFoundationStore` |
| NULL_FOUNDATION_GATE_PRODUCTION | false |
| CANONICAL_SOURCE_BINDING | yes |
| CANONICAL_SOURCE_RECEIPT | yes |
| TENANT_QUALIFIED_DF_READBACK | yes (mismatch → `RESOURCE_NOT_FOUND`) |
| BUSINESS_REQUIREMENT_LINEAGE | yes (`FOUNDATION_LINEAGE_MISMATCH` on role conflict) |
| PREMODEL_REVIEW_PRESERVATION | yes (copied, not resolved) |

`DriveImportReceipt` remains Data Foundation warehouse intake. `SourceMaterializationReceipt` remains Evaluation input authority.

## D. Materialization

| Field | Value |
|---|---|
| IMPORT_READY_GATE | PASS |
| FOUNDATION_SOURCE_DUAL_GATE | PASS_CANONICAL |
| SOURCE_VERSION_REVALIDATION | PASS |
| GCS_UPLOAD_REUSE | PASS |
| DRIVE_MATERIALIZATION | PASS (local Fake + Rest methods present) |
| BIGQUERY_MATERIALIZATION | PASS_BOUNDED |
| BIGQUERY_ROW_LIMIT | 100000 |
| DATASETUPLOAD_VERIFICATION | PASS |

Over-limit tables raise `MATERIALIZATION_LIMIT_EXCEEDED`. No silent `LIMIT 100000` success.

## E. Publish

| Field | Value |
|---|---|
| MODEL_READY_RESOLVER | PASS |
| PUBLISH_READY_GATE | PASS |
| DRIVE_PUBLISH | PASS (local) |
| BIGQUERY_VERSIONED_PUBLISH | PASS (local) |
| BIGQUERY_CURRENT_POINTER_VERIFICATION | PASS (local) |
| DF_NAMESPACE_PROTECTION | PASS (`app/data_foundation/owned_resources.py`) |
| PUBLISH_EXECUTION_RECEIPT | PASS |

## F. Credential vault

| Field | Value |
|---|---|
| PREVIOUS_ALGORITHM | `hmac-sha256-xor-v1` |
| NEW_ALGORITHM | `aes-256-gcm+kms-v1` |
| KMS_KEY_RESOURCE | `projects/modelready-m3/locations/us-central1/keyRings/prem3/cryptoKeys/prem3-google-oauth-credentials` |
| KMS_IAM | principal `m3-runtime@modelready-m3.iam.gserviceaccount.com`; resource key above; role `roles/cloudkms.cryptoKeyEncrypterDecrypter`; reason encrypt/decrypt DEKs only |
| PERSISTED_LEGACY_CREDENTIAL_COUNT | 0 |
| TOKEN_LEAKAGE_TEST | PASS |

Production Google OAuth without `GOOGLE_KMS_KEY` fails closed. Incremental auth with no new refresh token preserves the existing envelope.

## G. Deployment

| Field | Value |
|---|---|
| SOURCE_SHA | `f2c517c6abb80a2ac5a5fbc4aba5c3ae6b0b091a` |
| IMAGE_URI | `us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/prem3-api:f2c517c6abb80a2ac5a5fbc4aba5c3ae6b0b091a` |
| IMAGE_DIGEST | `sha256:6977f7d78b4f9eb74192ebaad21fffcb7cb5d468886c497695d724cad5ed744d` |
| CLOUD_RUN_REVISION | `prem3-api-00005-g77` |
| SERVICE_URL | `https://prem3-api-vkcd3cbiea-uc.a.run.app` |
| SERVICE_ACCOUNT | `m3-runtime@modelready-m3.iam.gserviceaccount.com` |

`scripts/deploy_prem3_api.py` sets `GOOGLE_KMS_KEY`. Historical `modelready-m3` and `meridian-eda-worker` were not modified.

Cloud route regression after `prem3-api-00005-g77`:

- `GET /health` → 200 public ok
- `GET /healthz` → Google 404 (Cloud Run reserved `z` path; liveness remains `/health`)
- `GET /readyz` → 200 truthful (`auth_provider=not_configured`, `billing_provider=configured`)
- `GET /v1/catalog/plans` → 200 public
- `GET /v1/me`, workspace create, materialization, publish without Clerk → 503 `AUTH_PROVIDER_NOT_CONFIGURED`
- unsigned identity webhook → 503 `AUTH_PROVIDER_NOT_CONFIGURED`
- unsigned billing webhook → 503 `BILLING_PROVIDER_NOT_CONFIGURED` (Stripe webhook secret not attached)

## H. Live proofs

All live provider proofs are independent. None were executed in this environment.

| Proof | State |
|---|---|
| LIVE_GOOGLE_OAUTH_PROOF | NOT_RUN |
| LIVE_GOOGLE_DRIVE_CONNECTION_PROOF | NOT_RUN |
| LIVE_GOOGLE_BIGQUERY_CONNECTION_PROOF | NOT_RUN |
| LIVE_DRIVE_MATERIALIZATION_PROOF | NOT_RUN |
| LIVE_DRIVE_STALE_SOURCE_PROOF | NOT_RUN |
| LIVE_BIGQUERY_MATERIALIZATION_PROOF | NOT_RUN |
| LIVE_BIGQUERY_STALE_SOURCE_PROOF | NOT_RUN |
| LIVE_DRIVE_PUBLISH_PROOF | NOT_RUN |
| LIVE_BIGQUERY_PUBLISH_PROOF | NOT_RUN |

Deployed `prem3-api-00003-d4z` has no `GOOGLE_OAUTH_CLIENT_ID` / secret and no Clerk secrets. Interactive Google consent was not available.

## I. Boundedness

| Field | Value |
|---|---|
| BIGQUERY_MATERIALIZATION | PASS_BOUNDED |
| BIGQUERY_MAX_ROWS | 100000 |
| BQ_MATERIALIZATION_LIMIT_FAIL_CLOSED | PASS (local) |
| PRODUCTION_SCALE_BIGQUERY_MATERIALIZATION | false |

## J. Regression

| Field | Value |
|---|---|
| DATASET_A_FINGERPRINT | `7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f` (unchanged invariant) |
| DATASET_A_REGRESSION | local unit/integration paths PASS; official Meridian EDA remains EXTERNAL_DEPENDENCY |
| DATASET_B_REGRESSION | WAITING_FOR_APPROVAL / APPROVAL_REQUIRED unchanged |
| DATASET_C_REGRESSION | SEALED_HOLDOUT / HOLDOUT_QUALIFICATION_ONLY unchanged |
| MEL_REGRESSION | no promotion/holdout semantic change in this mission |

## K. Contracts / tests

Local results after integration + KMS:

| Gate | Result |
|---|---|
| RUFF | PASS |
| OPENAPI_DRIFT | PASS (`contracts/openapi.yaml` sha256=`2c2c3c4b0c0a68590546976ac09e46f4855f2744076c20e96f2d775925953438`) |
| SCHEMA_DRIFT | PASS |
| UNIT_TESTS | PASS (`tests/unit -k "not meridian_eda"`) |
| DF_INTEGRATION_TESTS | PASS (`tests/integration/data_foundation -k "not meridian_eda"`) |
| REGRESSION_TESTS | PASS (`tests/regression -k "not meridian_eda"`) |
| PRECLOUD_CHECK | READY_FOR_CLOUD_RUN |
| FRONTEND_LINT | PASS |
| FRONTEND_TYPECHECK | PASS |
| FRONTEND_TEST | PASS (84) |
| FRONTEND_BUILD | PASS |
| NEW_FAILURES_FROM_THIS_MISSION | 0 |

## L. Change boundary

| Field | Value |
|---|---|
| DURABLE_EVALUATION_DISPATCH_ADDED | false |
| CLOUD_AUTHORIZED_ADK_EXECUTION_CLAIMED | false |
| NEW_BUSINESS_IQ_CAPABILITY | 0 |
| NEW_DATA_FOUNDATION_INTAKE_CAPABILITY | 0 |
| DIRECT_GOOGLE_SHEETS_SUPPORT_ADDED | false |

## M. External dependencies blocking QUALIFIED

1. Clerk session on deployed `prem3-api` (secret not attached to current revision).
2. `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` / registered redirect URI.
3. Interactive test Google account consent.
4. Official `google-meridian` or `MODELREADY_EDA_JOB` for Dataset A BQ/EDA (pre-existing).
5. Production-scale BigQuery materialization architecture (explicitly out of claim).

## Commits

1. `9a26574` chore: restore lint gate after BIQ Data Foundation merge
2. `e0df4f4` Mission 2: materialize governed sources and verify customer publishing (cherry-pick)
3. `f43f0ea` Mission 2: integrate governed IO with canonical Data Foundation
4. `f0bbade` Mission 2: harden Google credential vault with KMS
5. this commit — qualify canonical Google I/O runtime (docs + deploy wiring)

## Terminal

`PREM3_M2_CANONICAL_GOOGLE_IO_NOT_QUALIFIED`

`CODE_READY=true`

Live Google OAuth, Drive, BigQuery, materialization, stale-source, and publish proofs were not run.
