# M2-12 UI / backend support matrix

Design freeze reference: `foundational-intake-freeze-2026-08-22-v1`  
PR #15 is merged. Mission 12Q consumes canonical `SourceBinding` / `SourceFoundationReceipt` / `EvidenceRequirement` through `CanonicalFoundationSourceGate`. It does not replace Business IQ or Data Foundation intake.

No UI field below requires parsing narrative prose to determine authority.

| UI concept | Backend contract field | Source of truth | API response | Deterministic owner |
|---|---|---|---|---|
| Source provider | `SourceMaterializationResponse.provider` / `source_objects[].provider` | Import Contract role assignment; optional DF compatibility evidence | `GET/POST .../materializations` | Import governance compile + optional `FoundationSourceGate` |
| Source role / business requirement | `business_role` / `source_objects[].role` | Import Contract `RoleAssignment`; optional DF `business_role` | materialization response | Import Contract; DF evidence when present |
| Source identity | `source_objects[].source_identity` | Frozen `PreM3ImportContractV1` object | materialization response | Import Contract |
| Source version | `source_version` / `source_objects[].version_identity` | Live provider metadata revalidated against the Import Contract | materialization response | Import compile + M2-12 revalidation |
| Foundation source state | `foundation_source_state` | Canonical `SourceFoundationReceipt.status_code` or omitted when not DF-managed | materialization response | `DataFoundationStore` via `CanonicalFoundationSourceGate` |
| Import governance state | `import_governance_state` | Current `ImportReadinessReceipt.status` | materialization response | `evaluate_import_readiness` |
| Pre-model review | `premodel_review_remaining`, `premodel_review_findings` | DF compatibility evidence; never resolved by M2-12 | materialization response | Data Foundation |
| Materialization state | `materialization_state` | `SourceMaterializationReceipt.status` | materialization response | `MaterializationService` |
| DatasetUpload ID | `upload_id` | Control-plane `DatasetUpload` | materialization response | `UploadService` |
| Upload status | `upload_status` | `DatasetUpload.status` | materialization response | `UploadService.complete_upload` |
| Immutable input fingerprint | `upload_package_fingerprint` | Verified upload package fingerprint | materialization response | `UploadService` |
| History / refresh / grain / geography / metrics | `history`, `refresh_cadence`, `freshness`, `grain`, `geography`, `metrics` | Optional DF compatibility evidence only | materialization response | Data Foundation (when present) |
| MODEL_READY | `PublishReadinessReceiptResponse.model_ready_fingerprint` + evaluation/run evidence | `ModelReadyEvidenceResolver` | `POST/GET .../publish-readiness` | Existing pre-modeling pipeline; M2-12 reads only |
| Publish readiness | `PublishReadinessReceiptResponse.status` | `evaluate_publish_readiness` | publish-readiness routes | Publish governance evaluator |
| Destination status | `PublishExecutionResponse.destination_results[].status` | Per-destination write + readback | publish execution routes | `PublishExecutionService` |
| Published artifact identity | `destination_results[].artifacts_verified[].identity` and BQ `versioned_resource_identity` | Drive file IDs / BQ table IDs after readback | publish execution routes | Publish execution |
| Current model-ready pointer | `destination_results[].stable_pointer_identity` | BQ view `model_ready_{dataset}_current` after versioned table verifies | publish execution routes | Publish execution |
| Publish verification | `readback_verified`, `write_completed`, overall `status` | Destination readback | publish execution routes | Publish execution |

## Presentation rules

- GCS package URIs, OAuth tokens, Firestore paths, and bucket internals are not returned.
- `IMPORT_READY` is never inferred from `FOUNDATION_SOURCE_READY` or the reverse.
- `MODEL_READY` is never inferred from Evaluation `ACCEPTED` or `COMPLETE`.
- `PUBLISH_READY` is never inferred from `MODEL_READY`.
- `PUBLISHED` / `COMPLETE` is never inferred from `PUBLISH_READY`.
