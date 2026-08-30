# MTA DP6 Runtime

## Pin

- Library: DP6/Marketing-Attribution-Models  
- Version: **1.0.11**  
- License: Apache-2.0  
- Adapter: `app/modeling/mta/adapters/dp6_mam_v1_0_11.py` (`ADAPTER_VERSION`)

Canonical production fails closed if the installed package version differs from the pin.

## Models

Heuristics + Markov are required when configured. Shapley runs only through `ShapleyPreflight` (`ELIGIBLE` / `ELIGIBLE_WITH_TRUNCATION` with explicit `SHAPLEY_PATH_LIMIT_APPLIED`).

## Epistemic language

Attributed / journey credit and removal sensitivity — never causal incrementality or lift.

Worker images install the pin via `deployment/prem3_mta_worker/requirements.txt`. Local unit tests may use the adapter `fake=True` path labeled **SYNTHETIC**.
