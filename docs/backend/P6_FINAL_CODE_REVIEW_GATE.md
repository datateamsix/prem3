# P6 final code review gate

Correctness and tenant-isolation review of the P6-09A simulation runtime and P6-10 outcomes/MEL convergence delta already recorded frozen in `P6_FINAL_BACKEND_FREEZE_REPORT.md`. This is a review gate, not a new feature seam. No source was changed by this review.

**`P6_REVIEW_GATE_PASSED`:** no

6 blocking findings in 2 classes: cross-tenant isolation, and silently wrong governed output. 5 non-blocking correctness gaps, 3 hygiene. All 14 verified by direct source read at the SHAs below.

**Class A remediated** on `fix/p6-class-a-tenant-isolation` (`b1f8055`, `342a4d7`, `c5c8fe3`). A1–A4 are closed with tests; exit criteria 1–3 are met. Class B and the non-blocking items are open, so the gate itself does not yet pass. See "Class A remediation" below.

## Required SHA block

```text
REVIEWED_RANGE_BASE (= P6_09_FINAL_COMMITTED_HEAD): 30c2205bbb137ac1c27319e77973a8013d35d11e
P6-09A feature authority (cherry-pick #1): 5741d312bcc7c68abf2ae6fde44883fae520a240
P6-10 feature authority (cherry-pick #2): 3d1990bf63f6e7ca939ac694a31eff154eb04045
P6_FINAL_INTEGRATION_READY_HEAD (range tip): 5e302b4410937f6e501c8ba3b2ce3919761687e8
Consolidation merge: 4cafd7e0cc6bdb1a29c94e992814863693bb33e8
REVIEWED_AT_HEAD (= origin/main): 7fdbdd7a90603c2dc0cb4bb94b5774856576645e
Reviewed range: 30c2205..5e302b4 (55 files, 38 under app/)
```

Working tree clean at review time. `main` equal to `origin/main`; no pending diff existed, so the gate covers merged work.

## Relationship to the backend freeze

`P6_FINAL_BACKEND_FREEZE_REPORT.md` records `P6_BACKEND_FROZEN: yes` on a green proof matrix. That proof is **not** invalidated — those checks did pass and still pass. It is **incomplete**: the failing paths below carry no test, so contract export, OpenAPI check, ruff, and the P6 regression suite were all green over defective behaviour. Freeze status should be reopened, not reinterpreted.

## Blocking — class A: tenant isolation

| # | Finding | Site | Evidence |
|---|---|---|---|
| A1 | Cross-tenant read IDOR on 8 simulation and 5 outcomes GET handlers | `app/service/routers/simulation.py:137`, `app/service/routers/outcomes.py:145` | Handlers `del workspace` then fetch by raw client ID. `app/investment_optimization/firestore.py:174` `_load` resolves the ID through a root-level index and reads `tenant_id` / `workspace_id` **from the index document**, then loads from that workspace. Any known or guessed `osim_…` returns its owner's record |
| A2 | Receipt composition binds unowned records | `app/service/routers/outcomes.py:398`, `:353`, `:462` | Decision, prediction evidence, observation, both adherences, and prediction error are each fetched by client-supplied ID with no ownership check, then written into a receipt stamped `tenant_id=workspace.tenant_id` |
| A3 | Correlation fingerprint unscoped and constant | `app/investment_optimization/simulation/service.py:139`, `app/investment_optimization/store.py:332` | `validate_correlation_spec` returns immediately for `INDEPENDENT` (`simulation/correlation.py:18`), so `variable_ids=[]`, `matrix=[]` validates and the fingerprint over `{authority, variable_ids, matrix}` is a literal constant. `get_correlation_by_fingerprint` takes no tenant. Adjacent `get_distribution_set_by_fingerprint` (`store.py:326`) does take `tenant_id, project_id` |
| A4 | Prediction-evidence fingerprint unscoped | `app/investment_planning/outcomes/service.py:186` | `get_prediction_evidence_by_fingerprint(fingerprint=…)` carries no tenant. Narrower than A3: `pin_prediction_evidence` requires at least one pinned source ref and those refs enter the payload, so collision needs matching refs rather than being forced |

A1 and A2 compose. A1 discloses another tenant's identifiers; A2 admits them into a governed receipt under the caller's tenant.

## Blocking — class B: silently wrong governed output

