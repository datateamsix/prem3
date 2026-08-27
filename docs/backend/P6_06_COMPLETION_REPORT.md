# P6-06 completion report

Scenario artifacts, committee proposal governance, and Investment Plan revision drafts on the isolated P6-06 worktree. Optimizer execution is unchanged. Production BigQuery actuals remain fail-closed.

## A. Git isolation

| Item | Value |
|---|---|
| Worktree | `C:/Users/zroda/Desktop/prem3-p6-06` |
| Branch | `feature/prem3-p6-06-scenario-proposal-governance` |
| P6-05 base SHA | `411254c5ec458cc60a848866aeb2cf817b2c941c` |
| Final committed HEAD | `411254c5ec458cc60a848866aeb2cf817b2c941c` (P6-06 work is uncommitted until a checkpoint is requested) |
| Status | P6-06 sources/docs/contracts uncommitted; `uv.lock` left untracked |

Did not start from this Cursor M3 checkout, dirty P6-05, P6-04, P6-03A, IG, or M5. No push. P6-04 remains closed.

## B. Scenario artifact

`ScenarioArtifact` (`oscn_`) is Firestore metadata: type `OPTIMIZER_RECOMMENDATION`, run/result/plan pins + fingerprints, GCS object refs, and the `MODEL_RECOMMENDED` evidence label as a string. Amounts live only in immutable GCS `scenario_{scenario_id}` copied from the P6-05 result. Create requires a `COMPLETE` run with successful read-back. Existing `scenario_id` cannot be overwritten. See [OPTIMIZATION_SCENARIO_ARTIFACT.md](OPTIMIZATION_SCENARIO_ARTIFACT.md).

## C. Proposal contract

Committee `OptimizationProposal` (`oprop_`) is distinct from `OptimizationRun` and from unused P6-00 `OptimizationProposalRef`. States: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `REVISION_REQUESTED`, `WITHDRAWN`, `STALE`. Create pins exact `scenario_id`, source plan/revision/fingerprint, run, readiness, and model. After submit, those pins are immutable. See [OPTIMIZATION_PROPOSAL_GOVERNANCE.md](OPTIMIZATION_PROPOSAL_GOVERNANCE.md).

## D. Proposal readiness

`ProposalReadinessReceipt` (`opready_`) is separate from P6-04 `OptimizationReadinessReceipt`. Source-plan, result, artifact, or model-acceptance mismatch → `STALE`. Model no longer accepted → `REVIEW_REQUIRED`. Failed checks → `NOT_READY`. `PROPOSAL_READY` is required to submit. Stale proposals cannot be approved.

## E. Human approval

Create/submit/review/decision require `Feature.BUDGET_OPTIMIZATION` and `require_human_approver`. Service accounts, workers, and the optimizer cannot approve. Entitlement is not approval.

## F. Decision receipt

Each decision writes an immutable `ProposalDecisionReceipt` (`odrc_`: `APPROVE|REJECT|REQUEST_REVISION|WITHDRAW`, `decided_by_user_id`, fingerprints, optional comment/reason) plus a thin `PlanningDecisionRecord` (`odec_`). Receipts cannot be overwritten. See [PROPOSAL_DECISION_RECEIPT.md](PROPOSAL_DECISION_RECEIPT.md).

## G. Scenario comparison

`GET .../scenarios/{scenario_id}/comparison` is transient `CUSTOMER_AMOUNT_TRANSIENT`: baseline vs recommended, absolute/percent change, material flags. Zero is distinct from missing. Percent is unavailable when baseline is 0. `Cache-Control: private, no-store`.

## H. Financial privacy

`assert_optimization_metadata_only` rejects allocation arrays on scenario, proposal, decision, and readiness metadata. FakeFirestore dumps contain no budget arrays. Amount-bearing comparison is private/no-store. Client bodies cannot supply `tenant_id`, GCS/BQ/Drive/model paths, budget arrays, fingerprints, or scenario artifact paths.

## I. Plan revision

After proposal `APPROVED`, `create-plan-revision` re-checks fingerprints, calls `revise_plan` (new `plan_id`, `revision+1`, `predecessor_plan_id`, source pins), compiles xlsx via `TEMPLATE_HEADERS` overlaying `MODEL_RECOMMENDED` amounts, and `ingest_bytes` into a **new** Drive file. Predecessor Drive bytes are not rewritten. `approve_plan` is not invoked. See [INVESTMENT_PLAN_REVISION_FROM_PROPOSAL.md](INVESTMENT_PLAN_REVISION_FROM_PROPOSAL.md) and [INVESTMENT_PLAN_GOVERNANCE.md](INVESTMENT_PLAN_GOVERNANCE.md).

## J. Double-approval semantics

Proposal `APPROVED` authorizes draft creation only. New `APPROVED_PLAN` still requires existing P6-01 validate → save-version → `POST .../investment-plans/{plan_id}/approve`. The two acts are not collapsed.

