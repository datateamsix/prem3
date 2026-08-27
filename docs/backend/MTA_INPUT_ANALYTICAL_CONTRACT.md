# MTA input analytical contract

**Mission:** IG-04 → M5-03

IG-04 produces the governed analytical input plane. It does not run attribution and does not emit `MTA_RESULT_READY`.

## Handoff (`M5_03AnalyticalHandoff`)

- Artifact refs (`ga4_sessions_unified_*`, `mta_session_touchpoints_*`, `mta_journeys_*`)
- Topology and identity-rule fingerprints
- Available `market_ids[]` / `channel_ids[]` / `campaign_ids[]`
- Session / touchpoint / journey counts with explicit denominators on the readiness receipt
- Issues including `MULTI_MARKET_JOURNEY`

Campaign-level Markov validity remains M5-03 preflight. Do not change DP6 or the M5-01 operational MERGE chain.

## Policies imported, not forked

`SessionTrafficSourcePolicy`, `GA4SettlementPolicy`, `IdentityStrategy`, `DirectTreatmentPolicy` from MTA contracts. Session construction is preprocessing, not attribution.

## Isolation

MTA APIs remain method runs. Data Foundation compile APIs remain MMM foundation plans. Identity Graph owns `/identity-graph/analytics/*`.
