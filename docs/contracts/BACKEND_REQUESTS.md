# Backend Contract Requests

**Owner:** shared frontend/backend Mission 2 contract registry
**Canonical architecture:** `docs/context/14_MULTITENANCY_AND_IDENTITY_BOUNDARY.md`,
`docs/context/15_FRONTEND_INTEGRATION_AND_SERVICE_SURFACE.md`,
`docs/context/16_AUTH_BILLING_AND_ENTITLEMENTS.md`
**Purpose:** a living registry of backend capabilities the frontend depends on but does not
implement. Rule: **never invent missing backend behavior in frontend code — file or update a
request here instead.** Do not create a second overlapping request file.

Status values: `NOT STARTED` · `IN PROGRESS` · `AVAILABLE` · `SUPERSEDED` · `BLOCKED`.

REQ-001 through REQ-010 originated in the Mission 2 frontend prompt pack. REQ-011 through
REQ-015 are specified here as first-class Mission 2 commercial/resource contracts.
REQ-016 through REQ-018 are Google connections and import/publish governance.

---

## SUPERSEDED — anonymous Planner backend session / claim handshake

**Status:** SUPERSEDED (2026-08-17)

Any earlier requirement that public `/planner`:

- create an anonymous backend PlanningRun or session;
- receive `TenantContext` (including a fictional `ANONYMOUS` tenant);
- write GCS/Firestore/BigQuery state;
- later "claim" that anonymous state after Clerk sign-up;

is **SUPERSEDED**. Public `/planner` is deterministic/local-static. It makes no `prem3-api`
call at anonymous runtime. Conversion creates or selects an authenticated MMM Project only
after verified identity **and** a passing `max_active_projects` check. Imported Planner
fields are candidate/unconfirmed until backend provenance confirms them.

If a request below still mentions sessions/auth, that language applies to **authenticated**
`prem3-api` context only — never to anonymous `/planner`.

---

## P0 — before live auth/planning integration

### REQ-001 — Contract schema export

**Status:** IMPLEMENTED — EXPANDED WITH API PRESENTATION MODELS (2026-08-17)
**Exporter:** `scripts/export_contracts.py` (`app/tools/schema_export.py`)
**Check:** `python scripts/export_contracts.py --check` or `python scripts/check_contracts.py`
**Artifacts:** `contracts/schema/`

Generated from live Pydantic models. Do not hand-edit the JSON Schema files.

| Artifact | Public roots | Python source |
|---|---|---|
| `response.schema.json` | `StructuredResponse` | `app.response.contracts` |
| `state.schema.json` | `DurableRunState`, `RunStatusEvent`, `Issue`, `Transformation`, `ReadinessReceipt`, `BigQueryPublishReceipt`, `LearningReceipt` | `app.core.contracts` (`RunStage` via `DurableRunState.stage`) |
| `intelligence.schema.json` | `Prem3PreEdaFinding`, `SemanticQuestion`, `GuidedRemediationItem`, `DimensionalStatus`, `DomainView`, `DomainViewDiff` | `app.intelligence.contracts` + `app.domain.intelligence.models` |
| `mel.schema.json` | `ExperienceEpisode`, `ExperienceReflection`, `PromotionReceipt`, `ExperienceApplication`, `HoldoutManifest` | `app.mel.models` |
| `api.schema.json` | `ProblemDetail`, `MeResponse`, plan/workspace/dataset/billing/Google/import-publish presentation models | `app.service.models` + `app.service.errors` |

Firestore persistence models are not public roots.

### TenantContext / WorkspaceContext / canonical path foundation

**Status:** IMPLEMENTED — INTERNAL PRIMITIVE (2026-08-17)
**Modules:** `app/core/tenancy.py`, `app/core/resource_paths.py`, `app/core/identifiers.py`,
`app/core/developer_bootstrap.py`

