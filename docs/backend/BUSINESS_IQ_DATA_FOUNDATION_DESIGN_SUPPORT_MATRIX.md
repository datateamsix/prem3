# Design Support Matrix — Business IQ + Data Foundation

**Design freeze:** `foundational-intake-freeze-2026-08-22-v1`  
**Mockups:** `docs/mockups/business-iq-data-foundations-front-end-mock-ups/`  
**Frozen specs:**
- `uploads/PROMPT_PREM3_DATA_FOUNDATION_FINAL_DESIGN_REFINEMENT_SPEC.md` (`FINAL §n`)
- `uploads/PROMPT_BUSINESS_IQ_FINAL_REFINEMENT_AGENTIC_INSIGHTS.md` (`BIQ-REF §n`)
- `Business IQ Intake.dc.html` / `Data Foundation v2.dc.html`

**Branch:** `feature/prem3-data-foundation-backend`  
**P0 rule:** every data-bearing frozen capability must end as `IMPLEMENTED` or `EXTERNAL_DEPENDENCY`. Zero `MISSING` P0 rows.  
**Omission rule:** a Frozen ref column is required on every row. A capability that is not listed cannot be counted as covered.

Status values: `IMPLEMENTED` | `PARTIAL` | `MISSING` | `EXTERNAL_DEPENDENCY`

Readiness naming (locked):

| Public state | Owner | Emitter |
|---|---|---|
| `IMPORT_READY` | M2-11 import governance | only `evaluate_import_readiness` |
| `FOUNDATION_SOURCE_READY` / `FOUNDATION_SOURCE_NOT_READY` | Data Foundation | only DF deterministic evaluator |
| `DATA_FOUNDATION_READY` | Data Foundation (workspace) | only DF deterministic evaluator |
| `BUSINESS_CONTEXT_READY` | Business IQ | only BIQ deterministic evaluator |

Gemini never emits any of these. Non-blocking downstream items are `premodel_review_findings[]`, not a second readiness string.

---

