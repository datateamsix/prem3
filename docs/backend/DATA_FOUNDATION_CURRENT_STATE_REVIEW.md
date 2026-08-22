# Data Foundation — current-state review

**Review date:** 2026-08-22  
**Feature branch:** `feature/prem3-data-foundation-backend`  
**Base branch:** `feature/prem3-google-governance`  
**main_sha (origin/main):** `dce8a209bb67fbaa3c8a78ae4e8a7384897252ed`  
**base_sha (google-governance HEAD used as branch point):** `02cec50b6da6507838081e65086eaaf29a4a5329`  
**Branch correctly based on that SHA:** yes

This review is bounded to Data Foundation paths. It does not audit MEL internals, Meridian worker internals, branding, or frontend rendering.

## 1. What existing primitives can be reused unchanged?

- `app/tools/profiling.py` — row/column counts, dtypes, missingness, exact duplicates, grain inference.
- `app/tools/remediation.py` — copy-on-write date/numeric/label/duplicate transforms.
- `app/tools/provenance.py` and `app/tools/fingerprints.py` — lineage and semantic content fingerprints.
- `app/tools/safety.py` — summable-column and date-format guards.
- `app/tools/bigquery_inspect.py` — read-back verification philosophy for *outputs*, not discovery.
- `app/registry/` — sole provider registry (52 entries, typed catalog).
- `app/governance/import_evaluator.py` — sole emitter of Mission 11 `IMPORT_READY`.
- `app/control_plane/models.py` — `GoogleConnection`, `DriveWorkspaceBinding`, `BigQueryWorkspaceBinding`.
- `app/service/google_drive.py` / `google_bigquery.py` / `google_oauth.py` — connection and depot binding.
- `app/core/tenancy.py` — `TenantContext` / `WorkspaceContext`.
- `app/core/source_inventory.py` — `CanonicalRole` for M2-11 role mapping.
- `app/tools/io.py` — CSV and Parquet table I/O (XLSX is not in this helper).
- Fake Google adapters in `app/integrations/google/adapters.py`.

## 2. What should be generalized?

- Profiling and remediation become *composed* Data Foundation quality/transform primitives with `DF-Q*` / `DF-T*` IDs. Existing `MR-*` IDs stay model-readiness-only.
- Provenance receipts generalize to DF receipt types without replacing run-coordinator transformation evidence.
- BigQuery inspect’s read-back pattern is reused for `prem3_modeling` outputs. Discovery stays metadata-first and budgeted.
- Registry entries may grow optional discovery/provisioning fields. Existing fixtures must stay valid.
- Drive depot children expand under the same bound root folder ID. `imports` / `exports` / `reports` remain.

## 3. What new package boundaries are required?

`app/data_foundation/` is the isolated domain:

- contracts, context, store ports, receipts, readiness
- discovery (requirements, candidates, registry matching, query budget)
- quality engine
- transformation catalog / preview / executor
- BigQuery and Drive adapters
- foundation provisioning
- workspace-scoped `DataFoundationService`

Do not fold this into `app/core/run_coordinator.py`.

## 4. What code must not be modified?

- `app/core/run_coordinator.py`
- Meridian worker / official EDA
- `MODEL_READY` validators and Dataset A golden fingerprint
  `7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f`
- `frontend/`
- `evaluate_import_readiness` semantics (it remains the sole M2-11 `IMPORT_READY` emitter)
- Public `/planner` (must not call prem3-api)

Safe, additive edits only: prem3-api router registration, optional registry fields, OpenAPI description text.

## 5. What in-flight branches/PRs create merge risk?

See `DATA_FOUNDATION_PARALLEL_INTEGRATION_NOTES.md`.

```text
open_prs_relevant_to_app_core_tools_registry
  #9  feature/prem3-first-real-learning-cycle
  #10 feature/prem3-provider-agnostic-coordinator
  #13 feature/prem3-cloud-first-learning-cycle

remote_branches_with_path_overlap
  origin/feature/prem3-provider-agnostic-coordinator
  origin/feature/prem3-first-real-learning-cycle
  origin/feature/prem3-cloud-first-learning-cycle
  origin/feature/prem3-mel-episode-core
  origin/feature/prem3-mmm-intelligence-tools

files_likely_to_conflict
  app/core/run_coordinator.py   (we will not edit)
  app/tools/profiling.py        (compose only; avoid drive-by edits)
  app/tools/remediation.py
  app/registry/schema.py        (optional fields only)
  app/service/app.py            (additive router include)

integration_strategy
  New package + workspace-scoped routes. Reuse Mission 11 bindings.
  Do not stack on MEL/coordinator PRs. Rebase onto origin/main later
  only after Mission 2 lands, adapting to canonical TenantContext/API.
```

## 6. Which Data Foundation capabilities do not yet exist?

All of the Data Foundation runtime: evidence-requirement compiler, metadata-first discovery, source candidates, four-pillar assessment, quality engine, transformation preview/executor, Drive file-series grouping, `prem3_modeling` provisioning, DF source receipts, `DATA_FOUNDATION_READY`, and workspace-scoped service routes.

Business IQ persistence (`REQ-012`–`018`) also does not exist. This branch consumes a typed snapshot/fixture only.

## 7. Exact server-side authority assumptions

- Tenant is resolved from a verified Clerk credential via `authenticated_tenant`. Never from body/query/path/headers/cookies.
- Workspace is authorized by `authorized_workspace` against Firestore/control-plane ownership.
- Physical GCP project, `prem3_modeling` dataset, and Drive root folder ID come from stored bindings, not caller input.
- Google subject/email is never a PreM3 tenant.
- Mutating DF tools accept IDs only (`foundation_plan_id`, `transformation_plan_id`, `source_id`, `finding_id`).
- Discovery access ≠ foundation-management access. OAuth success ≠ `DISCOVERY_READY`. Write verification is required for `PROVISIONING_READY`.
- Drive OAuth `drive.file` is not folder-level enforcement. Server-side `root_folder_id` is.

## 8. What dependencies must be added?

None for the P0 vertical slice. CSV/Parquet already work via pandas/pyarrow. XLSX uses pandas; if `openpyxl` is absent, XLSX parse fails closed with a typed finding rather than a silent skip.

No new Google client libraries. DF adapters wrap existing integrations and an in-memory warehouse for deterministic proof.

## 9. What existing tests guard behavior we must preserve?

- `tests/unit/test_profiling.py`
- `tests/unit/test_remediation.py`
- `tests/unit/test_provenance.py`
- `tests/unit/test_registry.py`
- `tests/unit/test_bigquery_inspect.py`
- `tests/unit/test_prem3_import_ready.py`
- `tests/unit/test_prem3_drive_governance.py`
- `tests/unit/test_prem3_bigquery_governance.py`
- `tests/unit/test_tenancy_context.py`
- `tests/unit/test_execution_authority.py`
- Dataset A / `MODEL_READY` / Meridian regression tests

## 10. Branch base confirmation

`feature/prem3-data-foundation-backend` was created from `02cec50`. It is 25 commits ahead of `origin/main` and 0 commits behind that Mission 11 HEAD. `feature/prem3-data-foundation-backend` did not exist before this review.
