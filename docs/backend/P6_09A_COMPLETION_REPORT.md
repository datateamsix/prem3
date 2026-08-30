# P6-09A completion report

Governed Monte Carlo scenario simulation on the frozen P6-09 HEAD. Native Meridian remains the only optimizer. Simulation evaluates already-feasible candidates; it does not allocate.

## Required lineage block

```text
P6-06 base: e1a9477b9ce57719d56f0d522d3cb85540823362
P6-07 final committed HEAD: be554242b8b64cc702545902949044b163db6030
P6-03A final committed HEAD: eced1acf144c0d469e2c3b316f5391398c879bd8
P6_POST07_ACTUALS_INTEGRATION_READY_HEAD: 591d9969f7459ba7757fe2ca29d70138c92d39b7
P6-08 branch: feature/prem3-p6-08-exposure-risk-delivery-health
P6-08 worktree: C:/Users/zroda/Desktop/prem3-p6-08
P6_08_FINAL_COMMITTED_HEAD: 59d1df2ed40e6be95d526658a8a7fe68032a26d3
P6-09 branch: feature/prem3-p6-09-risk-aware-investment-frontier
P6-09 worktree: C:/Users/zroda/Desktop/prem3-p6-09
P6_09_FINAL_COMMITTED_HEAD: 30c2205bbb137ac1c27319e77973a8013d35d11e
P6-09A branch: feature/prem3-p6-09a-governed-monte-carlo-simulation
P6-09A worktree: C:/Users/zroda/Desktop/prem3-p6-09a
P6-09A base HEAD: 30c2205bbb137ac1c27319e77973a8013d35d11e
P6_09A_FINAL_COMMITTED_HEAD: PENDING_COMMIT
```

Push: not done. `uv.lock` left untracked.

## Isolation

Implemented only in `prem3-p6-09a`. Did not edit `prem3`, `prem3-p6-09`, `prem3-p6-08`, P6-07, P6-03A, integration, IG, M5, frontend, or any P6-10 worktree.

## Evidence path

```text
Accepted ModelVersion + approved baseline + FutureScenarioAssumptions + P6-08 handoff refs
  → ScenarioDistributionSet + ScenarioCorrelationSpec + MonteCarloSimulationPolicy
  → SimulationRunSpec (as_of_time + input fingerprint)
  → SimulationRun READY
  → POST .../execute 202 → SimulationExecutionAdapter.dispatch(run_id)
  → engine (GOVERNED_PLANNING_ECONOMICS | ACCEPTED_POSTERIOR_EVALUATION)
  → SimulationDrawArtifact Parquet on GCS
  → PortfolioOutcomeDistribution (scalar summaries + artifact ref)
  → MonteCarloSimulationReceipt
  → SimulationEvidenceHandoff (P6-10 seam)
```

`PREM3_RISK_AWARE_FRONTIER` remains a deferred adapter stub. P6-09 CVaR stays in `risk/downside.py`.

## Spec §55 closeout

- Schema `p6-09a/v1`. Public roots: `ScenarioVariableDistribution`, `ScenarioDistributionSet`, `ScenarioCorrelationSpec`, `MonteCarloSimulationPolicy`, `SimulationRunSpec`, `SimulationRun`, `PortfolioOutcomeDistribution`, `MonteCarloSimulationReceipt`, `SimulationEvidenceHandoff`. `SimulationDrawArtifact` is amount-bearing and is not a public planning root.
- IDs: `osds_`, `osvar_`, `oscor_`, `osimpol_`, `ospec_`, `osim_`, `odist_`, `osimr_`, `ohand_`, `odraw_`.
- Families: EMPIRICAL, NORMAL, LOGNORMAL, TRIANGULAR, BETA, DISCRETE, FIXED. Same seed → same draws.
- Correlation: INDEPENDENT / EMPIRICAL / USER_APPROVED; MODEL_DERIVED fail-closed without artifact. Iman–Conover via Cholesky (ADR-P6-088). No silent matrix repair.
- Policy limits: min draws 64, max draws 10_000, max candidates 50, max variables 32, max cells 50_000.
- Outcome V1: `GOVERNED_PLANNING_ECONOMICS` (shares × sampled governed variables × pinned baseline KPI). `ACCEPTED_POSTERIOR_EVALUATION` requires an accepted posterior artifact or `POSTERIOR_SIMULATION_SOURCE_UNAVAILABLE`.
- Candidates require existing feasibility receipt / fingerprint (`SIMULATION_CANDIDATE_INVALID`).
- Role C exposure may be a scenario variable; never a hard LINE_MIN/MAX constraint.
- Firestore: IDs/refs/fingerprints/statuses/draw counts/seed/engine version. Draws on GCS Parquet.
- HTTP `/v1/projects/{project_id}/investment-portfolio/simulations` (+ hidden workspace alias), `Feature.PORTFOLIO_VIEW`, `private, no-store`.
- Production `create_app` wires `UnavailableSimulationExecutionAdapter`. No fabricated Cloud Run proof.

