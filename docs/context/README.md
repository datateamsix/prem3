# PreM3 War Room context

This directory is the checked-in shared source of truth for human and coding-agent work on the hackathon MVP.

Read order:

1. `00_HACKATHON_MASTER_CONTEXT.md`
2. `01_PRODUCT_SPEC_PREM3.md`
3. `02_SYSTEM_ARCHITECTURE.md`
4. the relevant workstream document
5. `SOURCES.md` for authoritative external references
6. For product/MMM intelligence: `PREM3_MMM_BOOT_CONTEXT.md`, then the path-specific file in Context routing (`AGENTS.md`)

Workstream documents currently synchronized:

- `03_EXPERIENTIAL_LEARNING_FRAMEWORK.md`
- `04_MERIDIAN_READINESS_SPEC.md`
- `05_DEMO_AND_JUDGING_STRATEGY.md`
- `06_EXECUTION_PLAN.md`
- `07_AGENT_DELEGATION_AND_GUARDRAILS.md`
- `08_DECISION_LOG.md`
- `09_RESEARCH_BACKLOG.md`
- `11_ADK_RUNTIME_IDENTITY_MODEL.md`
- `12_PHASE1_EVIDENCE_MODEL.md`
- `13_CLOUD_TASKMASTER_EXECUTION_MODEL.md`
- `14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md`
- `15_FRONTEND_INTEGRATION_AND_SERVICE_SURFACE.md`
- `16_AUTH_BILLING_AND_ENTITLEMENTS.md`
- `17_IMPORT_AND_PUBLISH_GOVERNANCE.md`

Planning & Optimization (P6) product sources (bodies unchanged; implementation baseline override in `docs/backend/P6_SOURCE_AUTHORITY.md`):

- `PREM3_INVESTMENT_PLAN_BUDGET_INGESTION_FEATURE_SPEC.md`
- `PREM3_MARKETING_PORTFOLIO_ASSET_ALLOCATION_AND_OPTIMIZATION_SPEC.md`
- `PREM3_PLANNING_OPTIMIZATION_BACKEND_MISSION_PLAN.md`

Intelligence context (2026-08-16):

- `PREM3_PRODUCT_CONTEXT.md`
- `PREM3_MMM_BOOT_CONTEXT.md`
- `meridian/MERIDIAN_DATA_PREP_CONTEXT.md`
- `meridian/MERIDIAN_ADVISOR_PLAYBOOK.md`
- `intelligence/` — registry design, semantic interview, feasibility, scope scenarios, guided remediation, and discrepancy reports
- `domain-view/` — generated DOMAIN_VIEW, architecture, and learning-surface README

When architecture or product decisions change, update the canonical context and implementation together. Do not let prompts, code, README copy, and demo claims drift into different definitions of `MODEL_READY`. Do not let frontend routes, API contracts, backend tenancy, entitlements, or reports drift into different definitions of `tenant_id`, MMM Project / `workspace_id`, Dataset / `dataset_id`, Evaluation / `run_id`, `COLLECTION_READY`, `MODEL_READY`, or project capacity.
