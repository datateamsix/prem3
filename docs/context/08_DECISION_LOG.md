# Decision Log

## 2026-08-13 — Track
**Decision:** Target Taskmaster.

**Why:** ModelReady is naturally event-driven, autonomous, multi-system and artifact-producing.

---

## 2026-08-13 — Product
**Decision:** Primary entry is ModelReady.

**Positioning:** Autonomous pre-modeling data operations for marketing measurement.

---

## 2026-08-13 — First modeling target
**Decision:** Google Meridian.

**Why:** Strong challenge/domain fit, open source, Google-native, objective input requirements.

---

## 2026-08-13 — Canonical interoperability
**Decision:** Align output to Google's MMM Unified Schema where practical rather than inventing a competing universal schema.

**Why:** Interoperability and stronger Google-native architecture.

---

## 2026-08-13 — Learning
**Decision:** Experiential learning is P1 hackathon functionality, not post-hackathon roadmap.

**Definition:** prior evaluated episodes must measurably change future execution.

**Safety:** no uncontrolled live self-modification.

---

## 2026-08-13 — Learning architecture
**Decision:** BigQuery is the auditable experience ledger; Vertex AI Memory Bank is retrieval memory; ADK evaluation measures trajectories; ADK optimization is controlled/offline.

---

## 2026-08-13 — Engineering philosophy
**Decision:** LLM decides; deterministic code proves.

---

## 2026-08-13 — Demo
**Decision:** use synthetic ecommerce musical-instrument business data with seeded defects.

**Why:** reproducible, controllable, objective defect ground truth.

---

## 2026-08-13 — Agent naming
**Decision:** The autonomous worker inside ModelReady is the **M3 Agent**.

**Meaning:** **Map. Mend. Model-Ready.**

**Secondary/domain meaning:** Media Mix Modeling.

**Hierarchy:**
- ModelReady = product
- M3 Agent = autonomous worker
- MEL = ModelReady Experience Loop
- M3 Learning Receipt = visible proof of learned/applied experience

---

## 2026-08-13 — Model-ready BigQuery publish
**Decision:** BigQuery publishing is a first-class M3 task, not merely an export option.

**Why:** The strongest Taskmaster endpoint is an operational artifact that is immediately available for model use.

**Required behavior:** After deterministic readiness validation, M3 may autonomously create a versioned BigQuery model-input table/view, write provenance/manifests, generate the Meridian input contract, and verify publish parity.

**Success milestone:** `MODEL_READY`. True terminal stages remain `FAILED` and `COMPLETE`.

---

## 2026-08-15 — MODEL_READY is a success milestone
**Decision:** `MODEL_READY` is a success milestone, not a hard terminal state.

**Why:** Phase 3 learning (`MODEL_READY → LEARNING`) and later Meridian approval (`MODEL_READY → WAITING_FOR_MODEL_APPROVAL`) must remain legal. Failed and completed runs stay terminal.

**Display:** Phase 1 Dataset A scripts still stop showing progress at `MODEL_READY`.

---

## 2026-08-15 — Model consumption tables are partitioned, clustered, and described in DDL
**Decision:** Versioned Meridian model-input tables are created with compiled DDL, not inferred load-job schemas.

**Required physical layout:**
- `PARTITION BY time`
- `CLUSTER BY geo`
- every column has a description in `CREATE TABLE` DDL
- the subsequent load job restates partition, clustering, and descriptions so `WRITE_TRUNCATE` cannot drop them

**Why:** Meridian queries a durable consumption object. Partitioning and clustering keep that object cheap to scan. Column descriptions make the published contract inspectable in BigQuery without reading ModelReady source.

**Fail closed:** a destination that exists with the right rows but the wrong physical type, missing descriptions, or missing partition/cluster cannot become `MODEL_READY`.

---

## 2026-08-13 — Meridian execution authority
**Decision:** M3 may prepare the full Meridian execution handoff, but launching a Meridian posterior / fitted model remains approval-gated. Autonomous official pre-modeling EDA is required and is not that launch.

**Why:** Model configuration choices can materially affect model behavior and interpretation. Operational autonomy should not silently expand into model-governance authority. Pre-modeling EDA uses official `EDASpec()` and may call `sample_prior` only for diagnostics.

**Stretch architecture:** Cloud Workflows + Colab Enterprise, aligned with the official Cortex for Meridian pattern.

---

## 2026-08-15 — CLOUD_TASKMASTER five-tool operational API
**Decision:** The deployed M3 agent executes Dataset A through five run-level tools. Gemini selects issue IDs; deterministic plans supply transform parameters. Durable run state lives in the artifact GCS bucket, not in RAM or `/tmp`.

**Why:** Judges must see that M3 did not invoke a monolithic preprocessing script. Eventarc, MEL, Dataset B/C, and Meridian execution remain out of scope until this path is proven.

---

## 2026-08-15 — Official Meridian EDA is deterministic compute, not a second agent
**Decision:** M3 remains one Taskmaster worker. Pre-modeling EDA uses the published `google-meridian==1.8.0` package. Gemini interprets structured `EDAFinding` objects; it does not calculate EDA metrics or override ERROR/ATTENTION/INFO.

