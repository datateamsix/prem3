# Frontend Integration and Service Surface

**Status:** Mission 2 canonical integration constraint — revised 2026-08-17
**Applies to:** marketing, pricing, public Planner, Clerk/Stripe product flows, MMM Projects, Datasets, Planning, Taskmaster, Meridian Integration
**Depends on:** `14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md`, `docs/context/RESPONSE_STYLE_GUIDE.md`, `app/response/contracts.py`
**Architecture reconciliation:** Mission 2 frontend productization plan, 2026-08-17

---

## 1. The service dependency

The Mission 1 repository proved the ADK/Cloud Run/BigQuery/Meridian execution path but did not expose that capability as a customer HTTP service. Mission 2 adds a real SaaS surface, so `prem3-api` is a P0 backend deliverable for **authenticated** product workflows.

The public marketing site, `/start`, `/pricing`, `/how-it-works`, fixture demo, and deterministic `/planner` do **not** need to wait on `prem3-api`. The public Planner intentionally generates its lead-generation result without PreM3/GCP runtime execution, without `TenantContext`, and without a backend anonymous session.

Authenticated features do depend on the service: MMM Project creation, Dataset persistence/uploads, backend-powered planning, evaluation execution/history, Taskmaster state, entitlements, billing projection, and Meridian Integration.

Consequences:

1. Freeze service contracts before Claude integrates authenticated screens.
2. Keep public Planner rules/provider metadata generated and versioned, not hand-maintained in React.
3. Build frontend against generated types + mocks/fixtures until the matching endpoint is live.
4. Treat Project → Dataset → Evaluation as the product hierarchy from the API boundary onward.

## 2. Runtime topology

```text
PUBLIC / ANONYMOUS
Browser
  ├─► marketing / pricing / start / demo
  └─► deterministic PreM3 Planner
        └─► versioned local/static Planner manifest
            (no prem3-api / Gemini / ADK / Meridian / BQ / GCS execution)

AUTHENTICATED PRODUCT
Browser
  │
  ▼
Next.js app + thin BFF             ← no cloud credentials; no product business logic
  │  verified Clerk token / request ID
  ▼
prem3-api (Cloud Run)             ← auth verification, TenantContext, project authorization,
  │                                  entitlements, billing projection, planning/run coordination
  ├─► ADK agent runtime (in-process) ─► Vertex AI / Gemini when the backend workflow requires it
  ├─► Firestore                    (Mission 2 operational control plane)
  ├─► GCS                          (tenant/project/dataset artifacts + signed uploads)
  ├─► BigQuery                     (ops, experience, model consumption)
  └─► Cloud Run Job                (meridian-eda-worker, isolated, unchanged)
```

### 2.1 Decisions to lock now

**One backend service, not two.** `prem3-api` hosts HTTP and the ADK runner in-process. The Meridian EDA worker stays isolated.

**Use a thin Next.js BFF.** Authenticated browser requests flow through a bounded route such as `src/app/api/prem3/[...path]/route.ts`, which forwards verified identity/request context, applies timeouts, and normalizes typed errors. It does not contain readiness, entitlement, planning, or billing business logic.

**The frontend holds no Google Cloud credentials.** No service-account key, direct GCS/BigQuery/Vertex client, or Gemini call from browser/Next.js product code.

**Uploads use signed URLs issued by `prem3-api`.** URLs are tenant/project/dataset scoped, short-lived, and never expose a `gs://` path to the browser.

**Frontend state is a cache, never source of truth** for authenticated workflows. Planning progress, project capacity, Dataset state, Taskmaster status, readiness, and billing status reconstruct from the API.

**Public Planner is the exception only in scope, not authority.** Its local result is a planning brief/blueprint and may not declare `COLLECTION_READY`, `MODEL_READY`, entitlement state, or backend authority. On conversion, local fields enter authenticated planning only as candidate/unconfirmed inputs.

## 3. Route map and funnel wiring

### 3.1 Public

