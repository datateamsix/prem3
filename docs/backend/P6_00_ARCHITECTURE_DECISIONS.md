# P6-00 architecture decisions

Product sources are unchanged. See [P6_SOURCE_AUTHORITY.md](P6_SOURCE_AUTHORITY.md).

## ADR-P6-001 — Optional Project-scoped Investment Plan

Investment Plan is optional and owned by the Project. It is not a Dataset, Evaluation, MMM run, or Measurement Cycle. Absence does not block measurement.

## ADR-P6-002 — Business IQ owns portfolio semantics

Markets, channels, KPI meaning, economics, lifecycle, and business context come from a pinned Business Profile snapshot. Planning does not invent those semantics.

## ADR-P6-003 — Drive owns human-governed amounts

Customer Drive is the system of record for budget workbook bytes and allocation values. PreM3 GCS must not store budget artifacts.

## ADR-P6-004 — Firestore is metadata only

Control-plane documents store references, fingerprints, states, approvals, and receipts. The metadata store type-rejects amount-bearing models.

## ADR-P6-005 — Transient private PortfolioView

`PortfolioView` and optimization payloads are `CUSTOMER_AMOUNT_TRANSIENT`, Decimal, private/no-store, and excluded from logs.

## ADR-P6-006 — Actual spend is not approved budget

`ACTUAL_YTD` and `GOVERNED_ACTUALS` are observed-spend baselines. They are never labeled `APPROVED_PLAN`.

## ADR-P6-007 — One canonical portfolio grain

Planning, actuals, measurement evidence, and optimization share `fiscal year × quarter × market_id × channel_id`.

## ADR-P6-008 — Canonical IDs, no Planning registries

Reuse Channel Registry `channel_id`. `market_id` is required and is never derived from display names, fuzzy labels, or ISO 3166 codes. No `planning_channel_id`. No P6 market registry. Durable market identity is owned by the Marketing Identity Graph. IG-01 supplied `CanonicalMarket` and `BusinessMarketBinding` at `53b606a3b3bc529254816b8376d57c181b44a7ec`; P6 consumes those contracts via path-checkout and still fail-closes unresolved `market_id`. This freeze is not reopened. `campaign_id` is not a portfolio join key.

## ADR-P6-009 — Accepted MMM is the causal return engine

Optimization readiness for causal allocation requires accepted MMM evidence. MTA is supporting attribution/tactical evidence and must not replace MMM response curves.

## ADR-P6-010 — Immutable proposals; approval creates a new plan version

Optimization does not mutate the active Investment Plan. Human approval of `RECOMMENDED` authorizes a new Drive plan version.

## ADR-P6-011 — Meridian native optimizer first

Prove Meridian `BudgetOptimizer` (fixed budget) before any PreM3 risk-aware / CVaR solver. CVaR is a later labeled extension.

## ADR-P6-012 — Exposure integrity is separately governed

Reach/frequency/exposure-integrity may be inputs, constraints, or approval guardrails only when methodologically supported. Not a universal score. Not decoration.

## ADR-P6-013 — Actual spend is governed evidence, never approved-plan authority

`ActualSpendSourceRef` and `ActualSpendAllocation` record observed deployment. They are never labeled `APPROVED_PLAN`. `TEST_ONLY` synthetic adapters cannot be labeled customer-governed.

## ADR-P6-014 — Actuals join only on canonical market_id × channel_id × period

Display names, ISO codes, and fuzzy labels fail closed. Period is fingerprinted `fiscal_year × quarter`.

## ADR-P6-015 — MISSING is distinct from ZERO

No actual row is missing. An explicit `0` is zero. Source outage is unavailable, not zero-filled.

## ADR-P6-016 — Actual-spend rows remain analytical/transient; Firestore stores metadata only

`assert_metadata_only` rejects `ActualSpendAllocation` and `PortfolioView`. Firestore may store `ActualSpendSourceRef`, snapshot refs, coverage metadata, and observation metadata.

## ADR-P6-017 — PLAN_AND_ACTUALS and ACTUALS_ONLY are server-owned portfolio states