**Runtime:** Measured Option B. Official install docs require Python 3.11 or 3.12. The M3 ADK service is Python 3.13 with pandas 3.0.x. Installing Meridian 1.8.0 would downgrade pandas to 2.x and pull TensorFlow 2.21. EDA therefore runs in a dedicated worker interpreter, not inside the ADK Cloud Run image.

**Priors:** MeridianEDA may call `sample_prior` for prior-probability diagnostics. That context is recorded as `MERIDIAN_DEFAULT` / `EDA_PRIOR_DIAGNOSTICS_ONLY` / `approved_for_final_modeling=false`. `sample_posterior` is forbidden.

**Gate:** Any official ERROR finding is `EDA_BLOCKED` and cannot become `MODEL_READY`. ATTENTION sets `review_recommended=true` without blocking. Passing EDA is `PRE_MODELING_COMPLETE`. `MODEL_READY` requires that EDA gate.

**Official parameters:** Deterministic tools persist and evaluate official Meridian `ModelSpec.knots` (not a homemade `n_knots` constructor) plus `check_data_param_ratio` scalars: `n_geos`, `n_times`, `n_knots`, `n_controls`, `n_treatments`, `n_parameters`, `n_data_points`, and `ratio`. Gemini interprets those values; it does not calculate them. EDA-only `knots < n_time` for geo-invariant time-only controls is disclosed and `approved_for_final_modeling=false`.

**Stage:** The only added run stage is `EXPLORING` (`PUBLISHING → EXPLORING → MODEL_READY`). ERROR / ATTENTION / INFO remain the official Meridian severities.

**Runtime isolation:** Do not install `google-meridian` into the M3 ADK Cloud Run image. Production EDA runs in Cloud Run Job `MODELREADY_EDA_JOB` on Python 3.12 with `google-meridian==1.8.0`.

**Idempotency:** `run_id + model_input_fingerprint + meridian_version + eda_config_fingerprint`. The EDA config fingerprint includes the trusted EDA-only ModelSpec policy. A data-dependent `knots=n_time-1` compatibility event is persisted as `EDA_MODEL_SPEC_COMPATIBILITY_ADJUSTMENT` and is not approved for final modeling.

**User resolution:** Official Meridian input rejection or ERROR findings produce a `USER_REQUIRED` resolution pack (`agent_can_fix=false`). Official Meridian text is stored separately from M3 interpretation. ATTENTION remains non-blocking with `review_recommended=true`.

---

## 2026-08-16 — Pre-modeling golden hardening

**Decision:** Official Meridian EDA is part of autonomous pre-modeling. The package executes only in an isolated Cloud Run Job. EDA-only prior sampling does not authorize model priors. `MODEL_READY` requires zero official ERROR findings. Non-agent-fixable EDA/input issues produce `USER_REQUIRED` resolution artifacts. Model fitting and `sample_posterior` remain outside autonomous M3 authority.

**Why:** Judges and users must be able to answer what code, container, Meridian distribution, BigQuery data, and configuration produced `MODEL_READY`, and what happens when Meridian says the data is not suitable.

---
**Decision:** Learning Receipts are first-class product and demo artifacts.

**Types:**
- `EXPERIENCE_LEARNED`
- `EXPERIENCE_APPLIED`

**Why:** They make experiential learning observable and auditable instead of requiring judges/users to trust a claim that the agent "learns."

---

## 2026-08-15 — Product rebrand to PreM3

**Decision:** ModelReady is rebranded as PreM3.

**Canonical positioning:** "A self-learning, autonomous pre-modeling agent for Google Meridian."

**Operating method:** "Map. Mend. Model."

**Reason:** The system now owns the complete pre-modeling assignment rather than only data-readiness evaluation. It maps fragmented inputs, safely mends issues, constructs and independently verifies the model-consumption artifact, executes official Meridian pre-modeling EDA, interprets the findings and creates the modeler handoff.

**M3:** retained as the internal operating concept and natural reference to Media Mix Modeling.

**MEL:** becomes the PreM3 Experience Loop.

**MODEL_READY:** remains the verified operational state.

**Technical identifiers:** existing `modelready-m3` and `m3` cloud/runtime identifiers may remain to protect proven infrastructure and historical evidence.

**Modeling authority:** official pre-modeling EDA is autonomous; posterior/model fitting remains outside autonomous authority.

**Repository:** GitHub remote renamed to `datateamsix/prem3`. The Python distribution name remains `model-ready-m3`.

---

## 2026-08-16 — PREM3 INTELLIGENCE MODEL

**Decision:** PreM3 intelligence now consists of three layers:

1. **Product Intelligence** — why PreM3 exists, who it serves, value, proof vs roadmap (`PREM3_PRODUCT_CONTEXT.md`).
2. **MMM Domain Intelligence** — Meridian requirements, MMM best practice, causal reasoning (`PREM3_MMM_BOOT_CONTEXT.md` + specialized Meridian context).
3. **Run Intelligence** — what this user's actual data, diagnostics, official EDA, and open questions prove.

**User-value behavior** is organized around:

**Assess** — identify state, issues, contract readiness, and risk.  
**Advise** — explain official requirements and labeled best practice.  
**Insight** — interpret actual run evidence without converting pattern into causal claim.  
**Guide** — provide a concrete resolution path with an identified actor.

