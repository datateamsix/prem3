# Planning API and private response contract

Canonical namespace:

```text
/v1/projects/{project_id}/investment-plans
/v1/projects/{project_id}/investment-portfolio
/v1/projects/{project_id}/investment-optimizations
```

`/v1/workspaces/{workspace_id}/...` is a documented alias of the same state machine. `project_id == workspace_id`.

P6-00 does not register fake HTTP 200 handlers for these paths. Generated schemas live in `contracts/schema/planning.schema.json`.

Query filters may carry `fiscal_year`, `quarter`, `market_id`, `channel_id`, `baseline_kind`, and refs. URLs must not carry amounts.

Amount-bearing responses use `Cache-Control: private, no-store` and `Pragma: no-cache`.
