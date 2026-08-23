# System Architecture

## Architectural goal

Build a small but production-minded event-driven agent with explicit state, deterministic validation, durable run history and experiential learning.

## Proposed Google Cloud architecture

```text
                 ┌──────────────────────┐
                 │   Web UI / Upload    │
                 └──────────┬───────────┘
                            │
                            v
                 ┌──────────────────────┐
                 │ Google Cloud Storage │
                 │ raw/{run_id}/...     │
                 └──────────┬───────────┘
                            │ Object event
                            v
                 ┌──────────────────────┐
                 │ Eventarc / Pub/Sub   │
                 └──────────┬───────────┘
                            v
                 ┌──────────────────────┐
                 │ Cloud Run            │
                 │ PreM3 / ADK          │
                 │ Orchestrator         │
                 └───────┬──────────────┘
                         │
          ┌──────────────┼─────────────────┐
          │              │                 │
          v              v                 v
   ┌────────────┐ ┌────────────┐   ┌───────────────┐
   │ Gemini     │ │ Determin.  │   │ Isolated      │
   │ reasoning  │ │ tools      │   │ Meridian EDA  │
   │            │ │            │   │ Cloud Run Job │
   └────────────┘ └──────┬─────┘   └───────┬───────┘
                         │                 │
               ┌─────────┼─────────┐       │
               v         v         v       v
          BigQuery     GCS      Firestore  Vertex AI
          analytics  outputs     state     Memory Bank
```

The diagram remains the long-range Google Cloud shape. **Eventarc is still future (`AMBIENT_TASKMASTER`).** Mission 2 authenticated product traffic enters through `prem3-api` (see `15_*`), not Eventarc. Public `/planner` does not enter this diagram at all. Firestore is the Mission 2 operational control plane (`14_*` §5.4); GCS and BigQuery keep artifact and ledger roles. Customer identity is request-scoped and is not the Cloud Run service account (`11_*` vs `14_*`).

M2-13 durable Evaluation path: `createEvaluation` → HTTP 202 after Cloud Tasks enqueue on `prem3-evaluation-dispatch` → service-OIDC launch → Cloud Run Job `prem3-evaluation-worker` → trusted restoration of `TenantContext` / `WorkspaceContext` / `ExecutionContext` → existing in-process `EvaluationExecutor`. Cloud Tasks does not run ADK. `EvaluationStatus` stays `ACCEPTED`. Dispatch success is not `MODEL_READY`. Isolated `meridian-eda-worker` remains a separate job.

## Agent topology

The user-facing product and agent is **PreM3**. It uses the **M3** operating method: **Map. Mend. Model.**

In **Map. Mend. Model.**, **Model** refers to completing and validating the model-consumption package and pre-modeling diagnostics—not fitting the Meridian MMM.

PreM3 is one coherent Taskmaster implemented as an ADK orchestrator plus focused specialist agents/tools. Avoid presenting the product as a decorative swarm of agents.

Prefer one orchestrator plus focused specialist agents/tools.

### 1. PreM3 Orchestrator
Responsibilities:
- state transitions;
- task routing;
- retries;
- human approval pauses;
- final completion gate.

### 2. Intake/Resolver Agent
Reasoning tasks:
- provider identification;
- report-type identification;
- candidate field semantics;
- confidence scores.

### 3. Readiness Agent
Reasoning tasks:
- interpret deterministic findings;
- determine severity;
- build remediation plan;
- route ambiguous choices.

### 4. Learning/Evaluator Agent
Responsibilities:
- summarize run episode;
- compare outcome to expectations;
- create candidate lessons;
- assign scope/confidence;
- propose eval cases.

## Deterministic tools

Minimum:
- `inventory_files`
- `sample_dataset`
- `profile_dataset`
- `detect_grain`
- `detect_date_gaps`
- `detect_duplicates`
- `detect_missingness`
- `detect_non_summable_metrics`
- `aggregate_to_week`
- `aggregate_campaign_to_channel`
- `normalize_dates`
- `normalize_numeric_values`
- `zero_fill_media_if_inactive`
- `apply_mapping`
- `validate_meridian_fields`
- `validate_meridian_no_na`
- `validate_time_format`
- `validate_channel_mappings`
- `validate_history_length`
- `write_artifact`
- `write_bigquery_model_table`
- `create_meridian_bigquery_view`
- `generate_meridian_input_contract`
- `validate_bigquery_publish_parity`
- `write_publish_receipt`
- `compare_before_after`

## Assignment coordinator

Pre-modeling coordination is manifest-driven. An assignment arrives with `model_intent.json` and source files. The coordinator inventories those sources, identifies provider/report/grain/role from typed metadata and the provider registry, then applies deterministic adapters. It does not look up Music Center filenames.

