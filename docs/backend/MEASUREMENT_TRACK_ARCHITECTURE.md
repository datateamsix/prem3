# MeasurementTrack architecture

A **MeasurementCycle** is a versioned business / evidence / decision context. It is not an MMM run.

```text
Project
  └── MeasurementCycle
        ├── MeasurementTrack MMM
        ├── MeasurementTrack MTA
        └── MeasurementTrack FORECAST
```

One active track of each type per cycle. The uniqueness write is atomic (in-memory lock / Firestore transaction). Same `track_id` may be rewritten; a second `track_id` of the same type is rejected. `ensure_tracks_for_cycle` is idempotent. Multiple immutable runs may exist inside a track.

Track mutation contract:

- exact config replay is idempotent and does not bump `configuration_version`
- metadata (`status`, run/receipt pointers) may update without a version bump
- once a version is consumed by a run, receipt, or accepted artifact, that version's analytical config is immutable
- a material config change creates a new `configuration_version` and keeps the consumed revision
- `resolve_track_config_for_run` returns the exact config that run consumed

A conflicted Project Measurement Home (`namespace_conflict`) cannot be used as resource authority for Google/BigQuery/Drive use, Data Foundation provisioning, import/materialization, publish, or Track execution.

## Types

| Type | This mission |
|---|---|
| MMM | Thin adapter over existing evaluations / MODEL_READY evidence |
| MTA | Config skeleton + availability evaluator |
| FORECAST | Config skeleton + availability only |

Scenario Simulation and Budget Optimization are planning capabilities, not tracks.

Forecast availability is intentionally split:

- MeasurementTrack `FORECAST` is cycle-scoped and foundation-gated. If the selected cycle is not `DATA_FOUNDATION_READY`, the Track is `NEEDS_FOUNDATION` and cannot execute.
- Planning `FORECASTING` is Project-level configure-before-foundation. An entitled tenant may be `AVAILABLE_TO_CONFIGURE` before any given cycle's foundation is ready. That CTA is not a claim that the selected-cycle Forecast Track can run.

## Persistence

Firestore (and the in-memory twin): `tenants/{tenant}/workspaces/{workspace}/measurement_tracks/{track_id}`.

MMM domain state stays `MODEL_READY` when deterministic evidence exists. Track `SUCCEEDED` / dispatch success is never `MODEL_READY`.