The assembler owns `PortfolioCoverageState`. Clients do not infer state. `ACTUALS_ONLY` uses baseline `ACTUAL_YTD`.

## ADR-P6-018 — Portfolio comparison uses Decimal

Plan/actual remaining and variance are `Decimal` with `ROUND_HALF_EVEN` to two places. Binary float is not amount authority.

## ADR-P6-019 — Period/fiscal mapping is explicit and fingerprinted

Aggregation rule `fiscal_year_x_quarter/v1` uses `InvestmentPlan.fiscal_start_month` and the source timezone. Unknown mapping is `PERIOD_MAPPING_REQUIRED`.

## ADR-P6-020 — Currencies are never silently mixed

Plan currency must match actuals currency. Mixed currencies without governed FX are `CURRENCY_REVIEW_REQUIRED`. P6-03 does not invent FX.

## ADR-P6-021 — PortfolioEvidenceCoverage describes evidence scope, not causal certainty

Coverage items carry explicit scope and status. Coverage is not a universal score and is not `OPTIMIZATION_READY`.

## ADR-P6-022 — MTA coverage remains tactical attribution evidence, not causal optimization authority

Accepted MMM coverage is distinct and may be labeled causal. MTA coverage is not.

## ADR-P6-023 — PortfolioObservation is a deterministic finding, not a recommendation

Observations do not create `RECOMMENDED` amounts or optimizer output.

## ADR-P6-024 — Actual observations never mutate the approved Investment Plan

Plan vs actual comparison is composed transiently. Drive plan bytes and plan status are unchanged.

## ADR-P6-025 — Optimization requires an explicitly accepted MMM ModelVersion

Eligible models have `accepted is True` and `state is MODEL_ACCEPTED`. `MODEL_READY`, `ITERATION_REQUIRED`, `FAILED`, `FAILED_PRE_FIT`, and review-pending states are ineligible. Acceptance is never inferred. Selection: 0 accepted → `NO_ACCEPTED_MODEL`; 1 accepted → that `model_version_id`; 2+ without an explicit Project-scoped `model_version_id` → `MULTIPLE_ACCEPTED_MODELS`. There is no `CURRENT_ACCEPTED_MODEL_POINTER`.

## ADR-P6-026 — Model Consumption Contract is the Planning↔MMM integration boundary

Planning may compile or cache a Planning-facing `ModelConsumptionContract` projection from accepted `MMMModelVersion` plus ModelPlan / acceptance / artifact refs. MMM/modeling remains the source of truth for accepted-model semantics. A cached projection that diverges from the accepted version’s identity, plan fingerprint, window, or runtime is `MODEL_CONSUMPTION_PROJECTION_STALE` and cannot become `OPTIMIZATION_READY`. Missing required fields are `MODEL_CONSUMPTION_CONTRACT_INCOMPLETE`. `app/tools/model_consumption.py` remains the MODEL_READY BigQuery view registry and is not this contract.

## ADR-P6-027 — Portfolio-to-model mapping uses canonical market_id/channel_id, never fuzzy labels

Mapping authority is only `MODEL_CONTRACT_EXACT`, `CANONICAL_CHANNEL_BINDING`, `CANONICAL_MARKET_BINDING`, `USER_CONFIRMED`, or `APPROVED_CUSTOM_MAPPING`. `FUZZY_NAME`, string similarity, and LLM inference cannot become authority. Display labels are not identity. Canonical channel IDs are never inferred from Meridian `media_channels` strings.

## ADR-P6-028 — MTA cannot substitute for accepted causal MMM evidence

`OptimizationEvidenceCoverage` may record MTA as tactical context. MTA cannot satisfy `MODEL_ACCEPTED` or response-artifact readiness checks.

## ADR-P6-029 — Actuals do not replace APPROVED_PLAN as the V1 fixed-budget baseline

V1 baseline is `APPROVED_PLAN` only. `PLAN_ONLY` and `PLAN_AND_ACTUALS` may become `OPTIMIZATION_READY`. `ACTUALS_ONLY` is `APPROVED_PLAN_REQUIRED`. `NEITHER` is `NOT_CONFIGURED`. `ACTUAL_YTD` never replaces the approved baseline.