Request-scoped `TenantContext` and `WorkspaceContext` plus fail-closed identifier/path
builders exist. They are **not** public REQ-001 schema roots and are **not** `/v1/me`
payloads. The public Planner still receives no TenantContext.

This is a prerequisite for REQ-003, REQ-011, signed uploads, and repository/tool authority
refactor. It does **not** implement Clerk, Firestore persistence, FastAPI, entitlements, or
OpenAPI.

`MODELREADY_ORGANIZATION_ID` / `MODELREADY_WORKSPACE_ID` remain developer/CLI bootstrap
inputs only (`bind_developer_bootstrap()`). They do not bind `require_tenant()` /
`require_workspace()`.

### Dataset execution authority (server-owned ExecutionContext)

**Status:** IMPLEMENTED — INTERNAL PRIMITIVE (2026-08-17)
**Modules:** `app/core/execution_context.py`, `app/core/legacy_execution.py`,
`app/core/run_repository.py`

Registered `root_agent` tools no longer accept tenant, workspace, Dataset,
package URI, GCS/filesystem path, BigQuery destination, plan, or entitlement
arguments. Evaluation identity comes from bound `ExecutionContext`.
`RunRepository` derives Mission 2 and legacy artifact prefixes from that context
via `app/core/resource_paths.py`. `Settings` no longer carries organization or
workspace authority fields.

Trusted CLI/cloud-proof scripts may still pass a package URI through
`prepare_legacy_dataset_execution`, which is not registered on `root_agent`.
The already-deployed Cloud Run ADK API cannot bind process `ContextVar`s from
an HTTP prompt; historical cloud proof scripts remain a legacy harness until
`prem3-api` binds execution before agent invocation.

Not claimed: REQ-002, REQ-003, REQ-011, REQ-014.

### Firestore operational control plane

**Status:** IMPLEMENTED — INTERNAL PERSISTENCE (2026-08-17)
**Modules:** `app/control_plane/` (`models`, `repository`, `memory`,
`firestore_repo`, `entitlements`, `layout`, `serialization`, `ids`)

First-class server-owned resources: Tenant, identity-provider organization
mapping, membership projection, MMM Project (`workspace_id`), Dataset,
immutable EntitlementSnapshot, Stripe customer mapping, subscription
projection, processed webhook events, and a minimal DatasetEvaluationRef seam.

`InMemoryControlPlaneRepository` is the CI/primary contract twin.
`FirestoreControlPlaneRepository` targets Native `(default)` in
`us-central1` via ADC / `FIRESTORE_DATABASE`. Optional live proof:
`scripts/qualify_firestore_control_plane.py --execute` (never pytest/CI).

HTTP contracts now live in `app/service/` (`prem3-api`). Persistence models remain
internal. Clerk identity is implemented. Stripe SDK is implemented. Cloud Run
`prem3-api` packaging is in `deployment/prem3_api/`.

### prem3-api FastAPI service

**Status:** IMPLEMENTED — CONTRACT / FAIL-CLOSED SEAMS (2026-08-17)
**Modules:** `app/service/`
**OpenAPI:** `contracts/openapi.yaml` via `scripts/export_openapi.py`
**Local:** `py -3.13 -m uvicorn app.service.app:app --reload --port 8080`
**Docs:** `docs/context/PREM3_API.md`

Clerk session verification is live when `CLERK_SECRET_KEY` is configured;
otherwise identity remains fail-closed. Stripe Checkout/Portal/webhooks are live
when Stripe secrets are configured; otherwise billing remains fail-closed. No ADK
HTTP execution routes.

### REQ-002 — OpenAPI freeze

**Status:** IMPLEMENTED (2026-08-17)
**Artifact:** `contracts/openapi.yaml`
**Check:** `python scripts/export_openapi.py --check` or `python scripts/check_openapi.py`
Generated from the live FastAPI application. Deterministic. CI drift-protected.
Does not imply live Clerk/Stripe.

### REQ-003 — Identity `/v1/me` and authenticated context