PreM3 computes what the data can establish, advises from source-backed best practice, interprets evidence into insights, and guides users through resolution where additional action is required.

**Authority:** official Meridian rules remain separate from PreM3 heuristics. Parameter-pressure interpretation is advisory and cannot independently block `MODEL_READY`. Missing media is not automatically zero. KPI/control imputation remains approval-gated. Causal roles are not inferred from correlation. Modeling feasibility remains separate from `MODEL_READY`.

**Scope of this decision:** context, contracts, and registry design only. No diagnostic-tool suite, MEL runtime, Eventarc, or `MODEL_READY` gate change.

---

## 2026-08-16 — PreM3 DOMAIN_VIEW

**Decision:** PreM3 will maintain a versioned operational domain view representing the knowledge it is currently justified and authorized to use.

**Key distinction:** memory is stored information; learning requires evaluated experience that changes future behavior.

Promoted experiential lessons may update DOMAIN_VIEW only after evidence, scope, safety and regression gates.

Official Meridian requirements and PreM3 safety policies retain higher authority.

Organization-specific context does not become global domain knowledge. Run facts do not become domain knowledge.

DOMAIN_VIEW v1 is generated from current verified intelligence and contains **0 promoted experiential lessons**. MEL Episode Core and `EXPERIENCE_APPLIED` remain unimplemented.

---

## 2026-08-16 — PreM3 computational + semantic intelligence

**Decision:** After independent BigQuery verification, PreM3 evaluates model-consumption data beyond structural readiness using deterministic pre-EDA diagnostics and dynamic semantic-readiness questions.

Computable questions are answered with tools. Causal/business questions are surfaced to humans. Modeling feasibility remains distinct from `MODEL_READY`. Scope scenarios are read-only. PreM3 pre-EDA findings remain distinct from official Meridian EDA.

**Tools:** `run_pre_eda_diagnostics`, `inspect_modeling_feasibility`, `generate_semantic_readiness_interview`, `simulate_model_scope_scenarios`, `record_semantic_context`.

**Not in this decision:** MEL Episode Core, DOMAIN_VIEW mutation, Eventarc/Ambient, posterior fitting, official Meridian worker changes, or heuristic blocking of `MODEL_READY`.

---

## 2026-08-16 — PREM3 STRUCTURED RESPONSE ARCHITECTURE

**Decision:** PreM3 responses will be generated from typed intelligence into a structured presentation contract governed by `RESPONSE_STYLE_GUIDE`.

The LLM may summarize and explain evidence but may not invent or alter structured truth.

The response architecture is designed for chat, UI rendering, artifact output, and future automated QA.

Response QA is modeled across Accuracy, Semantics, Format, and Consistency. Full automated response evaluation remains a separate workstream.

**Not in this decision:** MEL promotion, DOMAIN_VIEW mutation, the full Agent Output Evaluation Harness, or waiving the outstanding computational/semantic cloud proof.

---

## 2026-08-16 — Docs filename convention and context cleanup

**Decision:** Markdown under `docs/` uses `ALL_CAPS_SNAKE_CASE` filenames. `README.md` is the index-file exception.

Canonical live context paths:

- `docs/context/PREM3_MMM_BOOT_CONTEXT.md`
- `docs/context/PREM3_PRODUCT_CONTEXT.md`
- `docs/context/meridian/MERIDIAN_DATA_PREP_CONTEXT.md`
- `docs/context/meridian/MERIDIAN_ADVISOR_PLAYBOOK.md`
- `docs/brand/PREM3_BRAND_AND_NAMING.md`

Removed one-shot / completed-phase files after human approval: `CURSOR_HANDOFF.md`, `CONTEXT_PACKAGE_NOTES.md`, `CONTEXT_MIGRATION_REPORT.md`, `PREM3_REBRAND_MIGRATION.md`.

Kept phase-named but still operational: `06_EXECUTION_PLAN.md`, `09_RESEARCH_BACKLOG.md`, `12_PHASE1_EVIDENCE_MODEL.md`.

DOMAIN_VIEW v1.0.0 was not regenerated. Provenance paths in the frozen snapshot remain historical.

---

## 2026-08-16 — PREM3 MEL EPISODE CORE + OPERATIONAL LEARNING

**Decision:** Completed assignments become `ExperienceEpisode` records. MEL evaluates experience only after task completion. Candidate lessons have no authority. Promotion is controlled by deterministic evidence, scope, safety, and regression gates. Promoted lessons update versioned DOMAIN_VIEW as data. The first learning cycle caps learned authority at routing/advisory behavior. `EXPERIENCE_APPLIED` requires a later independent behavior change plus correctness proof.

**Implemented:** Episode Core, ExperienceReflection, EDA alignment, CandidateLesson, evaluation, promotion policy, runtime DOMAIN_VIEW registry, synthetic `EXPERIENCE_LEARNED` / `EXPERIENCE_APPLIED` unit proofs, sealed Summit & Pine Dataset C holdout.

**Not proven:** a real Dataset A cloud episode promoting DOMAIN_VIEW v2 and applying that lesson on the sealed holdout.

**Reflection amendment:** `ExperienceReflection` sits between episode and candidate extraction. Reflection has no operational authority. Possible improvements are not lessons. No reflection means no production candidate extraction.