| # | Finding | Site | Evidence |
|---|---|---|---|
| B1 | `directional_correct` compares the sign of the error to the sign of the prediction | `app/investment_planning/outcomes/prediction.py:129` | `predicted=100, realized=99` gives `signed=-1`; all three clauses are false; line 135 then overrides a correctly computed `WITHIN_EXPECTED_RANGE` with `DIRECTIONAL_MISS`. Every under-delivery on a positive prediction is a directional miss, and the class propagates into `DecisionOutcomeLearningReceipt.prediction_error_class`. Intended test is presumably `sign(predicted) == sign(realized)`. No test covers it |
| B2 | Execution adherence discards the variance it computes | `app/investment_planning/outcomes/execution_adherence.py:42` | `variance_percent(planned_value, actual_value)` is assigned to `_`. `adherence_class` is driven only by whether each planned line has some actual. Planned 100k executed at 400k yields `status=COMPLETE`, `adherence_class=MATCH`, empty `limitations`. Keys present in `actual` but absent from `planned` are never inspected. Only the INCOMPLETE branch is tested (`test_p6_10_decision_adherence.py:246`) |

Class B is more damaging than a fault: it emits confident wrong governance output into receipts that MEL then consumes.

## Non-blocking — correctness

| # | Finding | Site |
|---|---|---|
| M1 | `InvestmentDecisionKind.ACCEPT` unreachable over HTTP. `BindInvestmentDecisionRequest` has no `recommended_shares` / `decided_shares`, so `classify_decision` returns `ACCEPT_WITH_MODIFICATIONS` for every APPROVE, which then feeds `choose_learning_candidate` | `app/service/routers/outcomes.py:121` |
| M2 | `DEMAND_MULTIPLIER` is sampled, validated, paid for, then discarded whenever any channel-scoped variable exists; `demand` reaches the outcome only via the `not used_channel` fallback. The `CHANNEL_MULTIPLIER` branch is unreachable, subsumed by the preceding `elif` | `app/investment_optimization/simulation/outcomes.py:42` |
| M3 | Baseline `_share_map` and `evaluate_planning_economics` are recomputed inside the per-draw loop on invariant input, roughly doubling engine work for an identical result. At `SIMULATION_MAX_CELLS = 50_000` that is 50k redundant dict builds and 50k redundant evaluations. Hoist both out of both loops | `app/investment_optimization/simulation/engine.py:93` |
| M4 | Simulation worker entry point validates the payload and resolves `run_id`, then returns; it never loads the run or calls `run_engine`. With `UnavailableSimulationExecutionAdapter` wired at `app/service/app.py:371`, `POST /runs/{run_id}/execute` can only reach `FAILED`, and `execute_inline` is unreachable from any route. Resolve or record explicitly as staged | `app/tools/simulation_worker.py:24` |
| M5 | `_fail` annotated `-> None` rather than `NoReturn`. Runtime is correct since it always raises, but every post-`_fail` attribute access is a `union-attr` error under `strict = true` (`pyproject.toml:77`) — 20+ in this file. One-line fix | `app/investment_planning/outcomes/simulation_handoff.py:36` |

## Non-blocking — hygiene

| # | Finding | Site |
|---|---|---|
| L1 | Batching is reported but never performed. `batch_seed(...)` is called and discarded, and `sample_distribution_set` draws all `number_of_draws` from the parent generator. `MonteCarloSimulationReceipt.batch_count` and the recorded `SimulationBatchRef` seeds would not reproduce the draws actually taken | `app/investment_optimization/simulation/engine.py:167` |
| L2 | `LearningCandidateType.NO_ACTION` effectively unreachable: `absolute_error > 0.0` holds for float noise, so every closed receipt with a computed error becomes `MODEL_CALIBRATION_REVIEW`. Gate on `error_class` or a tolerance instead | `app/investment_planning/outcomes/learning.py:38` |
| L3 | `_reject_client_authority` is dead code. Every request model derives from `ApiModel` with `extra="forbid"` (`app/service/models.py:11`) and none declare the forbidden keys, so FastAPI rejects them first. Reads as an enforced control while enforcing nothing | `app/service/routers/simulation.py:72`, `app/service/routers/outcomes.py:84` |

## Exit criteria

