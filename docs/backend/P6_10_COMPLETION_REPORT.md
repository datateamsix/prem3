# P6-10 completion report

Decision outcomes and MEL learning closure on the frozen P6-09 HEAD. P6-06 remains the only human-decision authority. Simulation distribution scoring stays an optional opaque ref. Native Meridian remains the only optimizer.

## Required lineage block

```text
P6-06 base: e1a9477b9ce57719d56f0d522d3cb85540823362
P6-07 final committed HEAD: be554242b8b64cc702545902949044b163db6030
P6-03A final committed HEAD: eced1acf144c0d469e2c3b316f5391398c879bd8
P6_POST07_ACTUALS_INTEGRATION_READY_HEAD: 591d9969f7459ba7757fe2ca29d70138c92d39b7
P6-08 final committed HEAD: 59d1df2ed40e6be95d526658a8a7fe68032a26d3
P6_09_FINAL_COMMITTED_HEAD: 30c2205bbb137ac1c27319e77973a8013d35d11e
P6-10 branch: feature/prem3-p6-10-decision-outcomes-mel-closure
P6-10 worktree: C:/Users/zroda/Desktop/prem3-p6-10
P6-10 base HEAD: 30c2205bbb137ac1c27319e77973a8013d35d11e
P6_10_FINAL_COMMITTED_HEAD: (recorded after commit)
```

Push: not done. `uv.lock` left untracked.

## Isolation

Implemented only in `prem3-p6-10`. Did not edit `prem3` (M3), `prem3-p6-09`, `prem3-p6-09a`, P6-08, P6-07, P6-03A, integration, IG, M5, frontend, or any convergence worktree. Did not import `app.investment_optimization.simulation` or P6-09A modules.

## Evidence path

```text
FrontierSelection MODEL_RECOMMENDED
  → existing P6-06 ProposalDecisionReceipt + PlanningDecisionRecord
  → InvestmentDecisionRecord (classifies ACCEPT / ACCEPT_WITH_MODIFICATIONS / REJECT / DEFER / WITHDRAW / EXPIRED)
  → optional DRAFT plan revision remains P6-06 create_plan_revision_from_proposal
  → RecommendationAdherence (L1 / max abs / add-remove)
  → ExecutionAdherence (P6-03A actuals; incomplete ≠ zero)
  → DecisionOutcomeObservation (governed source; supersession)
  → PredictionEvidenceSet (optional opaque simulation_evidence_handoff_ref)
  → PredictionErrorSummary (point error; distribution fields None without handoff)
  → RecommendationOutcomeReceipt CLOSED only with governed refs
  → DecisionOutcomeLearningReceipt LOCAL_ONLY (no policy/plan mutation)
```

## Spec §66 A–N

| | Item | Result |
|---|---|---|
| A | Launch gate | Re-verified P6-09 `30c2205bbb137ac1c27319e77973a8013d35d11e`; only `?? uv.lock`; ancestor of `59d1df2`. Worktree created from that SHA. |
| B | Isolation | P6-09 / P6-09A / M3 / P6-08 untouched. No P6-09A Python import. |
| C | Decision authority | P6-06 `ProposalDecision` unchanged. No second proposal-decision POST. Bind requires authenticated `decided_by_user_id`. |
| D | Classification | Matching shares → `ACCEPT`. Share/lineage delta → `ACCEPT_WITH_MODIFICATIONS` with both portfolio refs. `REJECT` / `DEFER` / `WITHDRAW` / `EXPIRED` never infer ACCEPT. |
| E | Recommendation adherence | L1, max abs line, add/remove. `%` refused when recommended share is 0. No opaque score. |
| F | Execution adherence | Missing/partial actuals → incomplete codes, never zero spend. P6-08 refs are limitations. |
| G | Outcome authority | Explicit semantic type, unit, window, source refs. Spend-only inference forbidden. v2 supersedes; v1 immutable. |
| H | Temporal fail-closed | Prediction after decision, outcome before window, latest-state / future-model substitution rejected. |
| I | Prediction error | Point signed/absolute/% (when valid). Distribution fields `None` + `SIMULATION_EVIDENCE_NOT_AVAILABLE` without opaque ref. |
| J | Closure receipt | `CLOSED` only with prediction + (observation or explicit `OUTCOME_NOT_OBSERVED`). Wall-clock does not close. |
| K | MEL LOCAL_ONLY | Learning receipts are structural metadata. Candidate types do not call optimizer, MEL promote, or plan revise. |
| L | Opaque P6-09A seam | `simulation_evidence_handoff_ref: str \| None` only. No `SimulationEvidenceHandoff` type. Convergence resolver deferred. |
| M | Privacy / storage / HTTP | Firestore metadata only. Amount artifacts off control plane. `/v1/projects/{project_id}/investment-portfolio/outcomes` + hidden workspace alias, `Feature.PORTFOLIO_VIEW`, `private, no-store`. |
| N | Proof + exclusions | Focused P6-10 tests + combined regression + schema/OpenAPI `--check` + Ruff on owned paths. No UME, Advisor, frontend, live Cloud Run, distribution scoring, or push. |