Dataset role (`TRAINING_EXPERIENCE`, `LEARNING_EVIDENCE`, `SEALED_HOLDOUT`) governs learning eligibility, not source parsing. Expected-answer artifacts are test oracles only.

See `docs/proof/PROVIDER_AGNOSTIC_COORDINATOR.md`.

## State model

```text
NEW
DISCOVERING
PROFILING
MAPPING
ASSESSING
WAITING_FOR_APPROVAL
REMEDIATING
VALIDATING
PUBLISHING
EXPLORING
MODEL_READY
WAITING_FOR_MODEL_APPROVAL
MODELING
FAILED
LEARNING
COMPLETE
```

State transitions must be persisted and idempotent.

## Run identity

Every run receives:
- `run_id`
- `dataset_fingerprint`
- `created_at`
- `source_manifest`
- `agent_version`
- `registry_version`
- `rule_version`
- `prompt/policy_version`
- `model_version`
- `lesson_set_version`

This enables true before/after and regression analysis.

## Persistence

### Cloud Storage
- raw files;
- transformed files;
- reports;
- manifests.

### BigQuery

BigQuery has two distinct responsibilities.

#### A. Agent / experience analytics
Tables:
- `runs`
- `run_files`
- `profiles`
- `issues`
- `actions`
- `tool_calls`
- `evaluations`
- `lessons`
- `lesson_evidence`
- `regression_results`

#### B. Model-ready publishing contract
For each versioned run or organization namespace:
- model-input table created by compiled DDL (`PARTITION BY time`, `CLUSTER BY geo`, column descriptions);
- stable Meridian-facing view;
- `model_ready_runs` registry;
- channel mapping;
- validation results;
- PreM3 Model-Ready Manifest (`model_ready_manifest.json`);
- transformation manifest;
- provenance;
- run metadata.

Gemini never chooses BigQuery types, partition fields, clustering, or descriptions. Deterministic schema compilation owns the physical contract. Publishing is complete only after the destination is independently read back and confirmed against the PreM3 Model-Ready Manifest, including physical types, partition, clustering, and column descriptions.

### Firestore
Firestore is the selected Mission 2 operational control-plane store. See `docs/context/14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md` §5.4.

Store:

- tenant ↔ identity-provider mappings;
- membership projections;
- MMM Projects and Datasets;
- entitlement and Stripe subscription projections;
- webhook idempotency records;
- tenant registry overlay metadata.

Do not use Clerk or Stripe provider IDs as Firestore document IDs, GCS path segments, or BigQuery dataset names.

GCS remains the durable artifact/run store. BigQuery remains the model-consumption contract and auditable experience/ops ledger. Firestore is not a substitute for either.

Historical optional uses (active job, current stage, approvals, status events) may still be projected here, but run evidence stays in GCS.

### Vertex AI Memory Bank
Store only **validated, generalized memories**, not raw datasets or secrets.

Examples:
- "Meta export field `amount_spent` is semantically media spend for report family X."
- "When a media-only week is absent and inactivity is supported by provider evidence, scaffold the period and zero-fill spend/exposure."
- "Do not aggregate CPC directly; reconstruct summable values from raw spend/clicks when available."

## Security

- Secret Manager for secrets.
- Service accounts with least privilege.
- Signed upload paths or authenticated API.
- No raw sensitive customer data in agent memory.
- Dataset retention config.
- Provenance log for all transformations.

## Failure strategy

- tool calls idempotent;
- retry transient failures;
- fail closed on ambiguous semantic transforms;
- preserve raw files;
- preserve previous output versions;
- validation required before READY;
- no irreversible transform without source artifact.

## Architecture constraint

Do not let "multi-agent" become decorative complexity.

Use agents when reasoning/context differs.
Use normal functions/tools for deterministic work.

CLOUD_TASKMASTER uses one deployed PreM3 agent plus run-level tools, including `run_pre_eda_diagnostics`, `inspect_modeling_feasibility`, `generate_semantic_readiness_interview`, `simulate_model_scope_scenarios`, and `run_meridian_eda`. Official Meridian pre-modeling EDA is deterministic compute in an isolated Cloud Run Job (`google-meridian==1.8.0` on Python 3.12). It is not a second agent and is not installed in the ADK Cloud Run image. Gemini interprets structured findings; it does not calculate EDA metrics or PreM3 diagnostic values. Eventarc remains future (`AMBIENT_TASKMASTER`). Durable run state is stored in the artifact GCS bucket; Cloud Run `/tmp` is scratch only. See `docs/context/13_CLOUD_TASKMASTER_EXECUTION_MODEL.md`. Dataset A Music Center has a historical golden run (`m3cloudc5b11fe79553` on `modelready-m3-00012-8xq`) and a generalized-coordinator regression (`m3cloud653724094004` on `modelready-m3-00013-c4s`). Datasets B and C Map/Mend on that same generalized revision. Proof: `docs/proof/PROVIDER_AGNOSTIC_COORDINATOR.md`.