**Not in this decision:** Eventarc/Ambient, Memory Bank, AUTO_SAFE learned policy, final model fit.

---

## 2026-08-16 — PREM3 DATASET B STRIDE & FIELD LEARNING EVIDENCE

**Decision:** Add an independent synthetic Dataset B (Stride & Field) so MEL can evaluate cross-episode evidence against Music Center Dataset A. Dataset B extends the existing Music Center generator helpers in `app.synthetic.mmm` rather than forking a second synthetic stack. Music Center `datasets/music_center/dataset_b/` is retained as a related-schema episode and is not overwritten.

**Implemented:** Deterministic generator `scripts/generate_dataset_b.py`, fixture package, computed expected intelligence/semantic-family manifests, twelve seeded defects distinct from Dataset A, minimal Klaviyo directory stub, optional cross-episode candidate fields, A+B candidate reporting without forced promotion.

**Not proven:** `EXPERIENCE_LEARNED`, DOMAIN_VIEW v2, `EXPERIENCE_APPLIED`, a required reusable lesson, or a cloud Dataset B `MODEL_READY` run.

**Holdout:** Dataset C Summit & Pine is now the hospitality sealed holdout under `datasets/`. Candidate generation must not read holdout episodes.

**Not in this decision:** lowering MEL promotion thresholds, AUTO_SAFE learned policy, Eventarc/Ambient, posterior fitting, rewriting `PREM3_PRODUCT_CONTEXT.md` as if learning occurred.

---

## 2026-08-16 — DATASET C — SUMMIT & PINE SEALED HOLDOUT

**Decision:** Summit & Pine is the independent evaluation assignment for the first experiential-learning proof. It is created and sealed before CandidateLesson promotion. It cannot contribute to candidate generation, evidence sufficiency, promotion, or DOMAIN_VIEW creation. Its DOMAIN_VIEW v1 baseline is recorded before learning. A later v2 execution may prove `EXPERIENCE_APPLIED`.

**Implemented:** Canonical `datasets/` root; hospitality generator `scripts/generate_dataset_c.py` v2.0.0 with seed `20260816`; sealed manifests and expected contracts; local DOMAIN_VIEW v1 baseline; typed `DatasetRole.SEALED_HOLDOUT` / `ReflectionRole.EVALUATION_ONLY` firewalls; `REJECTED_HOLDOUT_INPUT`; future v1/v2 comparison helper `app/mel/holdout_compare.py`; proof `docs/proof/DATASET_C_SUMMIT_AND_PINE_HOLDOUT.md`.

**Not proven:** `EXPERIENCE_LEARNED`, DOMAIN_VIEW v2, `EXPERIENCE_APPLIED`, cloud Dataset C `MODEL_READY`, official Meridian EDA on Summit & Pine.

**Not in this decision:** A+B promotion, DOMAIN_VIEW mutation, designing the holdout around a CandidateLesson, posterior fitting.

---

## 2026-08-16 — FIRST REAL LOCAL LEARNING CYCLE

**Decision:** Run the first controlled A+B → evaluation → at most one `ROUTING_HINT` promotion → sealed Dataset C application test without lowering MEL thresholds. Dataset C remains evaluation-only. Bootstrap DOMAIN_VIEW v1.0.0 stays the repo default. Experiment activation uses a versioned registry.

**Implemented:** Typed `ExpectedBehaviorEffect`; runtime retrieval/application of `ROUTING_HINT` to handoff/presentation order; first-cycle experiment orchestrator (`app/mel/experiment.py`); holdout evaluator (`app/mel/holdout_evaluate.py`); local intelligence assignments for A/B/C; receipts under `experience/` and `evaluation/`.

**Proven locally:** `EXPERIENCE_LEARNED` (`cand-semantic_question_routing-3ebf87fa174b`), DOMAIN_VIEW `1.0.1`, Summit & Pine `EXPERIENCE_APPLIED` (`modeler-questions` rank 2 → 1).

**Not proven:** Cloud Taskmaster `MODEL_READY` for A+B+C on one revision; BigQuery/GCS ledger proof for this cycle; official Meridian EDA on Dataset C.

**Not in this decision:** rewriting `promoted_lessons.yaml` by hand, replacing bootstrap DOMAIN_VIEW, AUTO_SAFE learned policy, final model fit, frontend integration.

---

## 2026-08-17 — DATASET A CLOUD PRE-MODELING GOLDEN

**Decision:** Prove the core PreM3 product on one frozen Cloud Run revision before replicating the local A+B learning cycle in the cloud. Do not relax `MODEL_READY`. Do not rewrite Dataset B into Music Center files.

**Implemented:** Pre-EDA BigQuery fingerprint aligned with publish parity (`coerce_model_frame_types` + `MODEL_READY_COLUMNS`); DOMAIN_VIEW GCS registry still loads v1.0.0; Dataset A Cloud Taskmaster run `m3cloudc5b11fe79553` on revision `modelready-m3-00012-8xq`.

**Proven:** Dataset A Map → Mend → Validate → Publish → Verify → Explore → Interpret → Handoff → `MODEL_READY`. Independent BigQuery readback 524 rows. Official Meridian EDA 1.8.0 with zero ERROR. Dataset B cloud initialize fail-closed on missing Dataset A runtime files.