## Business IQ

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| BIQ HTML; BIQ-REF §12–§16 | Durable BusinessProfile (identity, objectives, KPI, economics, markets, journey, portfolio, decision process, drivers, competition, events, facts, relationships, hypotheses, gaps, metadata) | `BusinessProfile` | `BusinessIqStore` — production `FirestoreBusinessIqStore`; CI/local `InMemoryBusinessIqStore` | `GET/POST/PATCH /v1/workspaces/{id}/business-iq/profile` | Deterministic persistence | IMPLEMENTED | `tests/unit/business_iq/test_profile.py` `test_durable_stores.py` |
| BIQ-REF §30 | Custom text preserved (never coerced to OTHER) | `custom_text` / free-string fields | same | PATCH profile | Deterministic | IMPLEMENTED | `test_custom_values_preserved` |
| BIQ-REF §32 | Version increment on material edit | `BusinessProfileVersion` | version log on store | `GET .../profile/versions` | Deterministic | IMPLEMENTED | `test_version_increments` |
| FINAL §20 | Immutable snapshot for later cycles | `BusinessProfileSnapshot` | snapshot collection | `GET .../profile/snapshots/{id}` | Deterministic | IMPLEMENTED | `test_historical_snapshots_unaffected` |
| BIQ-REF §25 | Fingerprint of consumed profile | `fingerprint` SHA-256 | computed on write | profile + snapshot | Deterministic | IMPLEMENTED | `test_fingerprint_changes_on_edit` |
| BIQ-REF §13–§15 | Organization display name / last edited / version | profile metadata + control-plane org | Clerk/control plane name; BIQ timestamps | profile response | Deterministic | IMPLEMENTED | `test_profile_metadata` |
| BIQ-REF §14 | Customer logo | `logo_asset_ref` optional | BIQ metadata only (no binary store) | profile | Deterministic | IMPLEMENTED | `test_profile_metadata` |
| BIQ-REF §25 | Typed BusinessFact + provenance | `BusinessFact` | store | profile payload | Deterministic | IMPLEMENTED | `test_fact_provenance` |
| BIQ HTML channels | MarketingChannel lifecycle + effective dates | `MarketingChannel` `DECLARED/ACTIVE/PAUSED/RETIRED` + `active_from`/`active_to` | store | profile | Deterministic | IMPLEMENTED | `test_channel_lifecycle_dates` |
| BIQ-REF §9–§11 | BusinessEvent / commercial drivers | `BusinessEvent` | store | profile | Deterministic | IMPLEMENTED | `test_events_effective_dates` |
| BIQ HTML relationships | BusinessRelationship / hypothesis | `BusinessRelationship`, `BusinessHypothesis` | store | profile | Deterministic | IMPLEMENTED | `test_relationships_hypotheses` |
| BIQ-REF §29 | KnowledgeGap / UNKNOWN_ACKNOWLEDGED | `KnowledgeGap` | store | profile | Deterministic | IMPLEMENTED | `test_unknown_acknowledged` |
| BIQ-REF §3–§8 | PriorEvidenceReference | `PriorEvidenceReference` | store | profile | Deterministic | IMPLEMENTED | `test_prior_evidence` |
| BIQ-REF §12 | BUSINESS_CONTEXT_READY | `BusinessContextReadyReceipt` | evaluator, not questionnaire % | `GET .../business-iq/ready` | Deterministic only | IMPLEMENTED | `test_business_context_ready` |
| BIQ-REF §21 §25 | Grounded Business Intelligence Brief | `BusinessIntelligenceBrief` | store; cites `BusinessFact` IDs | `GET/POST .../brief` | Advisory; evidence must be structured | IMPLEMENTED | `test_brief_cites_facts` |
| BIQ-REF §19 §26 | Brief cannot mutate profile or set readiness | same | service rejects write-through | brief regenerate | Deterministic guard | IMPLEMENTED | `test_brief_is_advisory` |
| BIQ-REF §21 | Gemini-authored BIQ brief prose | same sections; agent text optional | Gemini | not required for P0 | Agentic P1 | EXTERNAL_DEPENDENCY | n/a — structured brief is the P0 contract |
| FINAL §51 | BusinessProfileUpdateProposal | `BusinessProfileUpdateProposal` | store | `GET/POST .../proposals` accept/reject | Deterministic apply | IMPLEMENTED | `test_proposal_accept_reject` |
| FINAL §20 | DF cannot silently mutate BIQ | proposal-only writes | service | proposals | Deterministic | IMPLEMENTED | `test_df_cannot_silent_mutate` |

---

## Measurement Cycle

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §20–§21 | MeasurementCycle create/list/get/update | `MeasurementCycle` | `FirestoreDataFoundationStore` / InMemory | `/v1/workspaces/{id}/data-foundation/cycles` | Deterministic | IMPLEMENTED | `tests/unit/data_foundation/test_cycle.py` `test_durable_stores.py` |
| FINAL §21 | Cadence enum | `MONTHLY/QUARTERLY/SEMIANNUAL/ANNUAL/EVENT_BASED/ONE_TIME/CUSTOM/UNKNOWN` | cycle | same | Deterministic | IMPLEMENTED | `test_cycle_cadence` |
| FINAL §21 | Data cutoff + origin | `data_cutoff`, `DETECTED` / `USER_SELECTED` | cycle | same | Deterministic | IMPLEMENTED | `test_data_cutoff` |
| FINAL §21 §102 | Provisional target window | `PROVISIONAL` / `CONFIRMED_DOWNSTREAM` | cycle | same | Deterministic; DF never finalizes model window | IMPLEMENTED | `test_provisional_window` |
| FINAL §20 | Pinned BusinessProfile snapshot | `business_profile_snapshot_id` | cycle + BIQ snapshot | same | Deterministic; no silent replace | IMPLEMENTED | `test_cycle_pins_snapshot` |
| FINAL §21 | CONFIRMED_DOWNSTREAM reproducibility lock | snapshot, cutoff, target window immutable in place | cycle | PATCH rejected; `POST .../cycles/{id}/revise` | Deterministic | IMPLEMENTED | `test_confirmed_cycle_is_immutable_and_revise_creates_new_cycle` |
| FINAL §21 | Revision / new-cycle behavior | `predecessor_cycle_id`, `revision` | store | revise | Deterministic | IMPLEMENTED | same |
| FINAL §21 | Effective-dated requirement compilation | `EvidenceRequirementSet` from snapshot + channel dates | DF compiler | `GET .../cycles/{id}/requirements` | Deterministic | IMPLEMENTED | `test_effective_dated_requirements` |

