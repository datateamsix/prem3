# prem3-api Cloud Run

Distinct Cloud Run service for the authenticated PreM3 product API.

Do **not** deploy this image over `modelready-m3`. That service is the historical
ADK proof surface (`/list-apps`, `/run_sse`). Do **not** change `meridian-eda-worker`.

| Field | Value |
|---|---|
| Project | `modelready-m3` |
| Region | `us-central1` |
| Service | `prem3-api` |
| Runtime identity | `m3-runtime@modelready-m3.iam.gserviceaccount.com` |
| Image repo | `us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/prem3-api` |
| Container | FastAPI / Uvicorn only |

## Ingress vs product authentication

Clerk and Stripe webhooks cannot present a Google Cloud identity token.

`prem3-api` is therefore deployed with Cloud Run Invoker IAM checks disabled
(`--no-invoker-iam-check`). The service URL is infrastructure-reachable.

That is **not** product-route unauthenticated access. FastAPI remains authoritative:

| Route class | Examples | Gate |
|---|---|---|
| Public | `GET /health`, `GET /readyz`, `GET /v1/catalog/plans` | none |
| Clerk session | `/v1/me`, workspaces, datasets, uploads, evaluations, runs, Checkout/Portal | verified Clerk session + current org membership |
| Signed callbacks | `POST /v1/webhooks/identity`, `POST /v1/webhooks/billing` | Clerk Svix / Stripe-Signature |
| Google OAuth callback | `GET /v1/integrations/google/oauth/callback` | opaque single-use state; no Clerk bearer |

Do not add `X-Tenant-ID`. Do not add credentialed wildcard CORS. Browser clients
use the Next.js BFF, not prem3-api directly.

## What is not in this image

- `adk web` / `adk api_server`
- `/list-apps` / `/run_sse`
- Google Meridian / EDA worker
- frontend build
- `MODELREADY_ORGANIZATION_ID` / `MODELREADY_WORKSPACE_ID`

## Build

Tag the image with the git SHA. Do not deploy `latest` as the only identity.

```powershell
$sha = git rev-parse HEAD
gcloud builds submit `
  --config=deployment/prem3_api/cloudbuild.yaml `
  --project=modelready-m3 `
  --substitutions=_TAG=$sha
```

Record the image digest after build.

## Deploy

Use `py -3.13 scripts/deploy_prem3_api.py`. The script attaches `m3-runtime`,
injects Secret Manager references (not secret values), sets non-secret env vars,
and uses `--no-invoker-iam-check`.

Suggested service bounds (not the Meridian 8Gi / 3600s worker):

- CPU `1`
- memory `512Mi`
- timeout `60s`
- min instances `0`
- max instances `3`

## Dependencies

`deployment/prem3_api/requirements.txt` includes `google-cloud-storage` for signed
Dataset uploads (V4 PUT URLs + object metadata verify). Do not add ADK or Meridian
to this image.

## IAM

Mission 09 grants:

- `roles/datastore.user` on project `modelready-m3` to `m3-runtime`
- `roles/secretmanager.secretAccessor` per prem3-api secret, not project-wide

Mission 10 upload signing (same runtime SA):

- `roles/iam.serviceAccountTokenCreator` on `m3-runtime` **self** — required for IAM
  Credentials `signBlob` when issuing GCS V4 signed URLs (no private key file in the image)
- `roles/storage.objectUser` on the raw bucket — already required for object create/read
  during upload complete/verify

Do not grant Owner, Editor, or `roles/datastore.owner`.

Mission 12Q Google credential vault:

- `roles/cloudkms.cryptoKeyEncrypterDecrypter` on
  `prem3/prem3-google-oauth-credentials` for `m3-runtime` only.

Provision with `py -3.13 scripts/provision_prem3_api_cloud.py`.

Qualify signed upload cloud proof (operator only, never pytest/CI):

```powershell
py -3.13 scripts/qualify_signed_upload_cloud.py --execute --write-evidence
```

## Secrets

Secret Manager resources (values never committed):

- `prem3-api-clerk-secret-key` → `CLERK_SECRET_KEY`
- `prem3-api-clerk-webhook-signing-secret` → `CLERK_WEBHOOK_SIGNING_SECRET`
- `prem3-api-stripe-secret-key` → `STRIPE_SECRET_KEY`
- `prem3-api-stripe-webhook-secret` → `STRIPE_WEBHOOK_SECRET`

Optional Google OAuth (M2-11; not required for the current deployed revision):

- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` / `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_KMS_KEY` — required for real Google OAuth. Symmetric key
  `projects/modelready-m3/locations/us-central1/keyRings/prem3/cryptoKeys/prem3-google-oauth-credentials`.
  Production vault algorithm is `aes-256-gcm+kms-v1`. `m3-runtime` has key-level
  `roles/cloudkms.cryptoKeyEncrypterDecrypter` only. Do **not** grant KMS Admin.

`GOOGLE_CREDENTIAL_VAULT_KEY` (hmac-sha256-xor-v1) is retired for production writes.

Ordinary configuration stays in Cloud Run env vars: `FIRESTORE_DATABASE`,
`PREM3_FRONTEND_ORIGIN`, Stripe Price IDs, timeouts, `WEBHOOK_CLAIM_LEASE_SECONDS`,
`MODELREADY_RAW_BUCKET` (required for Dataset uploads).

Prefer Stripe **test mode**. Live `sk_live_` keys fail cloud startup unless
`PREM3_ALLOW_STRIPE_LIVE=1`.

## Qualify

```powershell
py -3.13 scripts/qualify_prem3_api_cloud.py --execute --write-evidence
```

Evidence is gitignored: `artifacts/deployment/prem3_api_cloud_proof.json`.

## Local vs cloud factory

| Mode | Control plane | Identity | Billing |
|---|---|---|---|
| Local default (`PREM3_API_RUNTIME=local`) | in-memory | Clerk if secret set, else unconfigured | Stripe if secret set, else unavailable |
| Cloud (`PREM3_API_RUNTIME=cloud` or `K_SERVICE`) | Firestore `(default)` | Clerk if secret injected | Stripe if secret injected |

Cloud startup probes Firestore with a non-destructive read. Missing
`roles/datastore.user` fails the revision. `/health` is process liveness.
`/readyz` reports adapter configuration and does not call Stripe.