**Not proven:** Dataset B Map/Mend, Dataset C cloud baseline, cloud EXPERIENCE_APPLIED, BigQuery experience-ledger readback for the learning cycle.

**Not in this decision:** Eventarc, posterior fit, frontend, generalizing `RunCoordinator` onto this frozen revision after Dataset A started.

---

## 2026-08-17 — PROVIDER-AGNOSTIC COORDINATOR

**Decision:** Generalize assignment initialization, source inventory, adapters, and canonical frame compilation so Datasets A, B, and C use the same coordinator. Do not start the controlled A+B→C learning experiment in this mission. Keep DOMAIN_VIEW 1.0.0. Preserve the Dataset A golden Cloud Run revision as historical proof.

**Implemented:** Manifest-driven `SourceInventory`; required/optional source checks from model intent; provider/report adapters; role-based model-frame compiler; generic local runner `scripts/run_cloud_dataset.py`; read-only `RunPresentationBundle`. Dataset A golden issue/output regression remains the non-negotiable local gate.

**Proven locally:** Dataset A 5 AUTO_SAFE / 524×16 / fingerprint `7cfc1515…fe18f` / readiness PASS. Dataset B initializes and maps without Music Center filenames and stops at `WAITING_FOR_APPROVAL`. Dataset C initializes as `SEALED_HOLDOUT` with unchanged package fingerprint. Expected-answer artifacts do not drive runtime behavior. Unit suite 320 passed, 1 skipped.

**Not proven:** New Cloud Run revision; Dataset A cloud generalization regression; Dataset B/C cloud qualification.

**Not in this decision:** CandidateLesson promotion, DOMAIN_VIEW 1.0.1 activation, EXPERIENCE_APPLIED, frontend edits, GCP resource renaming.

---

## 2026-08-17 — PROVIDER-AGNOSTIC COORDINATOR CLOUD QUALIFICATION

**Decision:** PreM3's production coordinator is assignment/manifest-driven rather than Dataset A filename-driven.

**Evidence:** Datasets A, B, and C qualified through one Cloud Run revision `modelready-m3-00013-c4s` (image `sha256:7dffe4904c1a3ce9e2bb7426793954608bb3d3b5c274b2dc592fcefb0246f6d6`, code `1222eb6fcdabec5ea6132347c8b6df2bc907f705`) with DOMAIN_VIEW 1.0.0. Dataset A reproduced golden `MODEL_READY`. Dataset B mapped real Microsoft/TikTok/Amazon sources and stopped on USER_REQUIRED. Dataset C remained `SEALED_HOLDOUT` with unchanged package fingerprint. Historical golden revision `modelready-m3-00012-8xq` was preserved.

**Rationale:** Provider-specific mechanics belong in adapters keyed to provider/report identity. Business identity must not select the runtime algorithm.

**Not in this decision:** controlled A+B→C cloud learning experiment, DOMAIN_VIEW v2, EXPERIENCE_APPLIED, frontend integration, prem3-api.

---

## 2026-08-17 — MISSION 2 TENANCY, SERVICE, AUTH, AND COMMERCIAL MODEL

**Decision:** Canonical Mission 2 architecture is `14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md`, `15_FRONTEND_INTEGRATION_AND_SERVICE_SURFACE.md`, and `16_AUTH_BILLING_AND_ENTITLEMENTS.md`. Contract requests live in `docs/contracts/BACKEND_REQUESTS.md`. Runtime code is not changed by this decision.

**Locked:**

1. `prem3-api` is the authenticated service boundary; official Meridian EDA remains an isolated Cloud Run Job.
2. Tenant identity is request-scoped application state resolved from a verified Clerk credential. Workload identity (`11_ADK_RUNTIME_IDENTITY_MODEL.md`) remains separate. Clerk/Stripe provider IDs are mapped attributes, never storage keys.
3. Customer hierarchy is Organization (`tenant_id`) → **MMM Project** (`workspace_id`) → **Dataset** (`dataset_id`) → **Evaluation Run** (`run_id`).
4. Commercial packaging is monthly Planner / Project / Portfolio / Enterprise with 0 / 1 / 10 / 50 active MMM Project capacity. `max_active_projects` is the commercial gate.
5. Paid plans include unlimited re-evaluations; commercial access is not metered by `run_id`. Operational abuse/concurrency/compute controls remain separate.
6. Public PreM3 Planner is deterministic/local-static. It performs no PreM3/GCP execution at anonymous runtime, does not receive `TenantContext`, and does not require a backend anonymous session. The earlier anonymous planning-session / claim-handshake requirement is **SUPERSEDED**.
7. Planner conversion creates or selects an authenticated MMM Project only after identity and capacity checks. Imported Planner fields are candidate/unconfirmed until backend provenance confirms them.
8. Clerk Organizations support identity. PreM3 issues its own `tenant_id`. Workspace and Dataset remain PreM3-owned. Clerk user/org provisioning must **not** auto-create a paid MMM Project; project creation is explicit and capacity-gated.
9. Entitlements ship before inline billing logic. Stripe monthly Checkout + Customer Portal + webhook projection are Mission 2 deliverables. Stripe is source of truth for subscription state; PreM3 stores the entitlement projection.
10. Customer-facing completion term is **Meridian Integration**. Legacy internal `handoff_*` evidence names may remain where renaming proven contracts adds risk.
11. Frontend is contract-first: OpenAPI/JSON Schema → generated TS/client → CI drift failure.
12. Planning reports are machine-contract-first. Exact `PlanningReportV1` must be frozen in a future `18_PLANNING_ENGINE_AND_REPORT_CONTRACT.md` before final plan-detail integration. Public Planner brief ≠ `COLLECTION_READY` ≠ `MODEL_READY`. Import/publish governance is `17_IMPORT_AND_PUBLISH_GOVERNANCE.md`.
13. **Firestore** is the Mission 2 operational control-plane store for tenant/provider mappings, membership projections, projects, datasets, entitlements, billing projections, webhook idempotency records, and tenant registry overlay metadata. GCS retains artifacts/uploads; BigQuery retains model-consumption and the experience/ops ledger.