| Route | Purpose | Auth | Backend execution |
|---|---|---|---|
| `/` | High-polish marketing landing | none | none required |
| `/how-it-works` | Product workflow / proof explanation | none | none required |
| `/pricing` | Planner / Project / Portfolio / Enterprise | none | optional catalog read; no secret pricing in client code |
| `/planner` | Free deterministic PreM3 Planner | none | **none** |
| `/start` | Three-path MMM stage chooser | none | none on page load |
| `/sign-in`, `/sign-up` | Clerk identity | none | identity provider only |
| `/privacy`, `/terms` | Public legal | none | none |
| `/app/demo/runs/:run_id` | Read-only fixture demo | none | fixture/static path |

### 3.2 Authenticated

Customer-facing copy says **MMM Project** while internal identifiers remain `workspace_id`.

| Route | Purpose |
|---|---|
| `/app` | Customer dashboard: plan, project allowance, recent activity/evaluations |
| `/app/w/:workspace_id` | MMM Project home |
| `/app/w/:workspace_id/plans` | Planning history |
| `/app/w/:workspace_id/plans/:planning_run_id` | Acquisition/data-gap plan detail + versions |
| `/app/w/:workspace_id/datasets` | Dataset inventory |
| `/app/w/:workspace_id/datasets/:dataset_id` | Dataset detail + evaluation history |
| `/app/w/:workspace_id/datasets/:dataset_id/runs/:run_id` | One evaluation/run detail |
| `/app/w/:workspace_id/taskmaster` | Project Taskmaster / current execution read model |
| `/app/settings/account` | Account / organization context |
| `/app/settings/billing` | Subscription + Stripe Customer Portal entry |

Tenant is resolved from verified identity, never from a URL segment. `workspace_id` in the URL is a selector that must be server-authorized on every request. Unauthorized project lookup returns the product's not-found behavior rather than confirming another tenant's resource exists.

### 3.3 Landing → workflow contract

```text
/ ──Get Started──► /start

Planning
  └─► /planner
       └─► deterministic local result shown before registration
            └─► Save as MMM Project
                 ├─ signed out → Clerk
                 ├─ no paid project slot → /pricing → Stripe Checkout
                 └─ entitled → create/select MMM Project
                       └─ optional Planner import as candidate/unconfirmed facts

Getting organized
  └─► signed out/free → preserve intent through Clerk/pricing
      entitled → create/select MMM Project → DATA_GAP_PLANNING

Ready to assess
  └─► signed out/free → preserve intent through Clerk/pricing
      entitled → create/select MMM Project → Dataset creation/upload → Evaluation
```

Do not create backend planning runs just because `/start` or `/planner` was visited. A backend Planning Run belongs inside an authenticated MMM Project.

The three stage cards are routing hypotheses, not permanent labels. Authenticated planning may change workflow kind through an explicit backend transition while preserving only compatible confirmed facts.

## 4. API and generated-contract surface

Versioned, typed, and the only authenticated route from frontend to PreM3. Exact shapes belong in `contracts/openapi.yaml` and generated JSON Schemas; this list defines required resource families, not permission to hand-write divergent clients.

```text
# identity / catalog / billing
GET    /v1/me
GET    /v1/catalog/plans
POST   /v1/billing/checkout-session
POST   /v1/billing/portal-session
POST   /v1/webhooks/identity
POST   /v1/webhooks/billing

# MMM Projects (workspace_id internally)
GET    /v1/workspaces
POST   /v1/workspaces
GET    /v1/workspaces/{workspace_id}
PATCH  /v1/workspaces/{workspace_id}              # only if lifecycle/edit contract exists

# authenticated planning
POST   /v1/workspaces/{workspace_id}/planning/runs
GET    /v1/planning/runs/{planning_run_id}
GET    /v1/planning/runs/{planning_run_id}/questions/next
POST   /v1/planning/runs/{planning_run_id}/answers
POST   /v1/planning/runs/{planning_run_id}/change-path
POST   /v1/planning/runs/{planning_run_id}/import-planner-brief
POST   /v1/planning/runs/{planning_run_id}/compile
GET    /v1/planning/runs/{planning_run_id}/reports
GET    /v1/planning/reports/{report_id}
GET    /v1/planning/reports/{report_id}/artifacts

# registry
GET    /v1/registry/search?q=
POST   /v1/registry/gaps                            # authenticated workflow only

# Datasets and Evaluations
GET    /v1/workspaces/{workspace_id}/datasets
POST   /v1/workspaces/{workspace_id}/datasets
GET    /v1/workspaces/{workspace_id}/datasets/{dataset_id}
POST   /v1/workspaces/{workspace_id}/datasets/{dataset_id}/uploads
POST   /v1/workspaces/{workspace_id}/datasets/{dataset_id}/runs
GET    /v1/workspaces/{workspace_id}/datasets/{dataset_id}/runs
GET    /v1/runs/{run_id}
GET    /v1/workspaces/{workspace_id}/taskmaster
```

