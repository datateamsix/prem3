# AGENTS.md

You are contributing to **PreM3**, an entry for Google's All Things Agentic Hackathon.

Canonical naming:
- **PreM3** = product and autonomous pre-modeling agent
- **M3** = Map. Mend. Model. operating method / Media Mix Modeling reference
- **MEL** = PreM3 Experience Loop
- **PreM3 Learning Receipt** = proof of promoted experience
- **EXPERIENCE_APPLIED** = proof validated experience changed a future run
- **MODEL_READY** = verified pre-modeling terminal state
- **MODEL_ACCEPTED** = a specific fingerprinted Meridian configuration was fit, reviewed, and consciously accepted

Before coding, read:
1. `README.md`
2. `docs/brand/PREM3_BRAND_AND_NAMING.md`
3. `docs/context/00_HACKATHON_MASTER_CONTEXT.md`
4. `docs/context/02_SYSTEM_ARCHITECTURE.md`
5. the relevant workstream spec (`14_*` for persistence/tenancy, `15_*` for service/API/frontend integration, `16_*` for auth/billing, `17_*` for import/publish governance, and the future `18_*` plus `RESPONSE_STYLE_GUIDE.md` for planning/report work).

## Absolute rules

- Deadline is Aug 31, 2026 at 5:00 PM PT.
- Primary track is Taskmaster.
- Google Meridian is the first modeling target.
- Align with Google's MMM Unified Schema where practical.
- Agent behavior must be autonomous but auditable.
- Deterministic validators own readiness; agent prose never does.
- BigQuery model input must be independently verified.
- Official Meridian EDA is autonomous pre-modeling.
- Official Meridian ERROR blocks `MODEL_READY`.
- EDA ATTENTION may allow `MODEL_READY` with review recommended.
- Agent prose never determines `MODEL_READY`.
- Raw input is immutable.
- Every transform has provenance.
- No fabricated observations.
- No silent business-semantic changes.
- Validated model artifacts should be publishable to a versioned BigQuery table/view.
- PreM3 may publish validated run-scoped/versioned model artifacts autonomously.
- Posterior sampling / model fitting is never autonomous. It may execute only after explicit human approval bound to an exact fingerprinted FitPlan. Official pre-modeling EDA, including EDA-only `sample_prior`, is required and is not model execution. The EDA ModelSpec remains `PRE_MODELING_EDA_ONLY` and is never silently promoted into the fitted model.
- `MODEL_READY` proves the evidence is ready to model. `MODEL_ACCEPTED` proves a specific model configuration was fit, reviewed, and consciously accepted.
- Learning is evidence-driven; do not implement uncontrolled self-modification.
- Demo reliability is more important than feature breadth.
- Do not add infrastructure or agents without a clear rubric/demo benefit.
- Do not hard-code GCP project IDs, resource names, demo metrics, readiness outcomes, or learning receipts.
- Tenant identity is resolved from a verified credential at the service boundary, never from environment variables, request bodies, URLs, agent prose, or Stripe/Clerk provider IDs used directly as storage keys.
- `workspace_id` is customer-facing **MMM Project**; `dataset_id` is a durable Dataset; `run_id` is one Evaluation. They are not interchangeable.
- No tool signature accepts tenant, workspace, dataset, storage path, BigQuery destination, plan, or entitlement as model-supplied authority.
- The frontend holds no cloud credentials and renders generated contracts; it never re-implements authority, readiness, project-capacity, or billing semantics.
- Public `/planner` is deterministic/local-static at anonymous runtime. It does not invoke PreM3/GCP execution, does not receive `TenantContext`, and does not require a backend anonymous session.
- Clerk user/org provisioning must not auto-create a paid MMM Project. Project creation is explicit and capacity-gated.
- Commercial plans gate active MMM Projects (0 / 1 / 10 / 50), not Dataset count or Evaluation Run count. Paid plans have unlimited re-evaluations subject to operational protections.
- Customer-facing completion language is **Meridian Integration**. Legacy internal `handoff_*` evidence names may remain only where changing proven contracts adds risk.
- Entitlement checks exist on every gated operation; Stripe is subscription source of truth and PreM3 stores a Firestore projection.
- Firestore is the Mission 2 operational control-plane store for tenant mappings, membership, projects, datasets, entitlements, billing projections, webhook idempotency, and registry overlay metadata. GCS and BigQuery retain their existing artifact and ledger roles.

## Engineering principle

**Gemini decides. Deterministic code proves. Meridian calculates. Gemini interprets. Experience teaches. Evaluation decides what survives.**

