# prem3-meridian-model-worker

Dedicated Cloud Run Job image for approved Meridian posterior sampling.

Pin:

- `google-meridian==1.8.0`
- Python 3.12 (same family as the official EDA worker; prem3-api remains 3.13)
- TensorFlow family resolved by the pinned Meridian release

This image must not install `google-adk` and must not execute generated Python.

GPU is attached at Cloud Run Job deploy time (`GPU_STANDARD` / L4 preferred).
`LIVE_GPU_PROOF_BLOCKED` until `prem3-meridian-model-worker` is deployed and an
authorized L4 job is executed. Attempted: `gcloud run jobs describe` in
`us-central1` returned job not found.