**Status:** IMPLEMENTED — CLERK SESSION + ORG MAPPING + MEMBERSHIP (2026-08-17)
**One-line description:** identity `/v1/me` and authenticated context.
Clerk session tokens are verified with `clerk-backend-api==6.0.1`
(`authenticate_request`, `accepts_token=["session_token"]`). Organization →
PreM3 `tenant_id` mapping and current Clerk membership are enforced. `/v1/me`
returns presentation-safe tenant/plan/capacity. Client-supplied tenant
authority is rejected. Identity webhook: `POST /v1/webhooks/identity`.
Remaining: dedicated tenant-deletion workflow (org-deleted only disables
access); live Clerk sandbox qualification is optional and not required.
**Scope:** authenticated `prem3-api` only. **Does not** apply to public `/planner`.
**Needs specification:** response shape — current subscription/plan, entitlement projection
(`max_active_projects`, active project count), organization/`tenant_id` mapping (internal),
authorized MMM Project list. Tenant is resolved from the verified Clerk credential, never
from the request body, query, or URL.
**SUPERSEDED portion:** any reading that `/v1/me` or a sibling session endpoint should mint
anonymous Planner backend state or a claim handshake.

### REQ-004 — Question schema

**Status:** NOT STARTED
**One-line description:** question schema.
**Needs specification:** `answer_type` enumeration and generated-question-renderer shape for
authenticated acquisition-planning intake. Must support tri-state YES/NO/UNKNOWN.

### REQ-005 — Field provenance

**Status:** NOT STARTED
**One-line description:** field provenance.
**Needs specification:** per-field provenance shape (user-confirmed vs. extracted/registry/
assumed/candidate-from-planner-import).

### REQ-006 — Workflow change

**Status:** NOT STARTED
**One-line description:** workflow change.
**Needs specification:** endpoint(s) for changing an in-progress authenticated planning
workflow path (`POST /v1/planning/runs/{planning_run_id}/change-path`).

## P0 — new commercial model

### REQ-011 — Project/Dataset resource model and endpoints

**Status:** PARTIAL — PERSISTENCE + HTTP CONTRACTS (2026-08-17)
**Needs:**

- First-class MMM Project (`workspace_id`) and Dataset (`dataset_id`) resources persisted in
  Firestore. Project creation is **explicit** and capacity-gated; Clerk user/org provisioning
  must not auto-create a paid MMM Project. **Persistence + capacity + HTTP list/create/get
  contracts exist. Full product lifecycle (uploads, evaluations) still pending.**
- CRUD endpoints per `15_*` §4 (`/v1/workspaces`, `/v1/workspaces/{workspace_id}/datasets`).
- Each Evaluation Run (`run_id`) carries an explicit `dataset_id` foreign key.
  Minimal `DatasetEvaluationRef` seam exists; full history/read model is REQ-014.
- List/detail fields remain contract-backed (name, intended KPI/grain, source count, latest
  evaluation state, latest evaluated timestamp, evaluation count, next action).
- Isolation: tenant from verified credential; `workspace_id` in the URL is a selector that
  must be authorized; unauthorized lookup returns not-found.

### REQ-012 — Public Plan Catalog + entitlement fields

**Status:** IMPLEMENTED (2026-08-18)
**Needs:** none for Mission 08. Frozen field names remain `display_price` / `checkout_eligible` (not the older `monthly_price_display` / `cta_kind` aliases).

- `GET /v1/catalog/plans` is public and returns Planner / Project / Portfolio / Enterprise with capacities 0 / 1 / 10 / 50.
- Paid-plan display amounts come from backend configuration when set. Missing amounts stay `null`; prices are never invented.
- `checkout_eligible` is true only for paid plans with a configured monthly Stripe Price ID.
- Planner remains `max_active_projects=0` and `checkout_eligible=false`.
- Stripe Price / Product / Customer IDs are never returned.
- No commercial run-balance field.
- `/v1/me` reflects the current `EntitlementSnapshot` from the control plane.

