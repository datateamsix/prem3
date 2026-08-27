# Planning API and private response contract

Canonical namespace:

```text
/v1/projects/{project_id}/investment-plans
/v1/projects/{project_id}/investment-portfolio
/v1/projects/{project_id}/investment-optimizations
```

`/v1/workspaces/{workspace_id}/...` is a documented alias of the same state machine. `project_id == workspace_id`.

P6-01 registers real Investment Plan handlers on the canonical namespace. Workspace paths are a same-state alias (`include_in_schema=False`). `investment-portfolio` and `investment-optimizations` remain unregistered until P6-02/P6-04. `GET .../view` is not registered in P6-01; portfolio assembly is P6-02.

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

Contract fingerprints at P6-01 HTTP checkpoint:

- `contracts/openapi.yaml` sha256 `6fd1fae50d435702374f8688e155432ce79e79cd4628ef13b5d92fc063539a40`
- `contracts/schema/planning.schema.json` sha256 `9213a388832794f259a579416b6e8c962895e2e7a92da3d23873aae597df24ec`

Generated schemas live in `contracts/schema/planning.schema.json`.

Query filters may carry `fiscal_year`, `quarter`, `market_id`, `channel_id`, `baseline_kind`, and refs. URLs must not carry amounts.

Amount-bearing responses use `Cache-Control: private, no-store` and `Pragma: no-cache`.