**Deferred, with trigger:**

| Deferred | Trigger |
|---|---|
| Per-tenant GCP projects / service accounts | Enterprise isolation that IAM cannot meet with application enforcement |
| CMEK | Customer-managed encryption requirement |
| Data residency / region pinning | Contractual residency requirement |
| SSO / SAML / SCIM | Enterprise identity procurement |
| Usage-based / per-Evaluation billing | Explicit commercial-model change |
| Annual pricing | Plan-catalog expansion |
| Cross-tenant project sharing | Explicit product requirement |
| Destructive downgrade automation | Only after a non-destructive archive/slot policy is specified and tested |

**Not in this decision:** runtime `prem3-api`, Clerk/Stripe wiring, Firestore schema implementation, planning compiler, or replacing the ADK/CLI golden path.

---

## 2026-08-17 — MISSION 2 BACKEND INTEGRATION BASELINE

**Decision:** Combine the Mission 2 architecture baseline, REQ-001 generated-contract export, PR #9 first-real-learning-cycle runtime, and PR #10 provider-agnostic coordinator onto one local branch without merging those PRs or rewriting their remote history.

**Implemented:** Cherry-pick of the six unique #9 commits then the two unique #10 commits onto `ff3c2f7`. `.gitattributes` keeps both `contracts/schema/*.json` and `datasets/**/*.csv` LF rules. Decision-log product proof from #9/#10 is preserved beside the Mission 2 architecture lock. Contract schemas regenerated from live models: `DurableRunState` gained `repaired_relpaths` / `dataset_role` / `qualification_mode`; `DomainViewClaim` gained `applicability_conditions`. `ExpectedBehaviorEffect`, `CandidateLesson`, `SourceInventory`, and `RunPresentationBundle` stay outside the public export roots.

**Not proven:** New Cloud Run revision; new cloud learning-cycle proof; Dataset B/C `MODEL_READY`; runtime `prem3-api` / tenancy / Firestore.

**Not in this decision:** TenantContext, WorkspaceContext, Clerk, Stripe, FastAPI, frontend product behavior, fixture hash regeneration.

---

## 2026-08-17 — REQUEST-SCOPED TENANT AND WORKSPACE AUTHORITY

**Decision:** Tenant identity is request-scoped application state. Workload identity remains Cloud Run/ADC. New Mission 2 object prefixes are assembled in one module. Legacy golden paths stay explicit.

**Implemented:** `TenantContext` / `WorkspaceContext` ContextVar binding; fail-closed `require_tenant()` / `require_workspace()`; identifier validation; Mission 2 artifact/raw/registry prefixes; `legacy_run_artifact_prefix()`; CLI-only `bind_developer_bootstrap()`. No ANONYMOUS auth state. Public Planner still has no TenantContext.

**Not implemented:** RunRepository migration, ADK tool-schema authority strip, Firestore, prem3-api, Clerk, Stripe, entitlements, historical GCS migration.

**Not in this decision:** expanding REQ-001 public roots with TenantContext/WorkspaceContext.

---

## 2026-08-17 — FIRESTORE OPERATIONAL CONTROL PLANE

**Decision:** Firestore Native `(default)` in `us-central1` is the Mission 2 operational control-plane store. PreM3 issues `tenant_id` / `workspace_id` / `dataset_id`. Provider IDs are mapped attributes only.

**Implemented:** `app/control_plane/` models + `ControlPlaneRepository` protocol; `InMemoryControlPlaneRepository`; `FirestoreControlPlaneRepository`; Planner/Project/Portfolio/Enterprise capacity; immutable entitlement snapshots; webhook claim state machine; optional `scripts/qualify_firestore_control_plane.py`.

**Deferred:** archive/reactivate slot semantics; full tenant deletion job; REQ-014 evaluation history API; registry overlay runtime (REQ-015); FastAPI/`prem3-api`; Clerk/Stripe SDKs; runtime SA `roles/datastore.user` grant.

---

## 2026-08-17 — PREM3-API CONTRACT FREEZE

**Decision:** `prem3-api` is a FastAPI application factory with injectable `ControlPlaneRepository`, `IdentityVerifier`, and `BillingGateway`. Default adapters fail closed. OpenAPI is generated and CI-drift-protected.