## ADR-P6-030 — National models do not imply market-level causal precision

Market compatibility is `DIRECTLY_MODELED` / `AGGREGATED_IN_MODEL` / `NOT_MODELED` / `REVIEW_REQUIRED`. National + multiple portfolio markets is `AGGREGATED_IN_MODEL` with a scope limitation, or `REVIEW_REQUIRED` when market-level optimization is requested. No false geo precision.

## ADR-P6-031 — Model variable existence does not imply optimization eligibility

Control, organic, context, and outcome variables are never auto-optimizable. Eligibility is explicit on the consumption contract and confirmed by `eligibility.py`.

## ADR-P6-032 — One-to-many portfolio/model mappings require an explicit governed split

One portfolio cell to many model variables requires `APPROVED_ALLOCATION_SPLIT` (weights sum 10000 bps). Otherwise `ONE_TO_MANY_MAPPING_REQUIRES_SPLIT` / `REVIEW_REQUIRED`. Many-to-one requires explicit `AGGREGATE_FOR_MODEL` and is a combined bucket only.

## ADR-P6-033 — Many-to-many mapping is unsupported V1

Many-to-many is `MANY_TO_MANY_MAPPING_UNSUPPORTED` / `NOT_SUPPORTED_V1` and cannot become `OPTIMIZATION_READY`.

## ADR-P6-034 — Readiness pins plan/model/mapping/policy fingerprints

`OptimizationReadinessReceipt` is immutable. A new evaluation is required if portfolio, model, mapping, or `policy_version` fingerprints change. Stale receipts cannot remain `OPTIMIZATION_READY`.

## ADR-P6-035 — OPTIMIZATION_READY is readiness, not optimizer execution or proposal approval

P6-04 does not invoke Meridian `BudgetOptimizer`, does not create recommended allocations, and does not register an optimizer execution route. Project Home feeds generated status into existing `BUDGET_OPTIMIZATION`. No accepted model still surfaces `REQUIRES_ACCEPTED_MMM_MODEL`.

## ADR-P6-036 — Amount-bearing optimizer input is resolved transiently from approved authority

`OptimizationInputContract` stores metadata and the resolution path `APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`. P6-05 re-resolves total budget from Drive plan → transient `PortfolioView` → selected fiscal period. Firestore stores no budget arrays, Decimal amounts, or recommended allocations.

## ADR-P6-037 — OptimizationRun is not a P6-00 execution plan

P6-05 introduces `OptimizationRun` (`orun_`) bound to a non-stale `OptimizationReadinessReceipt` before any proposal exists. `OptimizationExecutionPlan.proposal_id` is not the run record.

## ADR-P6-038 — Native Meridian BudgetOptimizer is the only V1 solver

Fixed-budget execution calls `BudgetOptimizer.optimize(use_posterior=True, fixed_budget=True, budget=<approved-plan float>)`. Flexible budget and CVaR stay unimplemented. No custom PreM3 solver is the primary path.

## ADR-P6-039 — Native defaults are pinned and fingerprinted

P6-05 pins `spend_constraint_lower=0.3`, `spend_constraint_upper=0.3`, `gtol=0.0001`. These are not P6-07 Planning min/max objects. Historical-spend default `budget` is never used.

## ADR-P6-040 — Dispatch revalidation is mandatory

Fingerprints for portfolio, mapping, input contract, and model consumption are re-checked at dispatch. Mismatch is `OPTIMIZATION_READINESS_STALE`. Planning rebinds the consumption projection with `bind_projection_to_accepted_model`. MMM artifacts are not mutated.

## ADR-P6-041 — Approved Drive plan is the only fixed-budget authority

Budget is re-resolved via `APPROVED_DRIVE_PLAN_TRANSIENT_VIEW`. Actuals, MTA, Firestore, and client arrays cannot supply the fixed budget. Unapproved plans fail closed.

## ADR-P6-042 — Decimal reconcile owns the budget invariant