### REQ-013 — Stripe Checkout/Portal endpoints and subscription projection

**Status:** IMPLEMENTED (2026-08-18)
**Needs:** none for Mission 08 code. Cloud webhook delivery and live Clerk identity
are optional Mission 09 qualification proofs, not contract changes.

```text
POST /v1/billing/checkout-session
  body: { plan_id, return_path? }
  header: Idempotency-Key?
  -> { url, expires_at? }

POST /v1/billing/portal-session
  body: { return_path? }
  -> { url, expires_at? }

POST /v1/webhooks/billing
```

- Checkout Session creation is keyed by `plan_id`. The backend resolves the monthly Stripe Price. Clients cannot supply Price or Customer IDs.
- One Stripe Customer is mapped per PreM3 tenant (`StripeCustomerMapping`). Stripe Customer IDs are never storage authority.
- Checkout uses `mode=subscription`, quantity 1, and server-owned success/cancel URLs.
- Creating a Checkout Session, or visiting the success URL, does not write entitlement. `/v1/me` changes only after signature-verified webhook reconciliation plus current Subscription readback.
- Webhook processing verifies `Stripe-Signature` against the raw body, claims `ProcessedWebhookEvent` with a bounded lease, retrieves the current Subscription, validates customer + Price mapping, writes `SubscriptionProjection`, and creates a new immutable `EntitlementSnapshot` only when material state changes.
- Portal uses the mapped customer and remains available for billing recovery without `ACTIVE` entitlement.
- Downgrade and cancellation are non-destructive. Existing MMM Projects, Datasets, and artifacts are not deleted.

If older notes used `/v1/billing/checkout` or `/v1/billing/portal`, those names alias the
canonical `checkout-session` / `portal-session` paths in `15_*` §4.

### REQ-014 — Dataset lifecycle, evaluation-run history, and dataset-to-run linkage

**Status:** PARTIAL — UPLOAD + EVALUATION RESOURCE API (Mission 10); EXECUTION DISPATCH IS LATER
**Available:**

- First-class Evaluation create/list/get: `POST|GET .../datasets/{dataset_id}/evaluations`,
  `GET /v1/runs/{run_id}`. Create returns **202** for accepted/created resource only
  (`EvaluationStatus.ACCEPTED`), not agent running and not `MODEL_READY`.
- Signed upload create/get/complete under `.../datasets/{dataset_id}/uploads`. Accepted
  formats: `.csv`, `.parquet`, `.json`. Frontend never constructs `gs://` or holds cloud
  credentials. Complete verifies object metadata and freezes GCS generation.
- Evaluation history scoped to a `dataset_id` (unlimited commercially; operational
  pagination is not a quota). Each Evaluation carries an explicit `dataset_id` /
  `upload_id` linkage and a `run_id`.

**Still later (durable Evaluation dispatch):**

- Durable Evaluation execution/dispatch after HTTP 202 (`ExecutionContext` → ADK).
- Comparable-fields contract for run-to-run comparison; frontend must not infer readiness
  deltas.

### REQ-015 — Deterministic Planner manifest / registry snapshot export

**Status:** NOT STARTED
**Needs:**

- A generated, versioned artifact (proposed:
  `contracts/planner-manifest.schema.json` and
  `frontend/src/generated/planner-manifest.v1.json`) containing approved BUNDLED/PROMOTED
  provider metadata and deterministic planning rules.
- Regenerable from canonical source with CI drift verification.
- **Not** a runtime API. Ships with the frontend so anonymous `/planner` makes zero backend
  calls and never includes tenant overlay data.
- Tenant OVERLAY registry metadata lives in Firestore and is available only inside
  authenticated project workflows.

### REQ-016 — Google Connections

**Status:** IMPLEMENTED — CONNECTIONS + KMS VAULT (2026-08-22)
**Does not implement:** live Google OAuth cloud proof (external credentials).

