# M2-14 frontend contract handoff

Backend Mission 2 is frozen. Frontend implements against generated OpenAPI / JSON Schema.
Do not invent readiness semantics in the UI.

Interactive Clerk Organization UX and Google account-picker flows are **frontend
integration work**, not missing backend schema.

## Frozen read models

### Business IQ

Use Business IQ routes and generated types. Display `BUSINESS_CONTEXT_READY` only from
the evaluator response. Do not infer it from profile completeness prose.

### Data Foundation

Display `FOUNDATION_SOURCE_READY` from source receipts and `DATA_FOUNDATION_READY` from
the workspace-level evaluator. They are not interchangeable. Neither is `IMPORT_READY`.

### Import

Display `IMPORT_READY` / `NOT_IMPORT_READY` from `ImportReadinessReceiptResponse.status`.
Do not compute it from source health or foundation state.

### Materialization

Display `materialization_state` from `SourceMaterializationResponse`.
Transport states: `REVALIDATING`, `COPYING`, `VERIFYING`, `COMPLETE`, `FAILED`.
`COMPLETE` plus `upload_status=VERIFIED` means a DatasetUpload exists. That is not
Evaluation acceptance.

### Evaluation progress

Create: `POST /v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations`
Poll: `GET /v1/runs/{run_id}`

HTTP 202 means Evaluation accepted and Cloud Tasks enqueue succeeded.
It is not agent running and not `MODEL_READY`.

Read `EvaluationResponse.execution` (`EvaluationExecutionView`):

| Field | Use |
|---|---|
| `run_id` | identity |
| `evaluation_status` | always `ACCEPTED` in Mission 2 |
| `dispatch_status` | transport: `PENDING`, `QUEUED`, `LAUNCHING`, `RUNNING`, `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_TERMINAL` |
| timestamps | started / updated / completed |
| `current_stage` | DurableRunState stage when present |
| `terminal` | dispatch/run finished transporting |
| `outcome` | pipeline outcome label when present |
| `model_ready` | true only from deterministic evidence |
| `approval_required` | Dataset B / human-approval path |
| `issue_count` | count only; do not invent issues |
| `readiness_receipt_available` | receipt exists |
| `eda_receipt_available` | official EDA receipt exists |

Never display or persist: `package_uri`, GCS paths, Cloud Task names, Cloud Run LRO,
tenant IDs, raw exceptions, credentials.

No SSE. Poll the run resource.

`dispatch_status=SUCCEEDED` is not `MODEL_READY`.

### MODEL_READY

True only when `execution.model_ready` is true **and** readiness evidence exists.
Do not derive it from `ACCEPTED`, `SUCCEEDED`, or publish readiness.

### PUBLISH_READY / publish execution

`PublishReadinessReceiptResponse.status` is `PUBLISH_READY` or `NOT_PUBLISH_READY`.
Publish execution statuses are `COMPLETE`, `PARTIAL`, `FAILED`.
`PUBLISH_READY` ≠ published.

### Google connection / binding

Present generated fields only: connection `status`, `display_email`, `capabilities`,
Drive binding `workspace_id` / folder identity presentation, BigQuery binding dataset
`prem3_modeling`. Do not treat Google email or subject as tenant identity.

## Mockups

Existing `docs/mockups/` remain the visual reference. M2-14 does not redesign them.
Backend field names for Evaluation progress are the `execution` view above.
Missing interactive Clerk/Google screens are frontend work, not backend schema deficiency.

See also `docs/backend/M2_12_UI_BACKEND_SUPPORT_MATRIX.md`.
