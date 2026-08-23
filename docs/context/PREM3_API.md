# prem3-api

**Status:** Mission 11 Google connections + import/publish governance foundation — 2026-08-18  
**Does not claim:** Cloud ADK execution, Drive/BigQuery DatasetUpload materialization, MODEL_READY artifact publishing, live Clerk cloud identity (`LIVE_CLERK_CLOUD_IDENTITY_NOT_RUN`), live Stripe Checkout/webhook cloud proof (`LIVE_STRIPE_BILLING_NOT_RUN`), or live Google OAuth (`LIVE_GOOGLE_OAUTH_PROOF` not run unless separately qualified).

`prem3-api` is the authenticated product HTTP boundary. The public `/planner` does not call it.

## Cloud Run

Service `prem3-api` in `modelready-m3` / `us-central1` runs as
`m3-runtime@modelready-m3.iam.gserviceaccount.com`. It is a distinct service from
historical `modelready-m3` (ADK proof). Packaging lives in `deployment/prem3_api/`.

Cloud Run Invoker IAM is disabled so Clerk and Stripe callbacks can reach the
service. Infrastructure reachability is not product authentication:

- public: `/health`, `/readyz`, `/v1/catalog/plans`
- Clerk session: `/v1/me`, workspaces, datasets, uploads, evaluations, runs, Checkout/Portal
- provider signatures: `/v1/webhooks/identity`, `/v1/webhooks/billing`

Cloud runtime (`PREM3_API_RUNTIME=cloud` or Cloud Run `K_SERVICE`) constructs
`FirestoreControlPlaneRepository`, Clerk, and Stripe from deployment
configuration. Local default remains in-memory and fail-closed. `/readyz` reports
adapter configuration and does not call Stripe.

Operator scripts (never pytest/CI):

```text
py -3.13 scripts/provision_prem3_api_cloud.py --execute
py -3.13 scripts/deploy_prem3_api.py --execute
py -3.13 scripts/qualify_prem3_api_cloud.py --execute --write-evidence
```

Evidence is gitignored at `artifacts/deployment/prem3_api_cloud_proof.json`.

## Local run

```text
py -3.13 -m uvicorn app.service.app:app --reload --port 8080
```

Default factory wiring (local):

- `InMemoryControlPlaneRepository` (no Firestore network on import)
- Clerk verifier when `CLERK_SECRET_KEY` is set; otherwise `UnconfiguredIdentityVerifier`
- Stripe Checkout/Portal/webhooks when `STRIPE_SECRET_KEY` is set; otherwise `UnavailableBillingGateway` → `BILLING_PROVIDER_NOT_CONFIGURED`

Cloud factory wiring (`PREM3_API_RUNTIME=cloud` or `K_SERVICE`):

- `FirestoreControlPlaneRepository` against Native `(default)`
- same Clerk/Stripe rules as local, using Secret Manager-injected values
- live Stripe `sk_live_` and Clerk `sk_live_` refused unless explicitly allowed

Public routes work without providers:

- `GET /health`
- `GET /readyz`
- `GET /v1/catalog/plans`

There is no insecure `X-Tenant-ID` development shortcut.

## Clerk configuration (server-only)

Placeholders live in `.env.example`. Never `NEXT_PUBLIC_*` for these values.

- `CLERK_SECRET_KEY`
- `CLERK_PUBLISHABLE_KEY` (optional server copy; frontend publishable key is a frontend concern)
- `CLERK_WEBHOOK_SIGNING_SECRET`
- `CLERK_JWT_KEY` (optional PEM for networkless session verification)
- `CLERK_AUTHORIZED_PARTIES` (comma-separated origins for `azp`)
- `CLERK_API_TIMEOUT_SECONDS` (default 5)

## Public vs authenticated