---

## Connect / discovery

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §7–§11 | BigQuery connection contract + lifecycle | `ConnectionView` + M2-11 `BigQueryWorkspaceBinding` | control plane | inherited Google routes + DF overview | Deterministic | IMPLEMENTED | existing Google + DF API tests |
| FINAL §12–§14 | Drive connection + authorized root | `DriveWorkspaceBinding.root_folder_id` | control plane | inherited | Deterministic; folder ID is authority | IMPLEMENTED | existing Drive tests + DF root tests |
| FINAL §23 | BQ discovery hints / strict scope | `DiscoveryHints.datasets_to_prioritize`, `only_inspect_prioritized_datasets` | DF store | `POST .../discover` | Deterministic | IMPLEMENTED | `test_strict_bq_dataset_boundary` |
| FINAL §52 | Drive hints stay inside bound root | `drive_sources_or_paths_to_prioritize` | DF store | same | Deterministic | IMPLEMENTED | `test_drive_hints_stay_in_root` |
| FINAL §24 | Provider-assisted discovery | `ProviderMatchEvidence` | registry + metadata | discover | Deterministic match; agent may narrate | IMPLEMENTED | existing provider matching tests |
| FINAL §30 | Source scope / geo provenance | `SourceScope` | assessment / candidate | source detail | Filename inference < schema/profile | IMPLEMENTED | `test_source_scope_provenance` |
| FINAL §23 §30 | Physical metadata (BQ table) | `PhysicalMetadata` | adapter + warehouse | source detail | Deterministic | IMPLEMENTED | `test_physical_metadata_table` |
| FINAL §23 | Physical metadata (BQ view) | same; no claimed partition/clustering | adapter | source detail | Deterministic | IMPLEMENTED | `test_view_metadata_no_partition_claim` |
| FINAL §52–§54 | Drive logical-source metadata | file_count, rows, schema versions, date range | DF store | source detail | Deterministic | IMPLEMENTED | `test_drive_physical_metadata` |
| FINAL §23 | Row counts exact vs estimated | `row_count_kind` | adapter | source detail | Deterministic | IMPLEMENTED | `test_exact_vs_estimated_row_count` |
| FINAL §22–§23 | Real BQ runtime adapter | `BigQueryRuntime` / REST client | Google APIs via M2-11 OAuth | discovery, preview, provision | Deterministic | IMPLEMENTED | unit fakes + adapter contract tests |
| FINAL §12 §52 | Real Drive runtime adapter | `DriveRuntime` / REST client | Google APIs via M2-11 OAuth | inventory, preview, ingest | Deterministic | IMPLEMENTED | unit fakes + adapter contract tests |
| FINAL §7 | Live authorized-project proof | same | customer GCP | n/a | n/a | EXTERNAL_DEPENDENCY | proof field `LIVE_CLOUD_PROOF_NOT_RUN` |

---

## Drive foundation (frozen file plane)

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §13–§15 | Drive root creation / canonical children | `DriveFoundationLayout` | DF store | `POST/GET .../drive/layout` | Deterministic; bound root is authority | IMPLEMENTED | `test_drive_layout_is_idempotent_under_bound_root` |
| FINAL §16–§19 §53 | File registration + fingerprints | `DriveFileRecord.file_fingerprint` | DF store | register + series | Deterministic SHA-256; raw immutable | IMPLEMENTED | `test_same_fingerprint_identity_and_rename_is_non_destructive` |
| FINAL §27 §52 | File-series grouping | `FileSeriesCandidate` | grouping engine | `GET .../file-series` | Deterministic membership | IMPLEMENTED | `test_file_series_grouping_is_deterministic` |
| FINAL §55 | Unclassified classification | slug `custom_unclassified` | grouping | file-series | Deterministic; never coerced to OTHER | IMPLEMENTED | `test_unclassified_files_group_under_custom_unclassified` |
| FINAL §16–§18 | Canonical logical naming | `canonical_logical_name` | naming | register | Deterministic; rename is non-destructive | IMPLEMENTED | `test_same_fingerprint_identity` `test_slug_rejects_other` |
| FINAL §92 | Drive→BQ ingestion + receipt | `DriveImportReceipt` | warehouse + store | `POST .../sources/{id}/materialize-drive` | Deterministic; raw files unmodified | IMPLEMENTED | `test_drive_ingest_writes_receipt_without_mutating_raw` |
| FINAL §56–§58 | Drive/BQ source convergence | `CrossSourceAlignmentAssessment` | alignment engine | `GET .../alignment` | Deterministic observations | IMPLEMENTED | `test_add_source_and_drive_bq_alignment` |

