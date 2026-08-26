# Music Center Real DP6 Proof

M5-02A closes the fake DP6 seam with exact `marketing_attribution_models==1.0.11`
(GitHub tag `v1.0.11`) and a later Music Center SYNTHETIC_DEMO window.

Worktree: `C:/Users/zroda/Desktop/prem3-m5-02a`  
Branch: `feature/prem3-m5-02a-real-dp6-demo-closure`  
Parent SHA: `9371c798ae40e972d9244743442694d1bfdc92ed` (M5-02). Working tree is uncommitted.

| Class | Result |
|---|---|
| UNIT | `tests/unit/test_mta_m5_01_runtime.py`, `test_mta_m5_01a_governance.py`, `test_mta_m5_02_results.py`, `test_mta_m5_02a_dispatch.py`. Fake adapter remains explicit `fake=True`. |
| REAL_DP6_LOCAL | `tests/unit/test_mta_m5_02a_real_dp6.py` (`pytest -m real_dp6`). `_run_real` does not call `_run_fake`. |
| LIVE_BQ | 6/6 passed. Fixture v2 `2024-09-01`–`2024-09-30` on `analytics_music_center_synthetic`, existing GA4 compiler refresh, real adapter, BQ write/read-back, snapshot + brief + 10 P0 visualizations. Proof: `evaluation/meridian_music_center_mta_real_dp6_demo_proof.json`. |
| CLOUD_E2E | **PASSED.** Cloud Tasks OIDC → `prem3-mta-launch` → Job `prem3-mta-worker` → real DP6 → BQ → receipt. Proof: `evaluation/meridian_music_center_mta_real_dp6_cloud_e2e_proof.json`. In-process `execute_fit_dispatch` is not this proof. |

## LIVE_BQ snapshot

| Field | Value |
|---|---|
| result_snapshot_id | `mrs_7cf40a6ab65a458a` |
| brief_id | `mdib_448b9ff30a58b3262dc7` |
| run_id | `mtrun_a0e776bb3efa44f4` |
| evidence_authority | `SYNTHETIC_DEMO` |
| computation_authority | `REAL_PINNED_RUNTIME` |
| journey_count | 88 |
| shapley | AVAILABLE |
| P0 visualizations | all 10 |
| historical fake snapshot | `mrs_11ec341be2c8486a` (untouched) |

## CLOUD_E2E

| Field | Value |
|---|---|
| status | PASSED |
| dispatch_id | `mtdsp_fe1e35c849164327` |
| run_id | `mtrun_dc4cb0face0c4b72` |
| receipt_id | `mrcpt_b0aa00aa988009343cb3` |
| receipt_status | SUCCEEDED |
| computation_authority | `REAL_PINNED_RUNTIME` |
| result_snapshot_id | `mrs_8285f1fef8064bea` (compiled from worker BQ outputs) |
| brief_id | `mdib_f97652c1f43f72be2b8a` |
| cloud_task | `projects/modelready-m3/locations/us-central1/queues/prem3-evaluation-dispatch/tasks/prem3-mta-mtdsp_fe1e35c849164327` |
| launch_url | `https://prem3-mta-launch-vkcd3cbiea-uc.a.run.app` |
| job | `prem3-mta-worker` |
| runtime_sa | `m3-runtime@modelready-m3.iam.gserviceaccount.com` |
| dispatcher_sa | `prem3-evaluation-dispatcher@modelready-m3.iam.gserviceaccount.com` |
| pinned image | `us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/prem3-mta-worker@sha256:bb1d93f1a059fd0a5bf3c3f7b35c8f805b854e14402e44d8a39ff6353c99f8d1` |

`prem3-api` was not overwritten. Launch HTTP service is `prem3-mta-launch`.

## Authority

- `evidence_authority = SYNTHETIC_DEMO` (source/demo)
- `computation_authority = REAL_PINNED_RUNTIME` (this run)
- Historical snapshot `mrs_11ec341be2c8486a` remains `TEST_FAKE_RUNTIME` and is not reclassified
- June 2024 v1 `events_*` shards are not overwritten