| Route | Auth |
|---|---|
| `GET /health` | public |
| `GET /readyz` | public |
| `GET /v1/catalog/plans` | public |
| `GET /v1/me` | Clerk session + org + current membership |
| `GET|POST /v1/workspaces` | authenticated |
| Dataset routes under a workspace | authenticated + workspace/dataset auth |
| Upload routes under a dataset | authenticated + workspace/dataset auth |
| Evaluation routes under a dataset | authenticated + workspace/dataset auth |
| `GET /v1/runs/{run_id}` | authenticated + tenant-scoped Evaluation lookup |
| `POST /v1/billing/checkout-session` | Clerk session + org + current membership |
| `POST /v1/billing/portal-session` | Clerk session + org + current membership; Stripe customer mapping required |
| `POST /v1/webhooks/identity` | Clerk signature; no user session |
| `POST /v1/webhooks/billing` | Stripe-Signature; no user session |
| `POST /v1/integrations/google/oauth/start` | Clerk session |
| `GET /v1/integrations/google/oauth/callback` | Google OAuth redirect; no Clerk bearer |
| Google connection/Drive/BigQuery/import-readiness routes | Clerk session + tenant/workspace/dataset auth |

## Google connections and import/publish governance

Canonical depots:

- Drive folder name `prem3-modeling` (authority is the bound folder ID, never the name)
- BigQuery dataset ID `prem3_modeling` (friendly name `prem3-modeling`)

Canonical states remain distinct: **IMPORT_READY**, **MODEL_READY**, **PUBLISH_READY**.
Only deterministic evaluators emit IMPORT_READY / PUBLISH_READY. MODEL_READY is unchanged.

```text
POST /v1/integrations/google/oauth/start
  capabilities + optional workspace_id/dataset_id + relative return_path
  → authorization_url (backend-owned scopes)

GET /v1/integrations/google/oauth/callback
  opaque state + code
  → frontend redirect; tenant/workspace/dataset never taken from Google query params

GET /v1/integrations/google/connections
POST /v1/integrations/google/connections/{connection_id}/disconnect

GET|POST /v1/workspaces/{workspace_id}/integrations/drive
POST /v1/workspaces/{workspace_id}/integrations/drive/setup
POST /v1/workspaces/{workspace_id}/integrations/drive/repair

GET /v1/workspaces/{workspace_id}/integrations/bigquery
POST /v1/workspaces/{workspace_id}/integrations/bigquery/setup
GET .../bigquery/projects
GET .../bigquery/projects/{project_id}/datasets
GET .../bigquery/projects/{project_id}/datasets/{dataset_id}/tables

PUT|GET /v1/workspaces/{workspace_id}/datasets/{dataset_id}/import-binding
POST|GET /v1/workspaces/{workspace_id}/datasets/{dataset_id}/import-readiness
POST /v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations/{run_id}/publish-readiness
```

M2-11 does **not** materialize Drive/BigQuery into DatasetUpload and does **not** publish MODEL_READY artifacts.

Server-only Google configuration (placeholders in `.env.example`):

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_CREDENTIAL_VAULT_KEY`
- optional `GOOGLE_KMS_KEY`

Refresh tokens are envelope-encrypted. They never appear in OpenAPI, receipts, or logs.

## Dataset uploads

## Dataset uploads

Accepted file extensions: `.csv`, `.parquet`, `.json`. Frontend never constructs `gs://` or holds cloud credentials.

```text
POST /v1/workspaces/{workspace_id}/datasets/{dataset_id}/uploads
  → 201 UploadResponse (signed PUT URLs; optional Idempotency-Key)

GET /v1/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}
  → 200 UploadResponse

POST /v1/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/complete
  → 200 CompleteUploadResponse (verify object metadata; generation freeze)
```

Cloud signed-upload proof: qualify with
`py -3.13 scripts/qualify_signed_upload_cloud.py --execute` (`CLOUD_SIGNED_UPLOAD`).
Requires `MODELREADY_RAW_BUCKET` and V4 `signBlob` IAM (see `deployment/prem3_api/README.md`).

## Evaluations

First-class Evaluation resource create/list/get. `POST` returns **202 Accepted** only
after durable Cloud Tasks enqueue. 202 means accepted for durable execution. It does
not mean the worker started, ADK ran, or `MODEL_READY`.

`EvaluationStatus` remains `ACCEPTED`. Execution progression lives on
`EvaluationDispatch` plus existing `DurableRunState` / readiness evidence.

