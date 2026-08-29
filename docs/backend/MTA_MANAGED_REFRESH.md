# MTA Managed Refresh

`MTARefreshWindowPlanner` produces deterministic windows with a calculation_trace:

- Inputs: run_date, settlement_days, source_overlap_days, lookback_window_days, watermark
- Outputs: source window, affected conversion window, fingerprint, trace steps

Lookback expands the **source** window so conversions at the settled horizon can see
full journeys. Regression coverage: lookback 7 / 30 / 60 / 90.

## Semantics

- MERGE sessions/conversions/touchpoints by logical keys (idempotent)
- Bounded rebuild for journeys + path frequencies
- Watermark advances only after compile + MERGE/rebuild + validation + read-back
- Failed refresh retains prior successful watermark

## Scheduled refresh vs MTA run

| Scheduled refresh | MTA run |
|---|---|
| Maintains current governed journey evidence | Immutable attribution evidence for pinned cutoff/config |

Scheduled refresh must not overwrite accepted/published MTA result snapshots.