Meridian floats are quantized with Planning `ROUND_HALF_EVEN` money quantum. Residual cents go to the largest recommended optimizable line. After reconcile `|sum(rec) - fixed| == 0`. Pre-round drift beyond `max(0.01, gtol * budget)` is `OPTIMIZER_BUDGET_INVARIANT_FAILED`.

## ADR-P6-043 — Results are MODEL_RECOMMENDED, never APPROVED_PLAN

Recommended amounts are labeled `MODEL_RECOMMENDED`. Optional outcome fields from `OptimizationResults` are `MODEL_ESTIMATE`. They are not an approved Investment Plan.

## ADR-P6-044 — Firestore stores run metadata only

`OptimizationRun` and `OptimizationResultRef` are control-plane metadata. Amount arrays live on an immutable GCS artifact `optimization_result_{run_id}` and on the private result HTTP payload.

## ADR-P6-045 — COMPLETE requires artifact read-back

A run is `COMPLETE` only after the GCS object exists, schema and fingerprint match, the key set matches mapped variables, and the Decimal total equals the fixed budget. Failed read-back never completes.

## ADR-P6-046 — Human POST is execution authorization, not proposal approval

Create requires `Feature.BUDGET_OPTIMIZATION` and `OPTIMIZATION_READY`. `require_human_approver` authorizes execution. That is not P6-06 proposal approval and does not write Drive.

## ADR-P6-047 — Optimizer worker is a sibling of the fit worker

`app/tools/meridian_optimizer_worker.py` reconstructs from `optimization_run_id` only. `execute_approved_fit` is unchanged. A second Cloud Run Job name is a `SHARED_MERIDIAN_WORKER_CHANGE_REQUEST`.

## ADR-P6-048 — HTTP lives under investment-portfolio

Create/list/get run and get result are registered under `/v1/projects/{project_id}/investment-portfolio/optimizations`. The unused P6-00 `/investment-optimizations` namespace stays unregistered. Result responses are `Cache-Control: private, no-store`.

## ADR-P6-049 — Optimizer output is proposal evidence, never an approved Investment Plan

`OptimizationRun` COMPLETE and `MODEL_RECOMMENDED` results are evidence. They never become `APPROVED_PLAN`.

## ADR-P6-050 — ScenarioArtifact is immutable and binds exact source plan + optimizer result

A scenario pins the source plan revision/fingerprint and the completed optimization result. Changing run, baseline, model, or period creates a new `scenario_id`. Historical bytes are not mutated.

## ADR-P6-051 — OptimizationProposal is separate from OptimizationRun

The P6-06 committee `OptimizationProposal` (`oprop_`) is not `OptimizationRun` and is not the unused P6-00 `OptimizationProposalRef`. A proposal references one scenario.

## ADR-P6-052 — Explicit authenticated human approval is required for proposal adoption

Only `require_human_approver` may `APPROVE`. Service accounts, workers, and the optimizer cannot fabricate the decision.

## ADR-P6-053 — Proposal decision is recorded in an immutable ProposalDecisionReceipt

Each decision writes `ProposalDecisionReceipt` plus a thin `PlanningDecisionRecord`. Receipts cannot be overwritten.

## ADR-P6-054 — Proposal approval does not mutate optimizer, result, or scenario evidence

Approval changes proposal governance state only.

## ADR-P6-055 — Approved proposal creates a new Investment Plan revision; prior versions remain immutable

`revise_plan` mints a new `plan_id` with `predecessor_plan_id`. Predecessor Drive bytes are not rewritten.

## ADR-P6-056 — Proposal approval and plan approval are separate governance acts

Proposal `APPROVED` authorizes `create-plan-revision` (draft). New `APPROVED_PLAN` still requires P6-01 validate / save-version / approve.

## ADR-P6-057 — Stale proposals cannot be approved or applied

Source-plan, result, or model-acceptance mismatch marks the proposal `STALE`. Stale proposals cannot be approved.

## ADR-P6-058 — Source-plan changes require new or rebased governance

