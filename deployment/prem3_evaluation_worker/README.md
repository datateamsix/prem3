# prem3-evaluation-worker Cloud Run Job

Long-running Evaluation execution substrate. Cloud Tasks only launches this job.

Do **not** merge this image with `meridian-eda-worker`.
Do **not** deploy this image over historical `modelready-m3`.
Do **not** add this image's ADK dependencies to slim `prem3-api`.

| Field | Value |
|---|---|
| Project | `modelready-m3` |
| Region | `us-central1` |
| Job | `prem3-evaluation-worker` |
| Tasks | 1 |
| Parallelism | 1 |
| Task timeout | 7200 seconds |
| Max retries | 2 |
| CPU | 2 |
| Memory | 4Gi |
| Service account | `m3-runtime@modelready-m3.iam.gserviceaccount.com` |
| Entrypoint | `python -m app.workers.evaluation_worker` |
| Authority env | `PREM3_EVALUATION_DISPATCH_ID` only |

The worker image uses the same `app/` source as `prem3-api` and `app/requirements.txt` (includes ADK). It is a different digest from slim `prem3-api` because the API image must not install ADK.

Provision IAM and the Cloud Tasks queue with `scripts/provision_evaluation_dispatch_cloud.py`.
Deploy with `scripts/deploy_evaluation_worker.py`.
