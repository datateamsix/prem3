# prem3-mta-worker

Cloud Run Job for MTA attribution runtime.

- Env: `PREM3_MTA_DISPATCH_ID` (only trusted input)
- Entrypoint: `python -m app.tools.mta_model_worker`
- Library pin: `marketing-attribution-models==1.0.11`