An old proposal is never silently applied to a newer approved plan (`PROPOSAL_SOURCE_PLAN_STALE`).

## ADR-P6-059 — Amount-bearing proposal and scenario data stays out of Firestore and logs

Comparison and change-summary payloads are transient and `Cache-Control: private, no-store`.

## ADR-P6-060 — P6-06 creates decision lineage suitable for a future Decision Ledger

`PlanningDecisionRecord` stores decision type, owner, evidence refs, and fingerprints without amounts.

## ADR-P6-061 — Native Meridian is the only flexible-budget solver

P6-07 calls `google-meridian==1.8.0` `BudgetOptimizer.optimize(fixed_budget=False, target_roi|target_mroi, ...)`. There is no PreM3 custom flexible-budget or group-sum solver. Unencodable hard constraints fail with `FLEXIBLE_BUDGET_API_UNSUPPORTED`.

## ADR-P6-062 — Future assumptions are pinned, fingerprinted, and GCS-private

`FutureScenarioAssumptions` amounts live on GCS. Firestore stores `ScenarioAssumptionSetRef` only. Changing the assumption fingerprint stales advanced readiness and the execution key.

## ADR-P6-063 — Hard constraints require explicit non-LLM authority

Every hard constraint carries source, `HUMAN_CONFIRMED` | `BUSINESS_IQ_GOVERNED` | `CONTRACTUAL` | `SYSTEM_DERIVED`, scope, period, reason, and fingerprint. LLM-proposed text is not authority.

## ADR-P6-064 — Feasibility is proven before native dispatch

`ConstraintValidationReceipt` plus interval feasibility run before `BudgetOptimizer.optimize`. Infeasible sets never dispatch. Native output is post-validated; violations are `RESULT_CONSTRAINT_VIOLATION`.

## ADR-P6-065 — Advanced readiness wraps P6-04 and does not rewrite it

`AdvancedOptimizationReadinessReceipt` (`oaready_`) wraps a non-stale `OPTIMIZATION_READY` receipt plus assumption, constraint, objective, and runtime fingerprints. P6-04 `evaluate_readiness` and the historical receipt shape stay frozen.

## ADR-P6-066 — B_min / B_max are PreM3 bounds, not native kwargs

Meridian 1.8.0 has no named `B_min` / `B_max`, and `_validate_budget` forbids the `budget` kwarg when `fixed_budget=False`. PreM3 compiles channel `spend_constraint_*` against the approved mix and hard-checks total bounds on the result. Otherwise it refuses.

## ADR-P6-067 — Financial value is never fabricated

Target ROI/mROI and contribution-value modes require governed `revenue_per_kpi` or margin. Missing unit value → `FINANCIAL_VALUE_ASSUMPTION_REQUIRED`. PreM3 reports cost per incremental KPI rather than inventing ROMI.

## ADR-P6-068 — Advanced amount payloads stay out of Firestore, logs, and public schema

Constraint/assumption arrays, budget vectors, and recommended rows are `CUSTOMER_AMOUNT_TRANSIENT`. Schema export publishes refs and readiness only. Amount HTTP is `private, no-store`. Worker request JSON cannot carry amount keys.

## ADR-P6-069 — Unsupported channels stay on the portfolio under an explicit policy

Missing evidence is not zero. Policies are `HOLD_BASELINE`, `RESERVE_EXPERIMENT_AMOUNT`, `EXCLUDE_FROM_OPTIMIZER_BUT_KEEP_PORTFOLIO`, and `APPROVED_PROXY_WITH_REVIEW`. Missing funnel weights are `FUNNEL_MAPPING_REQUIRED`.

## ADR-P6-070 — Exposure metrics remain definition-specific; no universal composite score

P6-08 interprets delivery/exposure as portfolio risk evidence. It does not emit `EXPOSURE_QUALITY_SCORE`, `delivery_confidence`, or any composite scalar. Named proxies (for example `human_viewable_in_target_impressions/v1`) are allowed only when components are comparable and the proxy is versioned and limitation-labeled.

## ADR-P6-071 — Exposure evidence has three governed optimization roles

