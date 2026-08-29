# MTA Music Center Demo Results

Live proof path for M5-02 (does not rewrite the DP6 worker):

1. Read operational journeys from `modelready-m3.prem3_modeling.mta_journeys`
   produced by the M5-01A SYNTHETIC_DEMO refresh of
   `modelready-m3.analytics_music_center_synthetic`.
2. Invoke the existing `MTAService` / `DP6MAMAdapter` production path.
3. Compile `MTAResultsSnapshot` with `evidence_authority=SYNTHETIC_DEMO`.
4. Derive channel roles from journey-position evidence. Do not hardcode
   Paid Social as INTRODUCER.
5. `ai_search` appears iff source journeys contain that canonical `channel_id`.
6. If Shapley is preflight-blocked, record typed `NOT_RUN` /
   `BLOCKED_BY_PREFLIGHT` — never fabricate zeros.

Integration tests: `tests/integration/test_mta_m5_02_live_bq.py` (marker `live_bq`).

Proof artifact (written by the live suite when run):
`evaluation/meridian_music_center_mta_results_proof.json`.

## Recorded live proof (2026-08-25)

Operational table `modelready-m3.prem3_modeling.mta_journeys` contained **3**
converted journeys. Channel IDs present: `search_paid`, `direct`,
`social_paid`, `social_organic`, `search_organic`. `ai_search` was not in
source journeys, so it is not in the snapshot.

| Field | Value |
|---|---|
| `result_snapshot_id` | `mrs_11ec341be2c8486a` |
| `run_id` | `mtrun_e5576268861b486e` |
| `fingerprint` | `98b03e943819c15ee1e93be1cc560219e6bf2364a6a5abcf79903c948bff0304` |
| `evidence_authority` | `SYNTHETIC_DEMO` |
| Models completed | FIRST_TOUCH, LAST_TOUCH, LINEAR, MARKOV, SHAPLEY |
| Shapley | `AVAILABLE` |
| Channel Registry V1 | `e117fb47a89eba9ae7915b4f7e062b7e59fd01672046066cef2d125e0475aa2b` |
| Brief | `mdib_a6ab6d0165b847173f8e` |

Roles were derived from position/volume features (not hardcoded names). With
n=3 journeys, every channel is below `volume_floor=3`, so labels include
`LOW_OBSERVABILITY`. `search_paid` and `social_paid` also received
`MODEL_SENSITIVE` from share dispersion.