Clerk-authenticated `POST /v1/integrations/google/oauth/start` (capabilities only; backend
owns scopes). Unauthenticated `GET /v1/integrations/google/oauth/callback` consumes a
single-use hashed state bound to the PreM3 tenant. Encrypted refresh-token vault.
Tenant-scoped `GoogleConnection`. Workspace Drive binding to canonical folder
`prem3-modeling` (folder ID is authority). Workspace BigQuery binding to canonical
dataset `prem3_modeling` (friendly name `prem3-modeling`). User-credential discovery.
Disconnect revokes provider access and encrypted credentials; it does not delete customer
Drive/BQ data or historical receipts.

**M2-12 / M2-12Q:** materialize selected Drive/BigQuery objects into immutable
`DatasetUpload` via `SourceMaterializationReceipt`. Production Google refresh tokens
use `aes-256-gcm+kms-v1`. Live provider proofs remain a separate qualification
level from code readiness.

### REQ-017 — Import Governance / IMPORT_READY

**Status:** IMPLEMENTED — CONTRACT AND EVALUATOR (2026-08-18)
**Does not implement:** materialization.

Typed `PreM3ImportContractV1` (`prem3.import.v1`) + `ImportReadinessReceipt`.
Only `evaluate_import_readiness` may emit `IMPORT_READY`. GCS_UPLOAD compiles from a
verified `prem3_upload_manifest.v1.json` / DatasetUpload. Drive and BigQuery selections
require explicit objects, roles (existing `CanonicalRole` taxonomy), and version identity.
Frontend receives the receipt; it does not recompute readiness.

### REQ-018 — Publish Governance / PUBLISH_READY

**Status:** IMPLEMENTED — CONTRACT AND EVALUATOR (2026-08-18)
**Does not implement:** publishing MODEL_READY artifacts.

Typed `PreM3PublishContractV1` (`prem3.publish.v1`) + `PublishReadinessReceipt`.
Only `evaluate_publish_readiness` may emit `PUBLISH_READY`. Requires MODEL_READY evidence
and a bound Drive `prem3-modeling` and/or BigQuery `prem3_modeling` destination with write
verification. Evaluation ACCEPTED is not MODEL_READY. HTTP publish-readiness does not write
customer data.

**M2-12 / M2-12Q:** publish MODEL_READY + PUBLISH_READY artifacts into bound
`prem3-modeling` / `prem3_modeling` destinations with readback receipts.
Durable Evaluation dispatch remains M2-13.

## P1 — execution workspace

### REQ-007 — Taskmaster read model

**Status:** NOT STARTED
**One-line description:** Taskmaster read model.
**Needs specification:** per-stage `status`, `objective`, `known`, `missing`, `owner`,
`evidence`, `artifacts`, `current_task`. Frontend reconstructs Taskmaster state from this
read model only.

### REQ-009 — Registry search/gaps

**Status:** NOT STARTED
**One-line description:** registry search/gaps.
**Needs specification:** authenticated provider search API and candidate-disambiguation
shape. Public Planner must not call this.

### REQ-010 — Planning response types

**Status:** NOT STARTED
**One-line description:** planning response types.
**Needs specification:** authenticated `PlanningReportV1` family (`MMM_PROJECT_BLUEPRINT`,
`MMM_ACQUISITION_PLAN`, `MMM_DATA_GAP_PLAN`). Distinct from the free Planner's local brief.
Exact schema belongs in future `18_PLANNING_ENGINE_AND_REPORT_CONTRACT.md`.
**Readiness:** Planner brief ≠ `COLLECTION_READY` ≠ `MODEL_READY`. Frontend computes none
of them.

## P1 — collaboration

### REQ-008 — Revocable plan share token

**Status:** NOT STARTED
**One-line description:** revocable plan share token.
**Needs specification:** backend-issued, revocable read-only share token for authenticated
plan detail pages. Optional until specified.