## K. Staleness / rebase

Source-plan version/fingerprint change, result/artifact change, or model-acceptance change marks the proposal `STALE` (or `REVIEW_REQUIRED`). Apply against a newer parent fails `PROPOSAL_SOURCE_PLAN_STALE`. V1 has no automatic rebase.

## L. APIs

```text
POST/GET /v1/projects/{project_id}/investment-portfolio/scenarios
GET      /v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}
GET      /v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}/comparison
POST/GET /v1/projects/{project_id}/investment-portfolio/proposals
GET      /v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}
POST     .../proposals/{proposal_id}/submit|review|decision
POST     .../proposals/{proposal_id}/create-plan-revision
```

Unused P6-00 `/investment-optimizations` stays unregistered.

- `contracts/openapi.yaml` sha256 `67eb3380484160207e51a96426993646677d07686dbc8c2b7671e14647775c52`
- `contracts/schema/planning.schema.json` sha256 `2dc39c9e438e889d484d6c2ad2cdc0c60e660fac077c9a620683b0ee610fc464`

## M. Audit lineage

Approved plan → `OptimizationRun` → `ScenarioArtifact` → `OptimizationProposal` → `ProposalDecisionReceipt` / `PlanningDecisionRecord` → successor draft `plan_id` with `predecessor_plan_id` + source pins. See [PLANNING_DECISION_LINEAGE.md](PLANNING_DECISION_LINEAGE.md).

## N. Tests

Required names §§65–73 in `test_p6_06_scenario.py`, `test_p6_06_proposal.py`, `test_p6_06_decision.py`, `test_p6_06_plan_revision.py`. API tests §74 in `test_p6_06_privacy_http.py`. P6-00/P6-04/P6-05 files kept.

P6-06 slice: 5 scenario + 9 proposal + 14 decision + 10 plan revision + 18 privacy/HTTP = 56.

## O. Regressions

`pytest tests/unit/investment_optimization tests/unit/investment_planning tests/unit/test_project_architecture.py` — 307 collected / 307 passed.

OpenAPI/schema export `--check` green. Ruff green on touched paths. Unrelated MTA / IG / P6-03A / vendored-skill SHA / MMM failures not repaired.

## P. P6-07 handoff

Scenario/proposal IDs, comparison rows, and material-change flags are the surfaces advanced min/max constraints should pin. Do not mutate COMPLETE runs or approved predecessor plans.

## Q. P6-10 handoff

Thin `PlanningDecisionRecord` (`DecisionRecordType.OPTIMIZATION_PROPOSAL`) stores refs and fingerprints only. MEL must not alter an active proposal, scenario, or plan.

## R. Blockers

None for this mission. Human approval is not fabricated. P6-03A production actuals stay `P6_03_PRODUCTION_ACTUALS_QUERY_PENDING` / fail-closed and do not block PLAN_ONLY governance.

## Explicit non-goals (held)

Automatic provider budget writes, campaign activation, flexible budget, P6-07 min/max, CVaR, frontier, outcome measurement, MEL closure, frontend, LLM narrative as authority, collapsing proposal+plan approval, mutating P6-05 optimizer execution, Identity Graph, MMM state machine, production BQ actuals.

## War room

TEAM 1

- P6-00  ✅ Architecture Freeze
- P6-01  ✅ Drive-native Investment Plan
- P6-02  ✅ Portfolio Snapshot
- P6-03  ✅ Actuals + Coverage + Observations
- P6-03A ⏳ fail-closed — `P6_03_PRODUCTION_ACTUALS_QUERY_PENDING`
- P6-04  ✅ Optimization Readiness + Portfolio-to-Model Mapping
- P6-05  ✅ Native Meridian Fixed-Budget Optimization (`411254c5ec458cc60a848866aeb2cf817b2c941c`)
- P6-06  ✅ Scenario Artifacts + Proposal Governance (implemented on this branch; not yet committed)
- P6-07  ⏭ Advanced Constraints

Include:

- Final committed HEAD: `411254c5ec458cc60a848866aeb2cf817b2c941c`
- Uncommitted: P6-06 domain/HTTP/tests/docs/OpenAPI; `uv.lock` untracked
- Scenario/proposal proof: `test_p6_06_scenario.py`, `test_p6_06_proposal.py`
- Human approval proof: `test_only_authorized_human_can_approve`, `test_service_account_cannot_approve`, `test_optimizer_cannot_approve`
- Plan revision proof: `test_approved_proposal_can_create_plan_revision`, `test_prior_approved_plan_not_mutated`, `test_plan_revision_requires_validation_and_approval`
- OpenAPI fingerprint: `67eb3380484160207e51a96426993646677d07686dbc8c2b7671e14647775c52`
- Test counts: 56 new P6-06; 307/307 on the required regression trio
- Next executable mission: P6-07 Advanced Constraints

The optimizer recommends. The human decides. The plan records the decision.