```text
POST /v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations
  → 202 EvaluationResponse (status ACCEPTED + execution view; optional Idempotency-Key)
  → 503 EVALUATION_DISPATCH_UNAVAILABLE if enqueue fails (same run/dispatch on retry)

GET /v1/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations
  → 200 EvaluationListResponse

GET /v1/runs/{run_id}
  → 200 EvaluationResponse with presentation-safe execution view
```

Poll `GET /v1/runs/{run_id}`. Do not use SSE, WebSockets, or `/run_sse`.
`dispatch_status == SUCCEEDED` is not `MODEL_READY`. Backend derives `model_ready`
from deterministic run evidence only.

Internal launch `POST /internal/v1/evaluation-dispatches/{dispatch_id}/launch` is
service-OIDC only (not in public OpenAPI). Clerk customers cannot invoke it.

Local in-process ADK bridge: `LOCAL_AUTHORIZED_ADK_BRIDGE`.
Cloud durable path: `CLOUD_DURABLE_EVALUATION_DISPATCH` +
`CLOUD_AUTHORIZED_ADK_EXECUTION`.

## Authority

```text
Clerk session token
  → authenticate_request(accepts_token=["session_token"])
  → org_id required
  → Clerk Backend API current membership
  → IdentityProviderOrganizationMapping → PreM3 tenant_id
  → TenantContext
```

A verified Clerk Organization with no mapping is provisioned as a PreM3 tenant with Planner entitlement (`max_active_projects = 0`). No MMM Project and no Stripe customer are created.

If Clerk membership lookup is unavailable, protected routes fail closed (`AUTH_PROVIDER_UNAVAILABLE`). Local membership projections do not override current Clerk truth.

Organization deletion marks the tenant `DISABLED` and blocks access. It does not delete workspaces, datasets, GCS, or BigQuery data.

## Identity webhook

`POST /v1/webhooks/identity` verifies Standard Webhooks / Svix headers against the raw body, then claims the event through `ControlPlaneRepository`.

Handled types:

- `organization.created`
- `organization.deleted`
- `organizationMembership.created`
- `organizationMembership.updated`
- `organizationMembership.deleted`

Unknown verified events are acknowledged and ignored. Out-of-order membership events for an unmapped organization are ignored (no guessed tenant). Request-time provisioning or a later `organization.created` heals the mapping.

## Generated contracts

```text
python scripts/export_contracts.py
python scripts/export_openapi.py

python scripts/export_contracts.py --check
python scripts/export_openapi.py --check
```

Frontend handoff artifacts (do not hand-edit):

- `contracts/openapi.yaml`
- `contracts/schema/api.schema.json`
- existing `contracts/schema/*.json`

## Billing

Stripe is the subscription source of truth. PreM3 stores a `SubscriptionProjection` and an immutable `EntitlementSnapshot`. Only the snapshot authorizes product capability.

Server-only configuration (placeholders in `.env.example`):

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PROJECT` / `STRIPE_PRICE_PORTFOLIO` / `STRIPE_PRICE_ENTERPRISE`
- optional catalog presentation amounts/display strings
- optional `STRIPE_PORTAL_CONFIGURATION_ID`
- `PREM3_FRONTEND_ORIGIN` for Checkout/Portal redirects
- `WEBHOOK_CLAIM_LEASE_SECONDS` (default 120)

Pinned SDK: `stripe==15.5.0`. `StripeClient` uses the SDK default API version `2026-07-29.dahlia` (not a separately selected preview).

```text
POST /v1/billing/checkout-session
  plan_id + optional relative return_path
  optional Idempotency-Key
  → Stripe-hosted Checkout URL

POST /v1/billing/portal-session
  optional relative return_path
  → Stripe-hosted Customer Portal URL

POST /v1/webhooks/billing
  raw body + Stripe-Signature
  → claim → retrieve current Subscription → project entitlement
```

Checkout Session creation and the success redirect do **not** write `EntitlementSnapshot`. `/v1/me` reads the Firestore/control-plane snapshot only; it does not call Stripe.

Portal access requires authentication and a Stripe customer mapping. It does not require `ACTIVE` entitlement.

Handled webhook types: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Unknown verified events are acknowledged as ignored.

Optional live test-mode proof: `py -3.13 scripts/qualify_stripe_billing.py --execute` (refuses `sk_live_`).