The public Planner is supplied by a **versioned generated artifact**, not a live planning endpoint, for example:

```text
contracts/planner-manifest.schema.json
frontend/src/generated/planner-manifest.v1.json
```

Conventions:

- Mutating endpoints accept `Idempotency-Key` where replay can duplicate state or cost.
- Errors return a typed problem object with stable `code`; frontend never parses rendered error prose.
- List endpoints paginate from day one.
- Long operations return `202` with operation/run identity and poll/stream contract.
- Project capacity is enforced server-side. The frontend may present `max_active_projects`, but cannot authorize itself.
- Every Dataset run is linked to one `dataset_id`; unlimited re-evaluations means no commercial run-balance endpoint is exposed.
- Plan price amounts / Stripe Price IDs come from the backend plan catalog/configuration, not React constants.

## 5. Rendering and report contracts — the highest-value integration rule

`app/response/contracts.py` remains the typed presentation contract for run/product responses, and `docs/context/RESPONSE_STYLE_GUIDE.md` remains the canonical human-readable standard. Mission 2 adds a planning/report contract that must follow the same rule: **machine structure first; UI/Markdown/PDF are renderers.**

The frontend must not:

- re-implement authority labels;
- derive status from prose;
- decide blocking/review/user-required semantics;
- compute `COLLECTION_READY` or `MODEL_READY`;
- merge official Meridian findings with PreM3 interpretation;
- invent planning sections or action ownership;
- treat the local Planner result as a certified backend report.

Backend planning should expose one versioned `PlanningReportV1` family capable of rendering at least:

- `MMM_PROJECT_BLUEPRINT`;
- `MMM_ACQUISITION_PLAN`;
- `MMM_DATA_GAP_PLAN`.

The exact planning report contract belongs in the planned Planning Engine / Report Contract source document and JSON Schema. The report section order, provenance, authority, assumptions, gaps, actions, and version context are backend-owned.

To make drift structural rather than procedural:

1. Export response, state, intelligence/MEL, planning, project/dataset, and entitlement schemas from backend models.
2. Commit generated JSON Schema under `contracts/`.
3. Generate TypeScript under `frontend/src/types/generated/`.
4. Generate/mock the API client from `contracts/openapi.yaml`.
5. Fail CI when generated outputs differ.

A backend enum or report-contract change should break frontend contract CI immediately; that is the desired outcome.

## 6. Contract-first integration and fixtures

Authenticated frontend work may proceed before every live endpoint exists, but only against the same contract the backend will implement:

1. Freeze `contracts/openapi.yaml` for the resource family being integrated.
2. Export JSON Schemas from Pydantic/backend models.
3. Generate TypeScript and API client code; no parallel hand-written contract mirror.
4. Use mock/fixture responses that validate against those schemas.
5. Keep the public Planner on the generated Planner manifest; do not mock `prem3-api` for anonymous planning because production anonymous planning should not call it.
6. Maintain golden Music Center planning report fixtures once the planning contract is defined, so UI, Markdown/PDF renderers, and backend tests share identical examples.

This prevents the failure mode where frontend, backend, and report generators each invent a different definition of Project, Dataset, readiness, or acquisition plan.

## 7. What Mission 2 frontend should and should not do

**Should:**

- High-polish `/`, `/how-it-works`, `/pricing`, legal pages.
- Public `/planner` using generated deterministic rules/provider metadata with a network test proving no PreM3/GCP execution call.
- `/start` routing into Planner or authenticated paid paths without creating orphan backend state.
- Clerk-authenticated `/app` dashboard with backend-returned plan/project allowance.
- MMM Project, Dataset, planning, evaluation-history, Taskmaster, billing, and Meridian Integration surfaces driven by generated contracts.
- Stripe Checkout/Customer Portal initiation only through backend endpoints.
- Existing Mission 1 fixture demo and evidence components preserved.

**Should not:**