## HTTP

Under `/v1/projects/{project_id}/investment-portfolio/outcomes`:

- `POST/GET .../decisions`
- `POST/GET .../recommendation-adherence`
- `POST/GET .../execution-adherence`
- `POST/GET .../outcome-observations`
- `POST/GET .../prediction-evidence`
- `POST/GET .../prediction-errors`
- `POST/GET .../receipts`
- `POST/GET .../learning-receipts`

## OpenAPI / schema

LF-normalized SHA-256 of the working tree (`--check` green; export run with `PYTHONPATH` on this worktree):

| Artifact | SHA-256 |
|---|---|
| `contracts/openapi.yaml` | `c36aa1cad5f12bb1ec4b0ebf66b80ef9eb0ce2296122a2913fa2405db4f40540` |
| `contracts/schema/planning.schema.json` | `1a2363f1a43759e282ba1991bef6cec29e393d5dce86f5b2723b15cb4be2d7cf` |
| `contracts/schema/api.schema.json` | `8f7d98f9724edc42a9dd829728337023102e69a3e4038130ce8e5191b5329628` |
| `contracts/schema/manifest.json` | `1aa7d8bac4b635f274597ad57db9996d008f83cf43ad65f65d3d8461063002f4` |

Schema `p6-10/v1`. Public planning roots added: `InvestmentDecisionRecord`, `RecommendationAdherence`, `ExecutionAdherence`, `DecisionOutcomeObservation`, `PredictionEvidenceSet`, `PredictionErrorSummary`, `RecommendationOutcomeReceipt`, `DecisionOutcomeLearningReceipt`. `ExecutionAdherenceArtifact` stays off the public catalog.

## Tests

- `tests/unit/investment_planning/p6_10_support.py`
- `tests/unit/investment_planning/test_p6_10_decision_adherence.py`
- `tests/unit/investment_planning/test_p6_10_outcomes_prediction.py`
- `tests/unit/investment_planning/test_p6_10_receipts_mel.py`
- `tests/unit/investment_planning/test_p6_10_http_privacy.py`

**42 P6-10 tests.** Combined planning / optimization / DF / IG / channel-registry / project-architecture suite: **exit 0** (3 skipped, remainder passed). P6-05 fixed-budget and P6-06 proposal tests remain green.

```text
PYTHONPATH=C:/Users/zroda/Desktop/prem3-p6-10
python -m pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_channel_registry.py
python scripts/export_contracts.py --check
python scripts/export_openapi.py --check
```

Ruff green on P6-10-owned paths.

## Docs / ADRs

ADR-P6-095 … ADR-P6-103 in [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md).

## Blockers

Distribution-aware scoring, P6-09A engine import, generalized backtester, UME, Advisor, frontend, and live Cloud Run are out of scope.
