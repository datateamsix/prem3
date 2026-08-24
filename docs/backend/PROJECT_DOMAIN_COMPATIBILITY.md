# Project domain compatibility

Storage key remains `workspace_id`. Customer-facing unit is **Project**.

```text
Workspace / workspace_id   →   Project / project_id (alias, same value)
```

There is one control-plane document. `/v1/workspaces` and `/v1/projects` read and write that document.

Do not treat `project_id` as a second identifier namespace. A future versioned migration may introduce distinct `project_id` values; this mission does not.

## Status

`DRAFT` is reserved. Creation remains `ACTIVE` and still consumes `max_active_projects`.

`ARCHIVED` decrements active capacity. Receipts, evaluations, and historical tracks remain. Archive does not delete customer data.

Planner (`max_active_projects = 0`) still cannot create a Project.

Archive/reactivate updates `active_workspace_count` atomically with status. Repeating `ARCHIVED` does not decrement twice.

Project Measurement Home is a read contract over existing Drive / BigQuery bindings. Two ACTIVE Projects may not claim the same `<gcp_project>.prem3_modeling` namespace; the Home contract reports `namespace_conflict`. Archived Projects do not consume that namespace. Runtime use of a `CONFLICT` binding fails closed (`MEASUREMENT_HOME_CONFLICT`).

## Metadata

Project fields (`scope_type`, `brand_name`, markets, currency, timezone) are identity/scope only. Business IQ remains canonical business truth.
