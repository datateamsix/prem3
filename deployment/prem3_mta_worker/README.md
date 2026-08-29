# prem3-mta-worker

Cloud Run Job for MTA attribution runtime, plus an optional HTTP launch
service used by Cloud Tasks OIDC.

- Job env: `PREM3_MTA_DISPATCH_ID` (only trusted input)
- Job env: `PREM3_MTA_CLOUD_RUNTIME=1` (set by the launcher override)
- Job entrypoint: `python -m app.tools.mta_model_worker`
- Launch service: `python -m app.tools.mta_launch_service`
- Library pin: Marketing-Attribution-Models tag `v1.0.11`

Image:

`us-central1-docker.pkg.dev/modelready-m3/cloud-run-source-deploy/prem3-mta-worker`

Do not overwrite Cloud Run service `prem3-api` or historical `modelready-m3`.
The launch HTTP service is named `prem3-mta-launch`.