Use agents for reasoning/context boundaries. Use ordinary typed functions/tools for deterministic calculations and transformations.

## Definition of useful work

A change is useful if it improves at least one:
- operational autonomy;
- deterministic correctness;
- Meridian readiness;
- experiential learning;
- cloud production proof;
- demo clarity;
- reproducibility;
- BigQuery model-contract integrity;
- PreM3 Learning Receipt evidence.

## MVP order of operations

Do not broaden scope until this works end to end:

`fixture/upload → PreM3 → profile → issue detection → safe repair → deterministic validation → BigQuery publish → parity check → Meridian contract → PreM3 pre-EDA diagnostics → official pre-modeling EDA → MODEL_READY`

## Context routing

Do not load every long context file into every agent prompt.

| Path | Load |
|---|---|
| Every agent | `docs/context/PREM3_MMM_BOOT_CONTEXT.md` |
| Product / general user-facing | `docs/context/PREM3_PRODUCT_CONTEXT.md` |
| User-facing presentation | `docs/context/RESPONSE_STYLE_GUIDE.md` plus the typed contract in `app/response/` |
| Execution / readiness | `docs/context/meridian/MERIDIAN_DATA_PREP_CONTEXT.md` |
| Advisory / conversational | `docs/context/meridian/MERIDIAN_ADVISOR_PLAYBOOK.md` |
| Deterministic runtime | `app/rules/meridian.yaml` plus `app/rules/intelligence_registry.yaml` (pre-EDA diagnostics implemented) |
| Domain reasoning | current DOMAIN_VIEW (`docs/context/domain-view/DOMAIN_VIEW.md`, `app/domain/intelligence/data/current/domain_view.json`) |
| Service / API layer | `docs/context/14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md`, `docs/context/15_FRONTEND_INTEGRATION_AND_SERVICE_SURFACE.md` |
| Frontend / product surface | `docs/context/15_FRONTEND_INTEGRATION_AND_SERVICE_SURFACE.md` |
| Auth / billing / entitlements | `docs/context/16_AUTH_BILLING_AND_ENTITLEMENTS.md` |
| Import / publish governance | `docs/context/17_IMPORT_AND_PUBLISH_GOVERNANCE.md` |
| MMM modeling / Meridian fit | `docs/backend/MMM_MODELING_STATE_MACHINE.md`, `docs/backend/MERIDIAN_SKILL_INTEGRATION_ARCHITECTURE.md`, `app/modeling/` |
| Planning engine / report compiler | `18_PLANNING_ENGINE_AND_REPORT_CONTRACT.md` once authored + `docs/context/RESPONSE_STYLE_GUIDE.md` |

MEL Episode Core lives in `app/mel/`. Learning evaluation is downstream of `MODEL_READY` and must not be loaded into the isolated Meridian EDA worker. MEL may record structured modeling evidence after a fit; MEL may not alter an active ModelPlan, prior, FitPlan, or trigger a rerun.

Intelligence version: `docs/context/intelligence/intelligence_version.json`.

Four user-value behaviors: **ASSESS · ADVISE · INSIGHT · GUIDE**.

Knowledge classes: `MERIDIAN_NORMATIVE` · `PREM3_DETERMINISTIC_DIAGNOSTIC` · `MMM_EVIDENCE_HEURISTIC` · `MMM_JUDGMENT`.

A deterministic calculation does not grant action authority. Official Meridian owns official EDA findings. Heuristics cannot independently block `MODEL_READY`.

The isolated Meridian EDA worker must not load product, DOMAIN_VIEW, or RESPONSE_STYLE_GUIDE prose.

Do not turn execution agents into sales bots. Product context exists so PreM3 can answer product questions accurately, not inject marketing into every interaction.

User-facing agents should use the structured response contract when a response type exists. Do not return a large unstructured text block when typed intelligence can be presented. Structured evidence remains authoritative. Gemini may summarize evidence; it may not invent numbers, owners, authority, `MODEL_READY`, or `MODEL_ACCEPTED`.

The computational/semantic intelligence layer must not change BigQuery publication, BQ parity, the Meridian worker, official EDA behavior, the `MODEL_READY` gate, Cloud Run resource names, Eventarc, or MEL runtime. DOMAIN_VIEW is consumed, not mutated. The presentation layer consumes that intelligence; it does not recalculate it.

## Legacy technical identifiers

Some infrastructure and internal machine identifiers retain the earlier `modelready-m3` / `m3` namespace for compatibility with proven cloud deployments. They are implementation identifiers, not a separate product.