## War-room §59 A–L

| | Item | Result |
|---|---|---|
| A | Launch gate | Re-verified P6-09 `30c2205bbb137ac1c27319e77973a8013d35d11e`; only `?? uv.lock`; ancestor of `59d1df2`. Worktree created from that SHA. |
| B | Isolation | P6-09 / P6-08 / M3 `prem3` untouched. No P6-10 / UME / Advisor / frontend. |
| C | Optimizer authority | Native Meridian only. Simulation does not allocate. Adapter stub still raises for `PREM3_RISK_AWARE_FRONTIER`. |
| D | Distribution governance | No silent distributions. Missing authority → `SCENARIO_DISTRIBUTION_NOT_GOVERNED`. Domain reject or recorded truncate. |
| E | Correlation + RNG | Fail-closed matrices. Iman–Conover documented. Parent seed + spawned batch seeds. |
| F | Outcome authority | Recorded evaluator versions only. Missing posterior ≠ zero uncertainty. |
| G | Artifacts + CVaR reuse | Parquet draws on object store. P6-09 CVaR / P(improvement) reused. Insufficient tail draws fail closed. |
| H | Job boundary | FastAPI dispatches. Local adapter not installed in `create_app`. `LIVE_SIMULATION_JOB_PROOF_PENDING` if live job missing. |
| I | P6-09 bridge | `p6_09_bridge.py` maps artifacts to existing `evaluate()` tuples. Frontier files unchanged. Absent simulation still `POSTERIOR_RISK_UNAVAILABLE`. |
| J | P6-10 handoff | `SimulationEvidenceHandoff` refs + `as_of_time` only. No P6-10 imports. |
| K | Privacy | Metadata-only Firestore. HTTP `private, no-store`. Client cannot submit draws/outcomes/quantiles/fingerprints. |
| L | Proof | Focused P6-09A tests + combined regression + schema/OpenAPI `--check` + Ruff on owned paths. |

## HTTP

Under `/v1/projects/{project_id}/investment-portfolio/simulations`:

- `POST/GET .../scenario-distribution-sets`
- `POST/GET .../correlation-specs`
- `POST/GET .../policies`
- `POST/GET .../run-specs`
- `POST/GET .../runs`
- `POST .../runs/{id}/execute` (202)
- `GET .../runs/{id}/receipt`
- `GET .../runs/{id}/outcome-distributions`
- `GET .../runs/{id}/evidence-handoff`

## OpenAPI / schema

LF-normalized SHA-256 of the working tree (`--check` green; export run with `PYTHONPATH` on this worktree):

| Artifact | SHA-256 |
|---|---|
| `contracts/openapi.yaml` | `d3953c8a0b42344606389e09807d7f80643b1055bfa1266a9a9b74667c6286c0` |
| `contracts/schema/planning.schema.json` | `56ffe0d9643c88c0d879148d1946faafdcb26da9968090d9e93df91d930e41de` |
| `contracts/schema/api.schema.json` | `8f7d98f9724edc42a9dd829728337023102e69a3e4038130ce8e5191b5329628` |
| `contracts/schema/manifest.json` | `5ea218b32e93e9f4694dd8e775d6cea0a3784cddf1d17061e4a411f3167a2b47` |

## Tests

- `tests/unit/investment_optimization/test_p6_09a_math.py`
- `tests/unit/investment_optimization/test_p6_09a_runtime.py`
- `tests/unit/investment_optimization/test_p6_09a_privacy.py`
- `tests/unit/investment_optimization/p6_09a_support.py`

**19 P6-09A tests.** Combined planning / optimization / DF / IG / channel-registry / project-architecture suite: **515 collected, exit 0** (3 skipped, remainder passed). P6-09, P6-08, and P6-07 tests remain green.

```text
PYTHONPATH=C:/Users/zroda/Desktop/prem3-p6-09a
python -m pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_channel_registry.py
python scripts/export_contracts.py --check
python scripts/export_openapi.py --check
```

Ruff green on P6-09A-owned paths. Pre-existing P6-07 privacy substring `12.50` can false-positive against ISO timestamps; one rerun passed and was not rewritten.

## Docs / ADRs

ADR-P6-086 … ADR-P6-094 in [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md).

## Blockers

Live Cloud Run simulation job proof is not a closeout gate (`LIVE_SIMULATION_JOB_PROOF_PENDING`). P6-10 MEL/UME/Advisor/frontend, custom allocator, generalized copula framework, and full historical backtesting are out of scope.