## PreM3 publish and model handoff

PreM3's default **success milestone** is **MODEL_READY**, not merely `READY`. True terminal stages are `FAILED` and `COMPLETE`. `MODEL_READY → LEARNING` and `MODEL_READY → WAITING_FOR_MODEL_APPROVAL` are legal; current demos still stop displaying at `MODEL_READY`. `MODEL_READY` is the operational pre-modeling outcome. `LEARNING` is post-task episode evaluation and is not required to validate the model artifact.

```text
RAW / MAPPED / REMEDIATED DATA
      ↓
deterministic validation
      ↓
manifest
      ↓
BigQuery publication
      ↓
independent verification
      ↓
PREM3 COMPUTATIONAL INTELLIGENCE
      ↓
PREM3 SEMANTIC READINESS
      ↓
OFFICIAL MERIDIAN EDA
      ↓
PREM3 INTERPRETATION / GUIDANCE
      ↓
MODEL HANDOFF
      ↓
MODEL_READY / USER_REQUIRED
```

DOMAIN_VIEW is an authorized knowledge input to PreM3 interpretation and routing. It is not the source of raw diagnostic calculations.

```text
validated artifact
      ↓
PreM3 Model-Ready Manifest (`VALIDATED_FOR_PUBLICATION`)
      ↓
compiled BigQuery DDL (types, descriptions, PARTITION BY time, CLUSTER BY geo)
      ↓
versioned BigQuery model table
      ↓
independent destination read-back
      ↓
stable Meridian-facing view + registry
      ↓
PREM3 pre-EDA diagnostics + modeling feasibility + semantic interview
  (verified BigQuery input; finding_origin=PREM3_PRE_EDA)
      ↓
EXPLORING — official Meridian PRE-MODELING EDA
  (EDASpec(); EDA-only sample_prior; never sample_posterior)
      ↓
Gemini interpretation of structured EDAFinding objects
      ↓
confirmation receipt
      ↓
MODEL_READY
      ↓
optional approval (WAITING_FOR_MODEL_APPROVAL)
      ↓
posterior / Meridian model execution
```

### Autonomous authority

PreM3 may autonomously:
- create run-scoped/versioned BigQuery model tables;
- create a Meridian-facing view;
- write provenance and manifests;
- generate field/channel mappings;
- verify publish parity;
- run official Meridian pre-modeling EDA, including EDA-only `sample_prior`.

### Approval boundary

Launching Meridian posterior sampling or model fitting is modeler-governed because modeling configuration choices can materially affect model behavior and interpretation. Autonomous pre-modeling EDA is required for `MODEL_READY` and is not model execution. The EDA gate records official `ModelSpec.knots` and data-adequacy parameters; those values are evidence for `MODEL_READY`, not agent prose. Official input rejection or ERROR findings produce a `USER_REQUIRED` resolution pack. PreM3 does not silently drop controls, change grain, or choose final knots.

For the hackathon, actual Meridian fitting remains out of scope. The required proof is `PRE_MODELING_COMPLETE` plus evidence-backed `MODEL_READY`.

## Learning proof

MEL (PreM3 Experience Loop) is embedded inside PreM3.

### Current

- **DOMAIN_VIEW v1** is implemented as a generated, versioned operational knowledge set (`app/domain/intelligence/`, `docs/context/domain-view/`).
- Promoted experiential lesson count is **0**.
- Machine receipts `EXPERIENCE_LEARNED` / `EXPERIENCE_APPLIED` exist as contracts in `app/core/contracts.py`.

### MEL target state

```text
ExperienceEpisode
  → ExperienceReflection
  → CandidateLesson
  → evidence / safety / regression
  → EXPERIENCE_LEARNED
  → DOMAIN_VIEW version change
  → future retrieval
  → changed behavior
  → EXPERIENCE_APPLIED
```

A meaningful learned episode should generate:
- **PreM3 Learning Receipt** when experience is promoted and DOMAIN_VIEW changes;
- **Experience Applied Receipt** when validated experience materially changes a future execution path.

BigQuery remains the planned authoritative experience/evidence ledger. DOMAIN_VIEW is the operational knowledge set. Vertex AI Memory Bank, if used, is an optional retrieval/indexing surface for validated generalized items — not the authority.