- Direct cloud SDK usage or credentials.
- Direct Stripe secret/API calls from client code.
- A bespoke chatbot as the primary planning interface.
- Hardcoded provider lists, project limits, price IDs, readiness logic, or billing state.
- Anonymous GCP planning execution for the lead-gen Planner.
- Treat Dataset, upload, and Evaluation Run as the same object.
- Customer-facing “Meridian handoff” language. Use **Meridian Integration** instead.

## 8. Mission 2 integration definition of done

- [ ] Public routes `/`, `/how-it-works`, `/pricing`, `/planner`, `/start`, legal, auth, and demo are stable and polished.
- [ ] Anonymous Planner produces a useful result with no `prem3-api`/Gemini/ADK/Meridian/BQ/GCS execution call.
- [ ] Planner result survives auth conversion and enters backend planning only as candidate/unconfirmed input.
- [ ] `/app` shows backend-returned subscription plan and active MMM Project allowance.
- [ ] Project → Dataset → Evaluation hierarchy is represented in routes and contracts.
- [ ] Unlimited re-evaluations are represented as Dataset history, not a run-credit balance.
- [ ] Every authenticated screen renders generated types; no hand-authored backend response interfaces.
- [ ] Taskmaster stage truth comes from the server read model.
- [ ] Official Meridian / PreM3 authority separation comes from contract fields.
- [ ] Stripe Checkout and Customer Portal are initiated through backend endpoints; no secret key reaches frontend.
- [ ] Uploads use server-issued signed URLs and never expose GCP credentials/URIs.
- [ ] Pricing supports Planner / Project / Portfolio / Enterprise and backend-configured monthly prices.
- [ ] Customer-facing completion capability is **Meridian Integration**.
- [ ] Frontend CI runs lint → typecheck → test → build plus generated-contract drift/security checks.

## 9. Dependency and sequencing map

| # | Backend/service work | Blocks / enables |
|---|---|---|
| 1 | Tenant + authorized workspace context; first-class Dataset resource | all authenticated product work |
| 2 | `prem3-api` skeleton, typed problems, request IDs, BFF contract | authenticated frontend integration |
| 3 | OpenAPI + schema export + generated client/types | all live integration |
| 4 | Clerk verification, tenant mapping, organization membership | `/app`, project access |
| 5 | Plan catalog + entitlements (`max_active_projects`) | project creation, pricing/billing UI |
| 6 | Stripe Checkout/Portal + webhook subscription projection | monthly paid conversion |
| 7 | PlanningRun/question/provenance/compiler + `PlanningReportV1` | authenticated acquisition/data-gap workflow |
| 8 | Registry overlay/search + Planner manifest export | authenticated provider resolution + public Planner sync |
| 9 | Dataset uploads + evaluation creation/history | Ready-to-assess paid path |
| 10 | Taskmaster server read model + Meridian Integration projection | final execution/product surface |

The public marketing/Planner work can proceed in parallel once the Planner manifest schema and commercial terminology are frozen. Claude must not invent unavailable backend behavior to unblock visible UI.

## 10. Non-goals

- Real-time collaborative editing of a plan.
- Usage-based or per-Evaluation commercial billing.
- A second anonymous server-side planning system duplicating the public Planner.
- Mobile applications.
- Server-side rendering of the authenticated Taskmaster (client-side fetch is sufficient).
- Direct customer SQL access to their BigQuery consumption dataset.
- Replacing the ADK developer/CLI path used by `scripts/run_dataset_a.py`. That path must keep working; it is the reproducible proof surface.

## 11. Mission 2 backend freeze (M2-14)

Backend architecture is frozen. Frontend implements against generated OpenAPI and
`contracts/schema/*`. Do not invent readiness or dispatch semantics.

Authoritative Evaluation progress fields live on `EvaluationResponse.execution`.
Poll `GET /v1/runs/{run_id}`. HTTP 202 after create is enqueue success, not
`MODEL_READY`. `dispatch_status=SUCCEEDED` is not `MODEL_READY`.

Interactive Clerk Organization UX and Google provider flows are frontend integration,
then live provider qualification. They are not backend schema gaps.

See `docs/backend/M2_14_FRONTEND_CONTRACT_HANDOFF.md` and
`docs/backend/M2_MISSION_2_ACCEPTANCE_FREEZE_REPORT.md`.
