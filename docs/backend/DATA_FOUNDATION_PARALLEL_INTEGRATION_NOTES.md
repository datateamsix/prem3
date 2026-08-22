# Data Foundation — parallel integration notes

**Branch:** `feature/prem3-data-foundation-backend`  
**Base:** `feature/prem3-google-governance` @ `02cec50b6da6507838081e65086eaaf29a4a5329`  
**origin/main:** `dce8a209bb67fbaa3c8a78ae4e8a7384897252ed` (does not yet contain Mission 2)

## Why this branch is not based on origin/main

The Data Foundation prompt asked for a parallel branch from `main` and ports if the control plane had not landed. Mission 2 *has* landed on the local qualified line (tenant, Firestore, Clerk, Stripe, prem3-api, uploads, Google OAuth, M2-11 import/publish governance). Branching from `origin/main` would invent a second authority plane.

This package stays isolated so it can rebase onto `main` once Mission 2 merges.

## Systems already available on this base

| System | Path | Data Foundation use |
|---|---|---|
| TenantContext | `app/core/tenancy.py` | Server-owned tenant on every mutating call |
| Control plane | `app/control_plane/` | Workspace, GoogleConnection, Drive/BQ bindings, receipts |
| prem3-api | `app/service/app.py` | Workspace-scoped `/v1/workspaces/{id}/data-foundation` |
| Google OAuth | `app/service/google_oauth.py` | Reuse connections; do not add a second OAuth stack |
| Drive depot | `app/service/google_drive.py` | Bound `root_folder_id`; keep `imports/exports/reports` |
| BigQuery depot | `app/service/google_bigquery.py` | Bound customer project + `prem3_modeling` |
| M2-11 IMPORT_READY | `app/governance/import_evaluator.py` | Unchanged authority/version/role gate |

## Expected later wiring

### Business IQ (`REQ-012`–`018`)

Implemented as a bounded domain at `app/business_iq/`. Data Foundation consumes durable snapshots through `snapshot_from_business_iq`; it does not persist Business IQ itself. Do not hard-code Business IQ UI fields.

### M2-12 materialization

M2-11 `IMPORT_READY` remains “safe to materialize into DatasetUpload.” DF source receipts are a stricter quality/transform gate that *consumes* that authority. Materializers should require both when promoting file/table bytes into an immutable DatasetUpload. Do not bypass DatasetUpload.

### Drive layout

Mission 11 children: `imports`, `exports`, `reports`.  
Data Foundation children (same root): `sources`, `business_data`, `evidence`, `system`.

`DriveFoundationLayout` is DF-owned metadata keyed by tenant/workspace and bound to the existing `root_folder_id`. Do not create a second depot.

### Open PRs that overlap tools/core

PRs #9, #10, and #13 are MEL / coordinator / cloud-learning work. They touch `app/core/run_coordinator.py` and adjacent tools. This branch must not edit the coordinator. If those PRs land first, rebase and keep DF isolated.

## Multi-tenant expectations (enforced in DF tests on this line)

- Cross-tenant source access denied
- Cross-tenant plan execution denied
- Drive root from another tenant denied
- BigQuery project from another tenant denied
- Agent/client cannot override `DataFoundationContext`

## API surface

Routes are workspace-scoped, not dataset-scoped:

```text
/v1/workspaces/{workspace_id}/data-foundation/...
```

M2-11 import governance stays under:

```text
/v1/workspaces/{workspace_id}/datasets/{dataset_id}/...
```