The MEL Episode Core is implemented (`app/mel/`). A local A+B intelligence cycle promoted one `ROUTING_HINT` and applied it to sealed Dataset C (`docs/proof/FIRST_REAL_LEARNING_CYCLE.md`). Do not present that as live Cloud Taskmaster `MODEL_READY` proof. Bootstrap DOMAIN_VIEW remains v1.0.0. Stride & Field Dataset B is independent learning-evidence input. Summit & Pine Dataset C is the sealed evaluation holdout and must not feed candidate generation or promotion.

```text
DATASET A  TRAINING_EXPERIENCE
DATASET B  LEARNING_EVIDENCE
        ↓
ExperienceEpisode → ExperienceReflection → CandidateLesson → evaluation
        ↓
possible EXPERIENCE_LEARNED / DOMAIN_VIEW v2

DATASET C  SEALED_HOLDOUT  (isolated)
        ↓
DOMAIN_VIEW v1 baseline (sealed before promotion)
        ↓
later: same Dataset C + DOMAIN_VIEW v2 → possible EXPERIENCE_APPLIED
```

Dataset C never enters the promotion path.

```text
TASK EXECUTION
     │
     └── MODEL_READY / USER_REQUIRED
               │
               ↓
        EXPERIENCE EPISODE
               │
               ↓
        EXPERIENCE REFLECTION
               │
               ↓
             MEL
               │
        ┌──────┴───────┐
        │              │
     REJECT/HOLD     PROMOTE
        │              │
     evidence      DOMAIN_VIEW vN+1
                       │
                       ↓
                   FUTURE RUN
                       │
                       ↓
                EXPERIENCE_APPLIED
```

Learning does not sit inside the `MODEL_READY` gate.

### Learning that can be inspected

Memory is recall. Reflection is evaluation. Learning is validated change.

PreM3 is designed for operational metacognition: it can represent and evaluate what it knew, observed, determined, was allowed to do, did not know, expected, and what subsequently happened. This is system metacognition, not a claim of consciousness or human subjective self-awareness.

Core pillars:

- **Memory** gives continuity.
- **Reflection** gives metacognition.
- **Evaluation** gives discipline.
- **Constraints** define allowances, guardrails and gold standards.
- **DOMAIN_VIEW** provides the evolving operational worldview.
- **EXPERIENCE_APPLIED** proves that learning mattered.

PreM3 distinguishes memory, evidence, reflection, candidate learning, promoted learning, and applied learning.

The system can show:

- what experience produced a lesson;
- why the lesson survived evaluation;
- exactly what DOMAIN_VIEW changed;
- which later run retrieved it;
- what behavior changed;
- how correctness was independently validated.

Diagrams:

- MEL lifecycle: `docs/architecture/PREM3_MEL_LEARNING_CYCLE.mmd`
- reflective self-model: `docs/architecture/PREM3_SELF_MODEL.mmd`
- learning pillars: `docs/architecture/PREM3_CORE_LEARNING_PILLARS.mmd`

First-cycle proof surface: `docs/proof/FIRST_PREM3_LEARNING_CYCLE.md`.

The conceptual self-model can show the full learning system. The technical MEL lifecycle still separates Episode A → reflection / evaluation / promotion → DOMAIN_VIEW update from later Episode B → `EXPERIENCE_APPLIED`.

## Response quality architecture

Most LLM systems treat generated prose as the final product. PreM3 separates:

- **what is true** — deterministic tools, run evidence, official Meridian, authorized DOMAIN_VIEW knowledge;
- **what should be said** — semantic interpretation and response-type selection;
- **how it should be expressed** — `RESPONSE_STYLE_GUIDE` and the typed response contract;
- **how it should be rendered** — reusable UI components;
- **how quality is verified** — output QA across accuracy, semantics, format, and consistency.

**Response Quality = Product Quality.** Intelligence is only useful when users can see what happened, why it matters, what evidence supports it, what should happen next, and who owns the next action.

```text
DATA / TOOLS
        ↓
STRUCTURED RUN INTELLIGENCE
        ↓
RESPONSE CONTRACT
        ↓
OUTPUT QA
        ↓
UI
```

Canonical image (do not repeat throughout the docs):

![PreM3 Agent Output QA Framework](../architecture/prem3_agent_output_qa_framework.png)

Detail: `docs/architecture/RESPONSE_ARCHITECTURE.md`.  
Human-readable presentation standard: `docs/context/RESPONSE_STYLE_GUIDE.md`.

The structured response architecture is implemented. The full Agent Output Evaluation Harness is not live. Output QA evidence may later inform ExperienceEpisode records; QA success or failure does not automatically create a lesson. MEL still owns promotion.
