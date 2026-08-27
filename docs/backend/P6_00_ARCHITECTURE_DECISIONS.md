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

## Additional freeze notes

- `PlanningChannelAllocation.amount` is pre-P6 compatibility, not value authority (see source-authority doc).
- Five optional Drive budget folder IDs are frozen; P6-01 provisions.
- No fake 200 Planning routes in P6-00.