**Implemented:** presentation-safe `/v1/me`, catalog, workspace/dataset, checkout/portal/webhook contracts; ProblemDetail; request IDs; `contracts/openapi.yaml`; `contracts/schema/api.schema.json`.

**Not implemented:** Clerk JWT verification; Stripe SDK/network; signed uploads; PlanningRun; ADK HTTP execution; Cloud Run deploy; IAM.

---

## 2026-08-17 — CLERK TENANT AUTHENTICATION

**Decision:** Clerk Organizations are the only tenant authority input. PreM3 issues `tenant_id`. Current Clerk membership is checked at request time; webhook projections cannot grant access when Clerk is unavailable.

**Implemented:** `clerk-backend-api==6.0.1`; `RealClerkRuntime` / `FakeClerkRuntime`; session-token-only verification; org-required; request-time Planner provisioning; `POST /v1/webhooks/identity` with raw-body Standard Webhooks verification and Mission 05 idempotency.

**Not implemented:** Stripe; paid Project auto-creation; inline tenant deletion; Cloud Run deploy; IAM.

---

## 2026-08-18 — STRIPE SUBSCRIPTION BILLING

**Decision:** Stripe is the subscription source of truth. PreM3 persists a `SubscriptionProjection` and an immutable `EntitlementSnapshot`. Only the snapshot authorizes product capability. Checkout redirects and webhook payload deltas are not authority.

**SDK:** `stripe==15.5.0` via `StripeClient`. API version is the SDK default `2026-07-29.dahlia`. No separately selected preview API version.

**Plan → Price:** backend env mapping only (`STRIPE_PRICE_PROJECT` / `PORTFOLIO` / `ENTERPRISE`). Planner has no Price. Catalog GET does not perform Stripe network reads. Display amounts are optional configuration; missing amounts stay null.

**Customer:** one `StripeCustomerMapping` per tenant. Stripe POST idempotency key `prem3_cust_{tenant_id}`. Metadata is only `prem3_tenant_id`. Provider calls stay outside Firestore transactions.

**Checkout / Portal:** subscription mode, quantity 1, server-built URLs from `PREM3_FRONTEND_ORIGIN` + validated relative `return_path`. Optional `Idempotency-Key` is tenant-scoped before it is sent to Stripe. Checkout create does not write entitlement. Portal requires a mapped customer, not `ACTIVE` status.

**Webhook:** raw body + `Stripe-Signature`. Events: `checkout.session.completed`, `customer.subscription.created|updated|deleted`, `invoice.paid`, `invoice.payment_failed`. After verify, claim `ProcessedWebhookEvent` with a 120s lease (stale `CLAIMED` may be reclaimed; fresh `CLAIMED` returns retryable 503). Then retrieve the current Subscription and project. Unknown verified events are ignored.

**Status mapping (2026-07-29.dahlia):**

| Stripe | PreM3 | New MMM Projects |
|---|---|---|
| `active` | `ACTIVE` | allowed |
| `trialing` | `TRIALING` | allowed (trial of a paid plan) |
| `past_due` | `PAST_DUE` | denied; no deletes |
| `incomplete` | `INCOMPLETE` | denied |
| `canceled` | `CANCELED` | denied; no deletes |
| `unpaid` | `CANCELED` | denied; no deletes |
| `paused` | `CANCELED` | denied; no deletes |
| `incomplete_expired` | `CANCELED` | denied; no deletes |
| unknown | fail closed | never `ACTIVE` |

**Deferred UX:** self-serve archive/slot reduction when active projects exceed a downgraded capacity; PAST_DUE read-only surface copy. Safer fail-closed mutation policy is in effect.

**Not implemented:** ADK billing tools; signed uploads; PlanningRun; run credits; production data deletion.


---

## 2026-08-18 — PREM3-API CLOUD RUN PUBLIC INFRASTRUCTURE / APPLICATION AUTH

**Decision:** `prem3-api` is a distinct Cloud Run service from historical `modelready-m3`. Invoker IAM is disabled (`--no-invoker-iam-check`) so Clerk and Stripe signed callbacks can reach the one-service Mission 2 API. Cloud Run reachability is not product authentication.

**Security boundary:**

- public: `GET /health`, `GET /readyz`, `GET /v1/catalog/plans`
- Clerk session: `/v1/me`, workspaces, datasets, Checkout/Portal
- provider signatures: `POST /v1/webhooks/identity`, `POST /v1/webhooks/billing`

Tenant authority is never derived from Cloud Run accessibility, request headers, or `X-Tenant-ID`. No credentialed wildcard CORS. Browser clients use the Next.js BFF.

**Runtime:** Cloud factory constructs Firestore + Clerk + Stripe from deployment configuration (`PREM3_API_RUNTIME=cloud` / `K_SERVICE`). Local default remains in-memory and fail-closed. `m3-runtime` receives `roles/datastore.user` and per-secret `roles/secretmanager.secretAccessor`.

**Liveness path:** Cloud Run reserves some URL paths ending in `z` (documented known issue). Public liveness is `GET /health`. `GET /healthz` is not used. `GET /readyz` remains reachable in this project for adapter readiness.

**Not in this decision:** Dataset Evaluation → ExecutionContext → ADK HTTP; replacing `modelready-m3`; Meridian in the API image.

