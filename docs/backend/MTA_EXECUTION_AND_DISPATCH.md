# MTA Execution and Dispatch

Mirrors Meridian durable async pattern with MTA vocabulary.

```
API start_run → MTAExecutionPlan → Cloud Tasks ({dispatch_id})
  → OIDC POST /internal/v1/mta-dispatches/{id}/launch
  → Cloud Run Job prem3-mta-worker (PREM3_MTA_DISPATCH_ID)
  → server-owned plan restore → DP6 → BQ outputs → read-back → MTARunReceipt
```

Caller cannot supply tenant, GCP project, BQ destinations, grouping routine, models, or worker image as authority.

Dispatch statuses: PENDING / QUEUED / LAUNCHED / COMPLETE / FAILED.  
Run statuses: PENDING / QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELED.
