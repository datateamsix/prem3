# Planning API and private response contract

Canonical namespace:

```text
/v1/projects/{project_id}/investment-plans
/v1/projects/{project_id}/investment-portfolio
/v1/projects/{project_id}/investment-optimizations
```

`/v1/workspaces/{workspace_id}/...` is a documented alias of the same state machine. `project_id == workspace_id`.

P6-01 registers real Investment Plan handlers on the canonical namespace. Workspace paths are a same-state alias (`include_in_schema=False`). `GET /v1/projects/{project_id}/investment-portfolio` is registered (P6-02/P6-03). P6-04 registers mapping and readiness under the same portfolio prefix. P6-05 registers `.../optimizations`. P6-06 registers `.../scenarios` and `.../proposals` (including submit/review/decision and `create-plan-revision`). The unused P6-00 `/investment-optimizations` namespace stays unregistered. `GET .../view` is not registered.

P6-03 extends the portfolio response with `actuals_source_id`, coverage, observations, and plan-vs-actual remaining/variance. Optional query parameter: `fiscal_year`. Client-supplied actual rows are not accepted. Entitlement remains `Feature.PORTFOLIO_VIEW`.

Implemented P6-01 HTTP routes (workspace alias omitted from OpenAPI):

```text
GET    /v1/projects/{project_id}/investment-plans
POST   /v1/projects/{project_id}/investment-plans
GET    /v1/projects/{project_id}/investment-plans/{plan_id}
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/template
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/sources/drive
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/mapping
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/validate
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/save-version
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/approve
POST   /v1/projects/{project_id}/investment-plans/{plan_id}/revise
GET    /v1/projects/{project_id}/investment-plans/{plan_id}/ready
```

`GET /ready` is the capability. A validation receipt may report `INVESTMENT_PLAN_READY` after checks pass; the capability stays `PENDING` until the plan is approved against that receipt and active Drive source version.

Implemented P6-04 HTTP routes (workspace alias omitted from OpenAPI):

```text
POST   /v1/projects/{project_id}/investment-portfolio/model-mapping
GET    /v1/projects/{project_id}/investment-portfolio/model-mapping
GET    /v1/projects/{project_id}/investment-portfolio/model-mapping/{mapping_id}
GET    /v1/projects/{project_id}/investment-portfolio/optimization-readiness
POST   /v1/projects/{project_id}/investment-portfolio/optimization-readiness/evaluate
```

Bodies accept `portfolio_snapshot_id`, optional Project-scoped `model_version_id`, and canonical-ID mapping overrides. Clients cannot supply `tenant_id`, workspace-as-authority, amounts, or model artifact location. Responses carry status, IDs, checks, issues, coverage summary, receipt_id, and fingerprints. No budget values.

Implemented P6-05 HTTP routes (workspace alias omitted from OpenAPI):

```text
POST   /v1/projects/{project_id}/investment-portfolio/optimizations
GET    /v1/projects/{project_id}/investment-portfolio/optimizations
GET    /v1/projects/{project_id}/investment-portfolio/optimizations/{optimization_run_id}
GET    /v1/projects/{project_id}/investment-portfolio/optimizations/{optimization_run_id}/result
```

Create is 202 metadata (`readiness_receipt_id`, optional `idempotency_key`). Result is amount-bearing `MODEL_RECOMMENDED` with `Cache-Control: private, no-store`. Clients cannot supply tenant, paths, budget arrays, or variable maps.

Implemented P6-06 HTTP routes (workspace alias omitted from OpenAPI):

```text
POST   /v1/projects/{project_id}/investment-portfolio/scenarios
GET    /v1/projects/{project_id}/investment-portfolio/scenarios
GET    /v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}
GET    /v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}/comparison
POST   /v1/projects/{project_id}/investment-portfolio/proposals
GET    /v1/projects/{project_id}/investment-portfolio/proposals
GET    /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}
POST   /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/submit
POST   /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/review
POST   /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/decision
POST   /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/create-plan-revision
```

Scenario comparison is amount-bearing and private/no-store. Create-plan-revision returns a **draft** `plan_id`; it does not approve the Investment Plan.

Contract fingerprints at P6-06:

- `contracts/openapi.yaml` sha256 `67eb3380484160207e51a96426993646677d07686dbc8c2b7671e14647775c52`
- `contracts/schema/planning.schema.json` sha256 `2dc39c9e438e889d484d6c2ad2cdc0c60e660fac077c9a620683b0ee610fc464`

Generated schemas live in `contracts/schema/planning.schema.json`.

Query filters may carry `fiscal_year`, `quarter`, `market_id`, `channel_id`, `baseline_kind`, and refs. URLs must not carry amounts.

Amount-bearing responses use `Cache-Control: private, no-store` and `Pragma: no-cache`.