---

## 2026-08-18 — UPLOAD GENERATION FREEZE + EVALUATION ACCEPTED LIFECYCLE

**Decision:** Verified Dataset uploads freeze raw object identity by GCS generation (and related object metadata) before Evaluation create. Evaluation create is a first-class control-plane resource with `EvaluationStatus.ACCEPTED` only.

**Upload:** `POST .../uploads` issues V4 signed PUTs; `POST .../uploads/{id}/complete` verifies size/generation and materializes a generation-frozen package view. Accepted extensions: `.csv`, `.parquet`, `.json`. Opaque object paths remain immutable; presentation names are copied with `if_generation_match=0`.

**Evaluation:** `POST .../evaluations` returns **202** meaning accepted/created, not agent running. `ACCEPTED` is pre-execution. `DurableRunState` owns execution stages. Create does not imply `MODEL_READY` or Cloud ADK dispatch (Mission 11).

**Proof levels:** `LOCAL_AUTHORIZED_ADK_BRIDGE` (local in-process bridge only); `CLOUD_SIGNED_UPLOAD` via `scripts/qualify_signed_upload_cloud.py` (operator; not pytest/CI).

---

## 2026-08-18 — GOOGLE CONNECTIONS + IMPORT/PUBLISH GOVERNANCE

**Decision:** M2-11 adds governed Google OAuth connections and typed import/publish contracts without materializing or publishing customer data.

**Locked:**

1. Clerk authentication ≠ Google authorization. Tenant identity is never derived from Google email, subject, Cloud project, Drive owner, or BigQuery principal.
2. Canonical Drive depot visible name is `prem3-modeling` (lowercase). Folder ID is authority.
3. Canonical BigQuery dataset ID is `prem3_modeling`. Friendly name is `prem3-modeling`. Customer source tables may live outside that depot.
4. `IMPORT_READY`, `MODEL_READY`, and `PUBLISH_READY` never collapse into `READY`. Only `evaluate_import_readiness` / existing MODEL_READY validators / `evaluate_publish_readiness` may emit those states.
5. Frontend submits capabilities, never raw Google scopes. Default Drive scope is `drive.file`. `write_verified` is not implied by `BIGQUERY_WRITE` scope.
6. Refresh tokens are envelope-encrypted (`hmac-sha256-xor-v1`) in a credential vault. Incremental auth with `refresh_token=None` preserves the existing token.
7. Google Sheets are not IMPORT_READY in M2-11. BigQuery EXTERNAL / MATERIALIZED_VIEW / UNKNOWN are not IMPORT_READY.
8. Future customer BQ publish names: `model_ready_{dataset_id}_{run_id}` plus `model_ready_{dataset_id}_current`.
9. M2-12 materializes IMPORT_READY sources into DatasetUpload and publishes MODEL_READY + PUBLISH_READY artifacts. Durable Evaluation dispatch remains a later mission.

**Not in this decision:** live Google OAuth cloud proof; Cloud KMS wrap of the DEK (key name is reserved on the envelope); Drive/BQ REST materializers.

---

## 2026-08-22 — CANONICAL DF + KMS GOOGLE VAULT (M2-12Q)

**Decision:** Restack Mission 12 onto merged PR #15. Production materialization consumes canonical Data Foundation. Production Google refresh tokens use Cloud KMS envelope encryption.

**Locked:**

1. `build_product_stores(repo)` is the only production DF/BIQ store constructor. Materialization does not instantiate a second Firestore DF store.
2. `NullFoundationSourceGate` is not the production default. `CanonicalFoundationSourceGate` tenant-qualifies `get_binding(source_id)` / `get_current_source_receipt(source_id)`.
3. Dual gate: non-DF imports need current `IMPORT_READY` only. DF-managed sources also need `FOUNDATION_SOURCE_READY` + `governance_import_ready`. `DATA_FOUNDATION_READY` is workspace-level and is not required per source.
4. Business role lineage is Business IQ → `EvidenceRequirement.business_role` → `SourceBinding.requirement_id` → Import Contract. Incompatible roles fail closed (`FOUNDATION_LINEAGE_MISMATCH`).
5. Production vault algorithm is `aes-256-gcm+kms-v1`. Per-write DEK + nonce, AES-256-GCM, Cloud KMS symmetric wrap. Key: `projects/modelready-m3/locations/us-central1/keyRings/prem3/cryptoKeys/prem3-google-oauth-credentials`. Runtime SA gets key-level `roles/cloudkms.cryptoKeyEncrypterDecrypter` only.
6. Real Google OAuth without `GOOGLE_KMS_KEY` fails closed. Incremental OAuth with `refresh_token=None` preserves the existing envelope.
7. Customer BQ publish remains `model_ready_{dataset}_{run}` / `_current`. DF warehouse names are reserved from `app/data_foundation/owned_resources.py`.
8. BigQuery materialization stays `PASS_BOUNDED` at 100,000 rows. Overflow is `MATERIALIZATION_LIMIT_EXCEEDED`, never silent truncate.
9. Durable Evaluation dispatch remains M2-13.

**Not in this decision:** live Google OAuth/Drive/BQ provider proofs (external Clerk + OAuth client + interactive test account); Cloud Tasks Evaluation dispatch.

---

