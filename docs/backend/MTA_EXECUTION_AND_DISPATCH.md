# MTA Execution and Dispatch

Mirrors Meridian durable async pattern with MTA vocabulary.

```
API start_run → Firestore mta_runtime bundle → Cloud Tasks ({dispatch_id})
  → OIDC POST /internal/v1/mta-dispatches/{id}/launch
  → Cloud Run Job prem3-mta-worker (PREM3_MTA_DISPATCH_ID, PREM3_MTA_CLOUD_RUNTIME=1)
  → hydrate plan → exact DP6 1.0.11 → BQ outputs → read-back → MTARunReceipt
```

The launch HTTP service for Cloud E2E is `prem3-mta-launch` so historical
`prem3-api` is not overwritten. `computation_authority` is `REAL_PINNED_RUNTIME`
when the worker uses `DP6MAMAdapter(fake=False)`.

Caller cannot supply tenant, GCP project, BQ destinations, grouping routine, models, or worker image as authority.

Dispatch statuses: PENDING / QUEUED / LAUNCHED / COMPLETE / FAILED.  
Run statuses: PENDING / QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELED.
