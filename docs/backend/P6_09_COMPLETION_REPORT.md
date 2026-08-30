# P6-09 completion report

Risk-aware Marketing Investment Frontier on the frozen P6-08 HEAD. Native Meridian remains the only optimizer. No universal risk score. No approved-plan mutation.

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
P6-09 base HEAD: 59d1df2ed40e6be95d526658a8a7fe68032a26d3
P6_09_FINAL_COMMITTED_HEAD: 68459ad561793d8e7becb021cf86a9818b151c3e
```

Push: not done. `uv.lock` left untracked.

## Isolation

Implemented only in `prem3-p6-09`. Did not edit `prem3`, `prem3-p6-08`, P6-07, P6-03A, integration, IG, M5, or frontend.

## Evidence path

```text
Native Meridian OptimizationRun (p6-05/v1 or p6-07/v1)
  → NATIVE_OPTIMUM_PLUS_FEASIBLE_NEIGHBORS
  → PortfolioRiskEvaluation (posterior fixture | POSTERIOR_RISK_UNAVAILABLE,
     discrete CVaR, HHI, L1, P6-08 ExposureRiskHandoff refs)
  → MarketingInvestmentFrontier (policy-fingerprinted Pareto)
  → FrontierSelection MODEL_RECOMMENDED
       EXPECTED_OUTCOME | BALANCED | CONSERVATIVE
  → optional ScenarioArtifact refs
  → existing P6-06 OptimizationProposal
  → authenticated human approval
  → DRAFT plan revision (P6-01 only may establish APPROVED_PLAN)
```

`PREM3_RISK_AWARE_FRONTIER` remains a deferred adapter stub. Risk-neutral `EXPECTED_OUTCOME` must match the native allocation fingerprint or fail `RISK_NEUTRAL_PARITY_FAILED`.

## Spec §40 closeout

- Schema `p6-09/v1`. Public roots: `RiskEvaluationPolicy`, `CandidatePortfolio`, `PortfolioRiskEvaluation`, `MarketingInvestmentFrontier`, `FrontierSelection`, `RiskNeutralParityReceipt`.
- IDs: `orpol_`, `ocand_`, `oreval_`, `ofrn_`, `osel_`, `opary_`, `ofeas_`.
- Discrete CVaR: worst-first VaR at `ceil(alpha * n) - 1`; `E[L | L >= VaR]`; `loss = baseline_outcome - candidate_outcome`.
- HHI and top-k by declared dimension. L1 / line movement vs pinned `RiskBaselineKind` (`ACTUAL_YTD` rejected as budget baseline).
- Role C exposure evidence is a limitation, never LINE_MIN/MAX or a hard constraint.
- Missing posterior / exposure is a typed code, not zero risk.
- Firestore: refs, fingerprints, statuses, non-amount scalars. Amounts and draw arrays stay off the control plane.
- HTTP `/v1/projects/{project_id}/investment-portfolio/risk-frontier` (+ hidden workspace alias), `Feature.PORTFOLIO_VIEW`, `private, no-store`.
- `create_scenario_from_frontier_selection` still requires the native `optimization_run_id`. No path from selection to `APPROVED_PLAN`.

## War-room §48 A–K

| | Item | Result |
|---|---|---|
| A | Launch gate | Re-verified `59d1df2ed40e6be95d526658a8a7fe68032a26d3`; only `?? uv.lock`; ancestor of `591d9969`. Worktree created from that SHA. |
| B | Isolation | P6-08 worktree untouched. M3 `prem3` untouched. No P6-10 / UME / Advisor / frontend. |
| C | Optimizer authority | Native Meridian only. Adapter stub still raises for `PREM3_RISK_AWARE_FRONTIER`. |
| D | Candidates + parity | Native optimum + deterministic neighbors. `RiskNeutralParityReceipt` fail-closed. |
| E | Evaluation math | CVaR / HHI / L1 / dominance unit-tested. Missing posterior ≠ zero. |
| F | P6-08 exposure | Handoff refs + Role C limitations. Role C is not a hard constraint. |
| G | Frontier + postures | Non-dominated set from fingerprinted `dominance_policy`. Three postures, `MODEL_RECOMMENDED` only. |
| H | P6-06 hook | Optional scenario refs. Existing proposal committee. No approved-plan mutation. |
| I | Privacy | Metadata-only Firestore. HTTP `private, no-store`. Client cannot submit CVaR/HHI/dominance/membership/outcomes. |
| J | Proof | Focused P6-09 tests + combined regression + schema/OpenAPI `--check` + Ruff on owned paths. |
| K | Exclusions | No custom allocator, no universal score, no live customer-cloud posterior optimize, no push. |

## HTTP

Under `/v1/projects/{project_id}/investment-portfolio/risk-frontier`:

- `POST/GET .../risk-evaluation-policies`
- `POST/GET .../candidates`
- `POST/GET .../evaluations`
- `POST/GET .../frontiers`
- `POST .../frontiers/{frontier_id}/select`
- `GET .../frontiers/{frontier_id}/selections/{selection_id}`
- `GET .../parity-receipts/{parity_id}`

## OpenAPI / schema

LF-normalized SHA-256 of the working tree (`--check` green; export run with `PYTHONPATH` on this worktree):

| Artifact | SHA-256 |
|---|---|
| `contracts/openapi.yaml` | `ce7a2a7bbf4b12d290ae4fdf4196fc13359cf2fb9e8af210b2e45bb6e362a5da` |
| `contracts/schema/planning.schema.json` | `e709a40647de55fedd96a97efb7257956a8f3525c88a887a982aa649da2a15e2` |
| `contracts/schema/api.schema.json` | `8f7d98f9724edc42a9dd829728337023102e69a3e4038130ce8e5191b5329628` |
| `contracts/schema/manifest.json` | `8caf7a00d55790cda12c43dcefe952cc9fd40d64afe7739d6c3ad17952f1a71b` |

## Tests

- `tests/unit/investment_optimization/test_p6_09_math.py`
- `tests/unit/investment_optimization/test_p6_09_frontier.py`
- `tests/unit/investment_optimization/test_p6_09_privacy.py`
- `tests/unit/investment_optimization/p6_09_support.py`

**21 P6-09 tests.** Combined planning / optimization / DF / IG / channel-registry / project-architecture suite: **496 collected, exit 0** (3 skipped, remainder passed). P6-08 and P6-07 tests remain green.

```text
PYTHONPATH=C:/Users/zroda/Desktop/prem3-p6-09
python -m pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_channel_registry.py
python scripts/export_contracts.py --check
python scripts/export_openapi.py --check
```

Ruff green on P6-09-owned paths. Pre-existing P6-01 lint was not rewritten.

## Docs / ADRs

ADR-P6-078 … ADR-P6-085 in [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md).

## Blockers

Live customer-cloud posterior optimize is not a closeout gate. P6-10, UME, Advisor, and frontend are out of scope.
