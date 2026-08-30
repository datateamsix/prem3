# MTA Journey Compiler

BigQuery compiles observable journey evidence from governed GA4 exports before DP6 attribution.

## Layers

- **Operational:** continuous `mta_sessions` / conversions / touchpoints / journeys / path frequencies + watermark (MERGE / bounded rebuild).  
- **Analytical run:** immutable run-scoped snapshots keyed by InputContract + AnalysisConfig + channel registry/UDF versions.

## Policies pinned per run

Settlement (`DAILY_SETTLED`), traffic-source policy, sessionization, identity, lookback vs conversion period, Direct treatment, nonconverting-path inclusion.

## Determinism

Journey IDs are fingerprinted. Invalid touchpoint/conversion timestamp order fails closed (`JOURNEY_COMPILATION_ERROR`) — no silent re-sort.