---

## Quality, preview, coverage

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §31–§45 | Deterministic quality | `SourceAssessment` / `DF-Q*` | quality engine | `POST .../sources/{id}/assess` | Deterministic | IMPLEMENTED | existing quality tests |
| FINAL §64 §44 | QualityOverview aggregate | `QualityOverview` | `overview_from_assessment` | `GET .../sources/{id}/quality-overview` | Deterministic counts + findings | IMPLEMENTED | `test_quality_overview_is_deterministic_aggregate` |
| FINAL §67 | Safe Data Preview (source) | `DataPreview` `SOURCE_PREVIEW` | compiled SQL / parsed rows | `GET .../sources/{id}/preview` | Deterministic | IMPLEMENTED | `test_preview.py` |
| FINAL §67 | 5 most recent only if verified time field | same | preview compiler | same | Deterministic | IMPLEMENTED | `test_recent_requires_verified_time` |
| FINAL §67 | Else 5 sample rows (not “most recent”) | same | preview compiler | same | Deterministic | IMPLEMENTED | `test_sample_when_no_time_field` |
| FINAL §49 | Mask emails/phones/names/addresses/IDs | `masked_fields[]` `omitted_fields[]` | field-safety policy | same | Deterministic | IMPLEMENTED | `test_sensitive_masking` |
| FINAL §23 | No SELECT * / no caller SQL | `QueryBudgetPolicy` | compiler | same | Deterministic | IMPLEMENTED | existing query-budget tests + preview |
| FINAL §67–§74 | Transformation Preview contract | `TransformationPreview` | transform preview | existing + expanded | Deterministic | IMPLEMENTED | `test_transformation_preview_contract` |
| FINAL §72 | USER_REQUIRED not presented as applied | same | preview | same | Deterministic | IMPLEMENTED | existing transform tests |
| FINAL §80 | Canonical Preview | `CanonicalPreview` | warehouse + receipt | `GET .../canonical-preview` | Deterministic | IMPLEMENTED | `test_canonical_preview` |
| FINAL §59 | Coverage & Continuity | `CoverageAssessment` / `CoverageSeries` / `CoverageBucket` | coverage engine | `GET .../cycles/{id}/coverage` | Deterministic | IMPLEMENTED | `test_coverage.py` |
| FINAL §59 | Bucket states (present / valid zero / missing / not expected / …) | `CoverageBucketState` | engine | same | Deterministic | IMPLEMENTED | `test_valid_zero_vs_missing` `test_not_expected_before_launch` |
| FINAL §59 | REQUIRED_EVIDENCE vs ALL_SOURCES | `view=` | engine | same | Deterministic | IMPLEMENTED | `test_coverage_views` |
| FINAL §57 | Source transitions + unreconciled overlap | `SourceContinuityPlan` | store | coverage | Deterministic | IMPLEMENTED | `test_source_transition_overlap` |
| FINAL §57–§58 | Shared continuous window + limiting source | `CoverageSummary` | engine | `GET .../cycles/{id}/shared-window` | Deterministic | IMPLEMENTED | `test_shared_window_limiting_source` |
| FINAL §59 | Gap detail | `CoverageGap` | engine | `GET .../coverage/gaps/{id}` | Deterministic | IMPLEMENTED | `test_gap_detail` |
| FINAL §50–§51 | Gap → clarification → proposal | `BusinessClarificationRequest` → `BusinessProfileUpdateProposal` | BIQ store | `POST .../clarifications` | Deterministic apply; agent may phrase question | IMPLEMENTED | `test_gap_clarification_proposal` |
| FINAL §43 §98 | Continuous health/drift | existing drift family + reassessment | quality engine | assess | Deterministic | IMPLEMENTED | existing drift tests |

