# M2-12 materialization + verified customer publish

**Status:** restacked onto PR #15 main. See `M2_12Q_CANONICAL_GOOGLE_QUALIFICATION_REPORT.md`.

## Baseline

| Item | Value |
|---|---|
| `origin/main` / PR15_MERGE_SHA | `a098e2cdb36b11d1c9f81790be941b913be117c6` |
| PR15_HEAD | `a610c5e359a53c8212211958e2b0d1d10642e7dc` |
| Integration branch | `feature/prem3-m2-canonical-google-qualification` |
| M12 original commit | `19d77902f00de5098209556c526cf184a8162586` |
| Design freeze | `foundational-intake-freeze-2026-08-22-v1` |
| PR15_ALREADY_ON_MAIN | true |
| NEW_FOUNDATIONAL_INTAKE_CAPABILITY | 0 |

## Architecture

Business IQ establishes meaning.  
Data Foundation establishes evidence.  
`IMPORT_READY` authorizes exact source materialization.  
`DatasetUpload` freezes the Evaluation input.  
`MODEL_READY` proves pre-modeling completion.  
`PUBLISH_READY` authorizes exact destination publication.  
`PublishExecutionReceipt` proves delivery.

M2-12 consumes `PreM3ImportContractV1` and `PreM3PublishContractV1`. It does not replace them.

```
IMPORT_READY (+ FOUNDATION_SOURCE_READY when DF-managed)
  → source version revalidation
  → SourceMaterializationReceipt
  → DatasetUpload VERIFIED
  → Evaluation
  → MODEL_READY (existing pipeline; read only)
  → PUBLISH_READY
  → Drive exports/reports and/or prem3_modeling.model_ready_*
  → PublishExecutionReceipt
```

## New contracts

- `SourceMaterializationReceipt` — distinct from Data Foundation `DriveImportReceipt`
- `MaterializationStatus`: `REVALIDATING` / `COPYING` / `VERIFYING` / `COMPLETE` / `FAILED` (API is synchronous and returns a terminal result)
- `MaterializationResultKind`: `CREATED_NEW_UPLOAD` / `REUSED_EXISTING_UPLOAD`
- `CanonicalFoundationSourceGate` backed by the shared `DataFoundationStore` from `build_product_stores(repo)`
- `ModelReadyEvidenceResolver` — reads deterministic run evidence; never emits `MODEL_READY`
- `PublishExecutionReceipt` with per-destination `VERIFIED` / `VERIFIED_EXISTING` / `FAILED`

## New routes

| Operation ID | Method | Path |
|---|---|---|
| `materializeDatasetSource` | POST | `/v1/workspaces/{workspace_id}/datasets/{dataset_id}/materializations` |
| `listDatasetMaterializations` | GET | same collection |
| `getDatasetMaterialization` | GET | `.../materializations/{materialization_id}` |
| `getPublishReadiness` | GET | `.../evaluations/{run_id}/publish-readiness` |
| `publishEvaluation` | POST | `.../evaluations/{run_id}/publishes` |
| `listEvaluationPublishes` | GET | same collection |
| `getEvaluationPublish` | GET | `.../publishes/{publish_id}` |

`evaluatePublishReadiness` remains the existing POST. Destinations and source identities are never accepted from the request body.

## Materialization state machine

1. Require current `IMPORT_READY` and `superseded == false`.
2. Recompile the Import Contract from live metadata. Manifest mismatch → `SOURCE_CHANGED_SINCE_IMPORT_READY`.
3. If DF evidence exists, require `FOUNDATION_SOURCE_READY` and `governance_import_ready`. Do not require `DATA_FOUNDATION_READY`.
4. `GCS_UPLOAD` revalidates and reuses the existing VERIFIED upload.
5. Drive/BigQuery copy into a new DatasetUpload via `ObjectStore.write_bytes` (create-only) and `UploadService.complete_upload`.
6. Persist `SourceMaterializationReceipt`. Return `COMPLETE` only after `VERIFIED`.

Pre-model review findings survive. Unknown intervals are not imputed.

BigQuery export is bounded (`BOUNDED_EXPORT_MAX_ROWS = 100000`). This mission does not claim production-scale `SELECT *` materialization.

## Publish execution state machine

1. Resolve MODEL_READY evidence server-side.
2. Compile `PreM3PublishContractV1` and evaluate `PUBLISH_READY`.
3. Persist a new `PublishReadinessReceipt` (do not mutate an older receipt into execution proof).
4. Write Drive artifacts only under `exports/{workspace}/{dataset}/{run}`.
5. Create versioned `model_ready_{dataset}_{run}` first; move `model_ready_{dataset}_current` only after readback.
6. Persist `PublishExecutionReceipt` as `COMPLETE`, `PARTIAL`, or `FAILED`.

## Data Foundation

Production runtime uses `CanonicalFoundationSourceGate` + `DataFoundationStore`.
`NullFoundationSourceGate` is fixture-only. Source-ID lookups are tenant- and
workspace-qualified before use. `DATA_FOUNDATION_READY` is not required per source.

## Security invariants

- Tenant is never taken from body/query/path/headers/cookies.
- Cross-tenant materialization and publish return the same 404 as missing resources.
- OAuth tokens are not stored on receipts or returned in API responses.
- Data Foundation warehouse names (`canonical_*`, `stg_*`, `source_registry`, `source_health`, `model_input_mmm`) cannot be publish targets.
- Drive publish cannot write `imports/`, `sources/`, `business_data/`, or `evidence/`.
- Direct Google Sheets import remains deferred.

## Tests

- `tests/unit/test_m2_12_materialization.py`
- `tests/unit/test_m2_12_publish.py`
- `tests/unit/test_m2_12_invariants.py`
- Existing import/publish/upload/Evaluation/tenancy suites remain in force.

## Proofs

- Dataset A fingerprint must remain `7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f`.
- Live Google materialization/publish: `EXTERNAL_DEPENDENCY` / `LIVE_CLOUD_PROOF_NOT_RUN`.

## Known external dependencies

- Customer-authorized Google Drive / BigQuery sessions
- Production-size BigQuery export beyond the bounded runtime
- Live Google OAuth / Drive / BigQuery sessions and a Clerk-authenticated test tenant

## OpenAPI

Regenerated from FastAPI models.

`contracts/openapi.yaml` sha256=`2c2c3c4b0c0a68590546976ac09e46f4855f2744076c20e96f2d775925953438`

`contracts/schema/api.schema.json` sha256=`e8c14c8bfcda8c75ed151dd1435f19e185639d5e71b2a0282ec7979372205493`

## Qualification notes

`tests/unit` passed with `-k "not meridian_eda"`.

`tests/integration/test_dataset_a_golden_slice.py` and `test_dataset_a_local_repairs.py` passed.

`tests/integration/test_dataset_a_bigquery.py` requires official `google-meridian` or `MODELREADY_EDA_JOB`. That environment is not configured here. This is an existing EXTERNAL_DEPENDENCY, not an M2-12 contract change.