Existing `ExposureGuardrailRole` values (`MODEL_INPUT`, `CONSTRAINT`, `SCENARIO_GUARDRAIL`, `APPROVAL_GUARDRAIL`) are retained. P6-08 maps them onto `ExposureOptimizationRole`: A `MODEL_INPUT`, B `CONSTRAINT_OR_FEASIBILITY`, C `SCENARIO_OR_REVIEW_GUARDRAIL` (scenario and approval both map to C). Qualification is a receipt. Roles are never silently promoted. P6-08 does not approve or reject proposals and does not mutate Meridian response curves.

## ADR-P6-072 — Hard exposure constraints require a defensible spend-to-quality relationship

Role B requires a policy-recorded spend→delivery relationship or bounded provider/capacity rule. P6-08 may then attach the qualified guardrail ID onto `OptimizationConstraintSet.exposure_guardrails`. It does not invent viewability/IVT `ConstraintFamily` values or compile observations into LINE_MIN/MAX or native `spend_constraint_*`. Client `POST` constraint-sets still fail: `pin_constraint_set` rejects caller-supplied IDs.

## ADR-P6-073 — Unsupported exposure constraints remain monitoring/scenario/review guardrails

If no spend-quality relationship exists, qualification assigns Role C with `SPEND_QUALITY_RELATIONSHIP_REQUIRED` / `EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED`. Role A requires an accepted MMM/optimizer consumption contract; otherwise `EXPOSURE_MODEL_INPUT_UNSUPPORTED`. Role A attaches qualification refs to `FutureScenarioAssumptions.source_refs`. Role C may attach `EXPOSURE_RISK_FLAGS_PRESENT` on the proposal change summary.

## ADR-P6-074 — Missing exposure evidence is not zero risk/zero quality

`PortfolioExposureCoverage` reports spend/channel/market/campaign-provider/freshness. Empty observations are `MISSING`, not a passing quality rate. Stale evidence is `REVIEW_REQUIRED`. Coverage uses existing `EvidenceCoverageLabel.EXPOSURE_INTEGRITY`. P6-03A actual spend joins as execution context only; amounts are never rewritten; `HIGH_SPEND_LOW_QUALITY` is descriptive.

## ADR-P6-075 — Provider metrics require explicit comparability

Each catalog metric pins numerator, denominator, population, unit, grain, and provider. `assert_comparable()` fails closed across classes (viewability ≠ in-target; average frequency ≠ over-frequency share). Same-named metrics across providers are not interchangeable without an explicit mapping.

## ADR-P6-076 — Campaign exposure context does not change canonical portfolio grain

Canonical grain remains fiscal year × quarter × `market_id` × `channel_id`. `campaign_id` and provider are optional context, not join keys. Campaign evidence may roll to channel/market only under explicit compatible aggregation rules.

## ADR-P6-077 — P6-08 measures risk evidence; P6-09 governs risk-aware selection

P6-08 returns `ExposureRiskHandoff` refs (evidence, qualified guardrails, scenarios, coverage, flags). It does not compute CVaR, a delivery-confidence scalar, or frontier selection. Production fetch is fail-closed without a governed Data Foundation exposure `SourceBinding` (`EXPOSURE_SOURCE_NOT_READY`). `TestOnlyExposureObservationAdapter` is unit-test only. Observations are `CUSTOMER_AMOUNT_TRANSIENT`; Firestore stores metadata only; HTTP is `private, no-store`; no person identity.

## ADR-P6-078 — Native Meridian remains the only optimizer; P6-09 evaluates neighbors

`PREM3_RISK_AWARE_FRONTIER` stays a deferred solver stub. P6-09 does not replace `BudgetOptimizer`. Candidate 0 is the native recommended allocation. Neighbors are deterministic feasible share reallocations. Risk-neutral `EXPECTED_OUTCOME` selection must match that native allocation fingerprint (`RiskNeutralParityReceipt`) or fail `RISK_NEUTRAL_PARITY_FAILED` with no authoritative selection. This is not “better than Meridian.”

