# Planning API and private response contract

Canonical namespace:

```text
/v1/projects/{project_id}/investment-plans
/v1/projects/{project_id}/investment-portfolio
/v1/projects/{project_id}/investment-optimizations
```

`/v1/workspaces/{workspace_id}/...` is a documented alias of the same state machine. `project_id == workspace_id`.

P6-01 registers real Investment Plan handlers on the canonical namespace. Workspace paths are a same-state alias (`include_in_schema=False`). `GET /v1/projects/{project_id}/investment-portfolio` is registered (P6-02/P6-03). `investment-optimizations` remain unregistered until P6-04. `GET .../view` is not registered.

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

Contract fingerprints at P6-03:

- `contracts/openapi.yaml` sha256 `3677b08a76d663049564f2eb1b2f61ff7f465c43cb9247f5c1e40e35e4b7665b`
- `contracts/schema/planning.schema.json` sha256 `e0315ce91459b561a8b9c14ff9d9f1b43696a95ece799a892d4a76d8849a218a`

Generated schemas live in `contracts/schema/planning.schema.json`.

Query filters may carry `fiscal_year`, `quarter`, `market_id`, `channel_id`, `baseline_kind`, and refs. URLs must not carry amounts.

Amount-bearing responses use `Cache-Control: private, no-store` and `Pragma: no-cache`.