---

## Data Intelligence Brief

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §65 | Frozen DataIntelligenceBrief (five sections) | `DataIntelligenceBrief` + `IntelligenceBriefSection` | DF store | `GET/POST .../intelligence-brief` | Grounded structured content is P0 | IMPLEMENTED | `test_intelligence_brief.py` |
| FINAL §65 §25 | Evidence references | `evidence_refs` + per-section refs | quality/coverage IDs | same | Deterministic citations | IMPLEMENTED | `test_data_intelligence_brief_cites_structured_evidence` |
| FINAL §65 §48 | Gemini prose for the brief | optional narration over the same sections | Gemini | not required for P0 | Agentic P1 | EXTERNAL_DEPENDENCY | structured compiler is the freeze contract |

---

## Foundation Plan

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §75 | Foundation Plan compile | `FoundationPlan` | DF store | `POST .../plans` | Deterministic | IMPLEMENTED | existing provisioning tests |
| FINAL §76–§81 | Five plan domains | `FoundationPlanSection` × 5 on `domains` | planner | same | Deterministic | IMPLEMENTED | `test_foundation_plan_covers_five_domains_and_will_not_modify` |
| FINAL §82 | Resource action classes | `PlanActionKind` `REUSE/CREATE/CHANGE/CUSTOMER_MANAGED` | planner | same | Deterministic | IMPLEMENTED | same + existing reuse tests |
| FINAL §84 | Permission preview | `permission_preview` + per-action `permission_requirements` | planner | same | Deterministic | IMPLEMENTED | same |
| FINAL §83 | Will-not-modify | `will_not_modify` | planner | same | Deterministic | IMPLEMENTED | same |
| FINAL §85 | Fingerprint-bound approval | `FoundationApproval` | store | `POST .../plans/approve` | Deterministic | IMPLEMENTED | existing |
| FINAL §86 | Partial approval + dependencies | `approved_sections`; action `dependencies` | executor | approve `sections` + execute | Deterministic skip/wait | IMPLEMENTED | `test_partial_approval_skips_unapproved_sections_and_dependencies` |
| FINAL §85 | Material-change reapproval | fingerprint mismatch / superseded | execute | execute | Deterministic fail-closed | IMPLEMENTED | `test_material_plan_change_requires_reapproval` |
| FINAL §87 | Deterministic execution | provision + transform executors | warehouse / runtime | `POST .../plans/execute` | Deterministic | IMPLEMENTED | existing |
| FINAL §91–§93 | Receipts | source / transform / provision / foundation | store | `GET .../receipts` | Deterministic | IMPLEMENTED | existing + readiness tests |

---

## Readiness (locked; not redesigned)

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §89 | FOUNDATION_SOURCE_READY | `SourceFoundationReceipt` | DF evaluator | `POST .../sources/{id}/ready` | Deterministic; consumes M2-11 `IMPORT_READY` | IMPLEMENTED | `test_pipeline.py` `test_readiness_names.py` |
| FINAL §89 | premodel_review_findings (not a readiness string) | `premodel_review_findings[]` | receipt | same | Deterministic | IMPLEMENTED | `test_premodel_findings_not_readiness` |
| FINAL §90 §95 | DATA_FOUNDATION_READY | `DataFoundationReadyReceipt` | DF evaluator | `POST .../ready` | Requires M2-11 `IMPORT_READY` + `FOUNDATION_SOURCE_READY` where applicable | IMPLEMENTED | `test_pipeline.py` |
| FINAL §89 | M2-11 IMPORT_READY unchanged | `ImportReadinessReceipt` | `evaluate_import_readiness` | existing import-governance routes | Deterministic M2-11 only | IMPLEMENTED | existing import-ready tests |
| FINAL §62 | DV360 contract / capability / PREREQUISITE_REQUIRED | `PrerequisiteNotice` + plan `CUSTOMER_MANAGED` | planner | foundation plan | Deterministic truthful state | IMPLEMENTED | existing DV360 prerequisite tests |
| FINAL §62 | Live DTV2 provisioning proof | same | authorized test project | n/a | n/a | EXTERNAL_DEPENDENCY | proof + adapter matrix |