## ADR-P6-079 — Candidate generation authority is the native run plus pinned policy

Every `CandidatePortfolio` records generation authority (`native_run:{optimization_run_id}`), the input fingerprint, allocation fingerprint, feasibility receipt, model/assumption/constraint refs, and the base approved-plan ref. V1 policy is only `NATIVE_OPTIMUM_PLUS_FEASIBLE_NEIGHBORS`. Random portfolios are forbidden. Failures are `CANDIDATE_GENERATION_FAILED`, `CANDIDATE_INFEASIBLE`, or `INSUFFICIENT_FRONTIER_CANDIDATES`.

## ADR-P6-080 — Risk taxonomy is explicit; there is no universal portfolio risk score

Named classes are `POSTERIOR`, `SCENARIO`, `EXPOSURE_DELIVERY`, `MODEL`, `DATA`, `CONCENTRATION`, `EXECUTION`, and `OPTIMIZATION`. Forbidden: `PORTFOLIO_RISK_SCORE`, `MARKETING_RISK_SCORE`, `DELIVERY_CONFIDENCE`, `INVESTMENT_CONFIDENCE_SCORE`. Missing evidence is a typed limitation or failure code, never a zero.

## ADR-P6-081 — Discrete CVaR is expected shortfall of baseline-minus-candidate loss

`loss = baseline_outcome - candidate_outcome`. VaR is the start of the upper tail at index `ceil(alpha * n) - 1` on losses sorted worst-first. CVaR is `E[L | L >= VaR_alpha(L)]`. The label CVaR is refused unless that definition is used. `PREM3_CVAR` is not a hidden composite score. Absent posterior draws → `POSTERIOR_RISK_UNAVAILABLE`.

## ADR-P6-082 — Dominance membership is policy-fingerprinted Pareto non-dominance

`dominance_policy` lists comparable dimensions and `MAXIMIZE` / `MINIMIZE` sense. A dominates B iff A is no worse on every declared dimension and strictly better on one. Candidate fingerprint is a deterministic tie-break for *ordering* only, not for membership. The frontier records all evaluated IDs, `dominated_by` lineage, and the policy fingerprint.

## ADR-P6-083 — Three postures select from the same frontier via declared policy fields

`EXPECTED_OUTCOME` maximizes expected outcome among non-dominated ready candidates. `CONSERVATIVE` minimizes downside-tail among non-dominated candidates at or above `conservative_expected_floor_ratio` of the best expected outcome. `BALANCED` applies the policy’s stored `balanced_keys`. Selection state is only `MODEL_RECOMMENDED`. Hidden weight vectors are forbidden.

## ADR-P6-084 — Risk artifacts persist as metadata; draws and amounts stay off Firestore

Schema `p6-09/v1`. Firestore stores IDs, refs, fingerprints, statuses, and scalar summaries that are not budget/revenue arrays (probabilities, HHI, L1, flags). Candidate allocation amounts and posterior draw tables are GCS / in-memory artifacts (`CUSTOMER_AMOUNT_TRANSIENT`). HTTP is `Cache-Control: private, no-store`. Clients cannot submit CVaR, HHI, dominance, frontier membership, or selected outcomes.

## ADR-P6-085 — Frontier selection enters P6-06 governance; it does not mint APPROVED_PLAN

Optional `ScenarioArtifact` refs (`risk_frontier_id`, `frontier_selection_id`, `parity_receipt_id`, `risk_evaluation_policy_id`) are metadata only. `create_scenario_from_frontier_selection` still requires the selected candidate’s native `optimization_run_id` and then the existing proposal path. Human approval remains `ScenarioArtifact` → `OptimizationProposal`. Proposal `APPROVED` is not `APPROVED_PLAN`. P6-09 does not rewrite Drive plan bytes. Role C exposure evidence stays a review limitation and is never compiled into LINE_MIN/MAX.

## ADR-P6-086 — Simulation evaluates candidates; it does not allocate