| # | Criterion |
|---|---|
| 1 | Reads scoped to the caller's workspace. Prefer making `_load` tenant-scoped at the store over patching 13 handlers, so the `del workspace` pattern cannot be reintroduced one site at a time (A1) |
| 2 | Receipt, prediction-error, and learning-receipt composition verifies each fetched record's tenant before binding (A2) |
| 3 | Every `*_by_fingerprint` lookup takes `tenant_id, project_id`, matching `get_distribution_set_by_fingerprint`; correlation fingerprint includes tenant (A3, A4) |
| 4 | B1 and B2 fixed with tests on the currently failing paths. Both shipped because only the passing branch is covered |
| 5 | M4 resolved, or recorded explicitly as staged, since the execute path is non-functional end to end |
| 6 | Freeze re-run after the above. M5 alone fails `strict = true` mypy, so the type gate should be confirmed green before re-freezing |

## Class A remediation

Branch `fix/p6-class-a-tenant-isolation`, three commits, `main` unchanged.

| Finding | Status | Fix |
|---|---|---|
| A1 | closed | Every `SimulationService` and `OutcomeService` read takes the caller's `tenant_id` and `project_id`. A record owned by another workspace raises the same not-found error as an absent one, so the read path is not an existence oracle. Outcome distributions and the evidence handoff carry no workspace of their own and are scoped through their owning run. Both routers stopped discarding the authorized workspace |
| A2 | closed | The receipt, prediction-error and learning-receipt composition paths resolve every component under the caller's scope. Making scope a required keyword promoted the remaining unscoped sites to type errors, which surfaced two more the review had not listed: `create_run` and `create_run_spec` in the simulation router composed a policy, distribution set, correlation spec and candidate set from client-supplied ids with no ownership check |
| A3 | closed | The workspace is part of the correlation fingerprint payload, and `get_correlation_by_fingerprint` is scoped in the protocol and both store implementations |
| A4 | closed | Same treatment for prediction evidence, scoped by project since the record carries no tenant. The investment-decision and outcome-receipt payloads, which previously derived identity only from component fingerprints, now carry the workspace explicitly rather than inheriting it transitively |

Exit criteria 1, 2 and 3 are met. Criteria 4, 5 and 6 remain open.

### Verified

`tests/unit/investment_optimization/test_p6_final_tenant_isolation.py` and `tests/unit/investment_planning/test_p6_final_tenant_isolation.py`, 24 tests, refusal and owning-workspace allow case for every reader plus collision and same-workspace idempotency for both fingerprints. Each was watched failing for the right reason before the fix: A1 as `DID NOT RAISE`, A3 and A4 as the second workspace receiving the first workspace's record id.

P6 regression subset green. `export_contracts.py --check` and `export_openapi.py --check` green, so the published contracts and HTTP surface are unchanged. `mypy` on the changed files reports only two pre-existing `no-any-return` errors in the router service accessors. The wider unit suite has 13 failures and one collection error, all of them present identically on `main` at `7fdbdd7` and all outside the P6 regression scope: 10 in `test_extended_eda.py`, 2 in `test_mmm_modeling.py`, 1 in `test_requirements_alignment.py`, and a missing `app.modeling.mta.parameter_explanations` module. This branch introduces no new failure.

### Residual

`FrontierSelection` carries neither `tenant_id` nor `project_id`, so `bind_decision_from_ids` cannot scope a selection directly. That path is not exploitable today because `bind_investment_decision` already rejects a P6-06 receipt from another workspace, and a regression test now pins that behaviour. Closing it properly needs a workspace field on the model, which is P6-08/P6-09 frontier territory and out of this gate's scope.

Ten further `*_by_fingerprint` lookups on the P6-09A/P6-10 surface still take no workspace argument. Their payloads now include the workspace, so cross-workspace collision is prevented at the fingerprint, but the lookups themselves remain unscoped and should be brought in line with `get_distribution_set_by_fingerprint`. The frontier and evaluation lookups were deliberately left untouched under the freeze.

## Method and exclusions

Reviewed `app/` source in the range; tests and generated contracts read only as evidence. Every finding above was confirmed by reading the cited source, including the sites first surfaced by automated review. No fix, refactor, or test was written. No branch, tag, or freeze record was modified. Frontend, M3, IG, M5, Meridian, P6-06, P6-03A, and the P6-08/P6-09 frontier were out of scope and unread.
