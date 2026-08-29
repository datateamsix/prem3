# Project Home read model

Frontend must not assemble Project truth from many endpoints or invent readiness.

```text
GET /v1/projects/{project_id}/home
GET /v1/projects/{project_id}/home?cycle_id={cycle_id}
GET /v1/workspaces/{workspace_id}/home
```

`cycle_id` selects a Project Home projection over the same contract. The payload always distinguishes:

- `current_cycle` — latest operational MeasurementCycle
- `selected_cycle` — the cycle being viewed (`cycle_id` or `current_cycle` when omitted)
- `is_current_cycle` — `selected_cycle` is the latest cycle

Business IQ, Data Foundation, MeasurementTracks, attention, and recent-change cycle events are bound to `selected_cycle`. A historical cycle uses its pinned Business IQ snapshot and cycle-scoped coverage. Live source health and current `MODEL_READY` evidence do not rewrite that analytical state. Unknown or cross-tenant/cross-Project cycles return the existing 404.

Planning capabilities remain Project-level (not cycle-scoped). `FORECASTING` may be `AVAILABLE_TO_CONFIGURE` while the selected-cycle Forecast Track is `NEEDS_FOUNDATION`: tenants may configure forecast intent before that cycle's foundation is ready. The Track cannot execute without the selected cycle's foundation.

`ProjectHomeReadModel` is server-owned and includes `generated_at`, empty `intelligence_summary.items` until a later engine exists, server-owned `attention_items`, and `recent_changes` derived from control-plane / cycle / evaluation timestamps. It projects:

- Project metadata
- current and selected MeasurementCycle (`is_current_cycle`)
- Project Measurement Home (read contract over existing Drive + `prem3_modeling` bindings)
- `namespace_conflict=true` when two ACTIVE Projects claim the same `<gcp_project>.prem3_modeling`
- Business IQ summary
- Data Foundation summary
- MeasurementTrack summaries
- planning capability availability
- attention items
- recent changes derived from control-plane / cycle / evaluation timestamps
- empty intelligence items until a later engine exists

Overview routes:

```text
GET /v1/projects/{id}/business-iq/overview
GET /v1/projects/{id}/data-foundation/overview
GET /v1/projects/{id}/cycles/{cycle_id}/coverage
```

Next actions are typed. Frontend renders them. `LOCKED` is not used.

Availability states are presentation/availability. They do not replace `BUSINESS_CONTEXT_READY`, `FOUNDATION_SOURCE_READY`, `DATA_FOUNDATION_READY`, `IMPORT_READY`, `MODEL_READY`, or `PUBLISH_READY`.
