# P6 final backend freeze report

P6-09A simulation and P6-10 outcomes are converged on `integration/prem3-p6-final`. The only new product seam is the `SimulationEvidenceHandoff` resolver. This is not P6-11. Native Meridian, P6-06 proposal authority, P6-03A actuals, and the P6-08/P6-09 frontier remain unchanged.

**`P6_BACKEND_FROZEN`:** yes

## Required SHA block

```text
REMOTE_MAIN_AT_CLOSEOUT_START: 26369a6b06d8082b92cc9630027a3a2feb584db6
LOCAL_MAIN_AT_CLOSEOUT_START: 0d72636c2b7298a29e212ac3b382a52e11933425
P6_09_FINAL_COMMITTED_HEAD (convergence base): 30c2205bbb137ac1c27319e77973a8013d35d11e
P6-09A feature authority (cherry-pick #1): 03671a396daa4ea1e475a7d10fd14376d97cf742
P6_10_FINAL_COMMITTED_HEAD (cherry-pick #2): 2ff6ecabf68fc2653602ab98c851c2dd6f75cb9c
P6-09A docs HEAD (not integrated): 10fd09307a24e986a5a07189b9ffba1f3fbe67ca
P6-10 docs HEAD (not integrated): 6f0e58dcb094e2243feaf584f3e1016c31669a92
P6_FINAL_INTEGRATION_READY_HEAD: 5e302b4410937f6e501c8ba3b2ce3919761687e8
P6-final branch: integration/prem3-p6-final
P6-final worktree: C:/Users/zroda/Desktop/prem3-p6-final-integration
```

Push of this freeze: not done in this report. `uv.lock` left untracked.

## Topology note

At Phase A fetch, `origin/main` had moved from PR #17 `0d72636` to merge `26369a6` (project-architecture checkpoint). That SHA is **not** an ancestor of P6-09 `30c2205`. Fast-forward of this freeze onto current `origin/main` is therefore impossible. Main consolidation must **merge** `integration/prem3-p6-final` into a consolidation branch based on `origin/main`. If that merge would change Meridian / P6-06 / P6-03A / P6-08 / P6-09 frontier / MISSING≠ZERO, stop `P6_FINAL_ARCHITECTURE_CONFLICT`.

## Convergence method

Isolated worktree from exact `30c2205`. Cherry-picked feat commits only (`03671a3`, then `2ff6eca`). Did not merge live P6-09A or P6-10 branches. Conflict authority: P6-09A owns simulation types/RNG/draws/handoff/ADR-086–094; P6-10 owns outcome types/temporal/MEL/ADR-095–103. Generated JSON/YAML were regenerated once after source merge.

Local cherry-pick commits on this branch: `5741d31` (09A feat), `3d1990b` (P6-10 feat), `5e302b4` (resolver + contracts).

## Resolver

`app/investment_planning/outcomes/simulation_handoff.py` is called only from `compute_prediction_error` / `OutcomeService.create_prediction_error`.

- Missing `simulation_evidence_handoff_ref` → existing `SIMULATION_EVIDENCE_NOT_AVAILABLE`; `realized_percentile` / `inside_expected_interval` stay `None`; not zero uncertainty.
- Present ref → `store.get_simulation_evidence_handoff`. Loads `SimulationRun`, `MonteCarloSimulationReceipt`, `SimulationRunSpec`, and the selected candidate’s `PortfolioOutcomeDistribution`.
- Fail `SIMULATION_EVIDENCE_INVALID_FOR_PREDICTION` unless: same `project_id`; run `COMPLETE`; `as_of_time` not after decision/prediction evidence time; candidate ∈ handoff and spec `candidate_set_ref`; compatible `model_version_ref`; matching `outcome_unit`; observation window valid via `assert_temporal_order`.
- Valid handoff fills the two interval fields from metadata `quantiles` / `median` only. No engine, RNG, correlation, or `SimulationDrawArtifact` in outcomes math or Firestore metadata.

## Proof

| Check | Result |
|---|---|
| `export_contracts.py` + `--check` | green |
| `export_openapi.py` + `--check` | green |
| P6 regression (`investment_optimization`, `investment_planning`, `test_project_architecture`, `data_foundation`, `identity_graph`, `test_channel_registry`) | green (3 skipped) |
| Ruff on convergence-owned paths | green |
| New handoff tests | no-ref limitation; valid percentile; invalid project/candidate/unit/future `as_of_time`/non-COMPLETE; draw artifact rejected by persistence barrier |

## OpenAPI / schema (working-tree `--check`)

| Artifact | SHA-256 |
|---|---|
| `contracts/openapi.yaml` | `4af258167b92d0042acb2d7919ad2e80c0a9fed6e670528f3d4acb09b1e669cd` |
| `contracts/schema/planning.schema.json` | `0e9297232b37f65827beb64b1b224027a5292a247c5e57c39dfe515f8d9df0a4` |
| `contracts/schema/manifest.json` | `3377358e1ca24c6eb0eb4b0960d52c67e91272181e64c5b8879bf4fcc3c0e110` |

## ADRs

`docs/backend/P6_00_ARCHITECTURE_DECISIONS.md` preserves ADR-P6-086–094 then ADR-P6-095–103. No renumber.

## Exclusions

M3 / IG / M5 / frontend were not merged. No force push. No history rewrite. No second proposal-decision POST. No UME, Advisor, live Cloud Run, or P6-11.