---

## Operate phase

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| FINAL §99 | Reauthorization | reassess + re-evaluate | quality + readiness | `POST .../sources/{id}/reauthorize` | Deterministic | IMPLEMENTED | `test_reauthorize_and_health_retrieval` |
| FINAL §97 §100 | Source replacement | retire prior + bind replacement + continuity plan | bindings + transitions | `POST .../sources/{id}/replace` | Deterministic | IMPLEMENTED | `test_replace_source_retires_prior_and_binds_replacement` |
| FINAL §97 §100 | Add source / provider | `bind_source` | candidates + bindings | `POST .../sources` | Deterministic | IMPLEMENTED | `test_add_source_and_drive_bq_alignment` |
| FINAL §97 | Retirement | `lifecycle_state=RETIRED` | binding | `POST .../sources/{id}/retire` | Deterministic | IMPLEMENTED | `test_retire_degrades_source_readiness` |
| FINAL §96–§98 | Health retrieval | assessment + `QualityOverview` + source receipt | store | `GET .../sources/{id}/health` | Deterministic | IMPLEMENTED | `test_reauthorize_and_health_retrieval` |
| FINAL §98–§101 | Readiness degradation / re-evaluation | RETIRED cannot stay `FOUNDATION_SOURCE_READY`; workspace re-eval excludes retired | readiness evaluator | retire / reauthorize / ready | Deterministic; locked model unchanged | IMPLEMENTED | `test_retire_degrades_source_readiness` |

---

## Durable production backing

| Frozen ref | UX capability | Backend contract | Source of truth | API/service | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|---|
| control-plane reuse | Production Business IQ store | `FirestoreBusinessIqStore` | Firestore via control-plane client | `build_product_stores` | Deterministic | IMPLEMENTED | `test_durable_stores.py` |
| FINAL §75 §91–§93 | Production DF store for cycles, bindings, plans, findings, receipts | `FirestoreDataFoundationStore` | Firestore | same | Deterministic | IMPLEMENTED | `test_durable_stores.py` |
| CI/local | InMemory remains CI/local | `InMemory*` | process memory | `create_app` when repo is not Firestore | Deterministic | IMPLEMENTED | `test_inmemory_control_plane_keeps_inmemory_product_stores` |

---

## External dependencies (explicit, not MISSING)

| Frozen ref | Dependency | Why P0 is not live-proven | Status |
|---|---|---|---|
| FINAL §7 | Authorized customer GCP project + OAuth tokens for live BQ/Drive I/O | Adapters and contracts exist; this environment has no authorized live proof | `EXTERNAL_DEPENDENCY` |
| FINAL §62 | DV360 / DTV2 first-party transfer provisioning | Contract + `PREREQUISITE_REQUIRED` are P0; live provision is not | `EXTERNAL_DEPENDENCY` |
| inherited Mission 2 | Live Clerk/Stripe SaaS proofs | Unchanged Mission 2 gap; not invented here | `EXTERNAL_DEPENDENCY` |
| FINAL §65 / BIQ-REF §21 | Gemini-authored brief prose | Grounded structured brief is P0; agent narration is P1 | `EXTERNAL_DEPENDENCY` |

## Authority invariants

- Tenant never from body/query/path/headers/cookies.
- Clerk/Stripe/Google subject is never PreM3 tenant.
- No tool accepts tenant, workspace, dataset, storage path, BQ destination, plan, or entitlement as model-supplied authority.
- Raw input immutable. Missing ≠ zero. Agent recommends; deterministic code proves.
- `IMPORT_READY` ≠ `FOUNDATION_SOURCE_READY` ≠ `DATA_FOUNDATION_READY` ≠ `MODEL_READY` ≠ `PUBLISH_READY`.