P6-09A is a fingerprinted Monte Carlo layer over already-feasible P6-09 candidates. Native Meridian remains the only optimizer. `PREM3_RISK_AWARE_FRONTIER` stays a deferred stub. Simulation never invents allocations, never mutates an approved plan, and never replaces `BudgetOptimizer`.

## ADR-P6-087 — Every scenario variable requires explicit distribution authority

A `ScenarioVariableDistribution` is governed only when family, parameters, `source_authority`, `source_refs`, and `approval_state` are pinned. Missing authority is `SCENARIO_DISTRIBUTION_NOT_GOVERNED`. There is no silent default, latest-state substitution, or invented empirical window. Domain bounds reject out-of-range draws unless the policy records truncation.

## ADR-P6-088 — Correlation is fail-closed; joint sampling is Iman–Conover

V1 authorities are `INDEPENDENT`, `EMPIRICAL_CORRELATION`, and `USER_APPROVED_CORRELATION`. `MODEL_DERIVED` fails closed unless a pinned artifact exists. Approved matrices must be square, symmetric, unit-diagonal, in `[-1, 1]`, and positive semidefinite. Invalid matrices are not repaired (`SCENARIO_CORRELATION_INVALID`). Joint sampling reorders independent marginals with Iman–Conover rank correlation via a Cholesky factor of the approved matrix. This is not a generalized copula framework.

## ADR-P6-089 — RNG is a parent seed plus spawned batch seeds

Sampling uses `numpy.random.Generator` / `PCG64` / `SeedSequence`. The parent seed is pinned on the policy. `batch_seed` is spawned from `(parent_seed, batch_index)` so batch schedule cannot change results. Same seed and inputs yield the same draws; FastAPI never owns the N-draw loop.

## ADR-P6-090 — HTTP dispatches; the engine runs in a job adapter

`POST .../runs/{id}/execute` is 202 and calls `SimulationExecutionAdapter.dispatch(simulation_run_id)` only. Production `create_app` wires `UnavailableSimulationExecutionAdapter`. `LocalSimulationExecutionAdapter` is test/explicit-local only. Missing live Cloud Run proof is `LIVE_SIMULATION_JOB_PROOF_PENDING`. Job JSON may carry the run id, never amount or authority keys.

## ADR-P6-091 — Draws and amounts stay on GCS; Firestore stores metadata

Schema `p6-09a/v1`. Firestore stores IDs, refs, fingerprints, statuses, draw counts, seed, and engine version. `SimulationDrawArtifact` Parquet lives on the object store (`CUSTOMER_AMOUNT_TRANSIENT`) and is not a public planning schema root. HTTP is `Cache-Control: private, no-store`. Clients cannot submit draws, outcomes, quantiles, correlation results, P(improvement), tail losses, or simulation fingerprints.

## ADR-P6-092 — P6-09 CVaR and P(improvement) remain canonical

P6-09A summaries call existing `conditional_value_at_risk` and `probability_improvement`. Frontier, posture, and `RiskFrontierService.evaluate` signatures are unchanged. A completed run’s Parquet is mapped to `(candidate_draws, baseline_draws)` by `p6_09_bridge.py`. Missing in-memory draws still yield `POSTERIOR_RISK_UNAVAILABLE`. Too few draws for the requested tail probability is `SIMULATION_INSUFFICIENT_DRAWS_FOR_TAIL_METRIC`.

## ADR-P6-093 — P6-10 consumes only SimulationEvidenceHandoff

The serialized handoff is refs, fingerprints, engine version, limitations, and `as_of_time`. It contains no raw arrays and imports no P6-10 types. Team 2 may attach `simulation_evidence_handoff_ref` later. This is the only convergence seam.

## ADR-P6-094 — as_of_time is the historical-backtesting seam

Distribution sets and run specs pin `effective_period` plus `as_of_time`. V1 does not implement full historical backtesting. Future backtests must reuse this temporal authority rather than substituting latest state.

## Additional freeze notes

- `PlanningChannelAllocation.amount` is pre-P6 compatibility, not value authority (see source-authority doc).
- Five optional Drive budget folder IDs are frozen; P6-01 provisions.
- No fake 200 Planning routes in P6-00.
