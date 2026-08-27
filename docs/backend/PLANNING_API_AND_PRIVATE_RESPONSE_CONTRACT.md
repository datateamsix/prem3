# Planning API and private response contract

Canonical namespace:

```text
/v1/projects/{project_id}/investment-plans
/v1/projects/{project_id}/investment-portfolio
/v1/projects/{project_id}/investment-optimizations
```

`/v1/workspaces/{workspace_id}/...` is a documented alias of the same state machine. `project_id == workspace_id`.

P6-01 registers real Investment Plan handlers on the canonical namespace. Workspace paths are a same-state alias (`include_in_schema=False`). `GET /v1/projects/{project_id}/investment-portfolio` is registered (P6-02/P6-03). P6-04 registers mapping and readiness under the same portfolio prefix. `investment-optimizations` remain unregistered until P6-05. `GET .../view` is not registered.

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

Bodies accept `portfolio_snapshot_id`, optional Project-scoped `model_version_id`, and canonical-ID mapping overrides. Clients cannot supply `tenant_id`, workspace-as-authority, amounts, or model artifact location. Responses carry status, IDs, checks, issues, coverage summary, receipt_id, and fingerprints. No budget values. No optimizer execution route.

Contract fingerprints at P6-04:

- `contracts/openapi.yaml` sha256 `f9dca9867abdb90937a36f19d36be7b4dfffac0dddad4f7581f6d80256dda213`
- `contracts/schema/planning.schema.json` sha256 `4a64123be72d30456745dac46711c51044db2f88ae3ec62dc53e8bd8af893bcd`

Generated schemas live in `contracts/schema/planning.schema.json`.

Query filters may carry `fiscal_year`, `quarter`, `market_id`, `channel_id`, `baseline_kind`, and refs. URLs must not carry amounts.

Amount-bearing responses use `Cache-Control: private, no-store` and `Pragma: no-cache`.
