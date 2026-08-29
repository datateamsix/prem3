# MTA Real Runtime Authority

`evidence_authority` describes the **source** (e.g. `SYNTHETIC_DEMO`).
`computation_authority` describes the **attribution runtime**:

| Value | Meaning |
|---|---|
| `REAL_PINNED_RUNTIME` | Exact `marketing_attribution_models==1.0.11` executed |
| `TEST_FAKE_RUNTIME` | Explicit adapter `fake=True` path |

LIVE and SYNTHETIC_DEMO execution cannot use the fake adapter
(`MTA_FAKE_RUNTIME_NOT_ALLOWED`). Environment variables cannot override that.

Unit tests may use `DP6MAMAdapter(fake=True)` when `runtime_mode=FAKE_TEST`.

Historical snapshot `mrs_11ec341be2c8486a` remains `TEST_FAKE_RUNTIME` /
M5-02 fake-adapter proof. It is not reclassified as real DP6 evidence.
