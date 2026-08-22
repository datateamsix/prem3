# Real-adapter / external-dependency matrix

**Design freeze:** `foundational-intake-freeze-2026-08-22-v1`  
**Branch:** `feature/prem3-data-foundation-backend`

| Integration | OAuth / credential owner | Connection storage | Token refresh | Revocation | Runtime adapter | Root / project binding | Live proof |
|---|---|---|---|---|---|---|---|
| Google OAuth | Mission 2 `GoogleConnectionService` + `RestGoogleOAuthProvider` | Control-plane `GoogleConnection` + credential vault | Existing refresh | Existing revoke | Reused; no second OAuth stack | n/a | EXTERNAL_DEPENDENCY (authorized tokens) |
| BigQuery | Same OAuth connection | `BigQueryWorkspaceBinding` | Same | Same | `RestBigQueryClient` (metadata, physical, jobs.query preview, dataset create). Tests use `FakeBigQueryClient`. Production `create_app` selects REST when OAuth client is configured; never reports CONNECTED from an in-memory adapter. | Bound customer project + `prem3_modeling` | EXTERNAL_DEPENDENCY — no authorized live project in this environment (`LIVE_CLOUD_PROOF_NOT_RUN`) |
| Google Drive | Same OAuth connection | `DriveWorkspaceBinding.root_folder_id` | Same | Same | `RestDriveClient` (get/create folder, list children, download). Tests use `FakeDriveClient`. | Bound `prem3-modeling` root; folder ID is authority | EXTERNAL_DEPENDENCY — same |
| DV360 / DTV2 | Customer-managed first-party transfer | Foundation Plan `CUSTOMER_MANAGED` + `PrerequisiteNotice` | n/a | n/a | Contract + capability + `PREREQUISITE_REQUIRED` are implemented. Live DTV2 provision is not. | n/a | EXTERNAL_DEPENDENCY |
| Clerk / Stripe SaaS proofs | Mission 2 | Control plane | n/a | n/a | Inherited; not re-proven here | n/a | EXTERNAL_DEPENDENCY (inherited) |

Production rule: if Google OAuth client id/secret are unset, prem3-api keeps fake Google clients for local/CI only and Data Foundation overview stays `NOT_CONNECTED` until a real binding exists. It does not advertise `CONNECTED` from the in-memory warehouse.
