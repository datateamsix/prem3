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

## Additional freeze notes

- `PlanningChannelAllocation.amount` is pre-P6 compatibility, not value authority (see source-authority doc).
- Five optional Drive budget folder IDs are frozen; P6-01 provisions.
- No fake 200 Planning routes in P6-00.
