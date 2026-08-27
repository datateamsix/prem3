# Planning & Marketing Investment Portfolio architecture

Product authority for this workstream:

- [PREM3_INVESTMENT_PLAN_BUDGET_INGESTION_FEATURE_SPEC.md](../context/PREM3_INVESTMENT_PLAN_BUDGET_INGESTION_FEATURE_SPEC.md)
- [PREM3_MARKETING_PORTFOLIO_ASSET_ALLOCATION_AND_OPTIMIZATION_SPEC.md](../context/PREM3_MARKETING_PORTFOLIO_ASSET_ALLOCATION_AND_OPTIMIZATION_SPEC.md)
- [PREM3_PLANNING_OPTIMIZATION_BACKEND_MISSION_PLAN.md](../context/PREM3_PLANNING_OPTIMIZATION_BACKEND_MISSION_PLAN.md)

Implementation baseline, Project vs Workspace aliasing, and shared-contract reconciliation live in [P6_SOURCE_AUTHORITY.md](P6_SOURCE_AUTHORITY.md). Decisions: [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md).

```mermaid
flowchart TD
    P[Project] --> BIQ[BusinessIQ]
    P --> IP[InvestmentPlan_metadata]
    P --> DF[DataFoundation]
    P --> C[MeasurementCycle]
    IP --> D[CustomerDrive_planValues]
    DF --> A[ActualSpend_BQ]
    C --> MMM[AcceptedMMM]
    C --> MTA[MTAEvidence]
    D --> PV[TransientPortfolioView]
    A --> PV
    BIQ --> PV
    MMM --> PV
    MTA --> PV
    PV --> OR[OptimizationReadiness]
    MMM --> OR
    OR --> O[OptimizationRun]
    O --> OP[OptimizationProposalRef]
    O --> DA[CustomerDrive_proposalArtifact]
    OP --> HD[HumanDecision]
    HD --> NP[NewInvestmentPlanVersion]
```

## Bounded contexts

- `app/investment_planning/` owns plan metadata, portfolio read contracts, privacy, and the metadata-only store barrier.
- `app/investment_optimization/` owns proposal refs, solver kinds, and the unimplemented Meridian adapter seam.
- Business IQ, Data Foundation, and `app/modeling/mmm/` are not Planning owners.

## Canonical grain

`Project × fiscal year × quarter × market_id × channel_id`

`channel_id` is the Channel Registry ID. `market_id` is the Identity Graph `CanonicalMarket` ID. Market display strings are non-authoritative. Planning does not own market identity and does not resolve markets by name, fuzzy match, or ISO code. Unresolved `market_id` fails closed and blocks `INVESTMENT_PLAN_READY`. `campaign_id` is not part of this grain. Campaign Ledger is not a prerequisite for `INVESTMENT_PLAN_READY`.

Canonical Market source commit: `53b606a3b3bc529254816b8376d57c181b44a7ec` (path-checkout; see [P6_SOURCE_AUTHORITY.md](P6_SOURCE_AUTHORITY.md)).

## Optional Investment Plan

The Investment Plan is Project-scoped and optional. Missing `INVESTMENT_PLAN_READY` does not block Business IQ, Data Foundation, MMM, MTA, or `MODEL_READY`.

## Actuals and observations (P6-03)

Governed actual spend is assembled through `ActualSpendQuery`. See [PORTFOLIO_ACTUALS_INTEGRATION.md](PORTFOLIO_ACTUALS_INTEGRATION.md), [PORTFOLIO_STATE_MODEL.md](PORTFOLIO_STATE_MODEL.md), [PORTFOLIO_EVIDENCE_COVERAGE.md](PORTFOLIO_EVIDENCE_COVERAGE.md), and [PORTFOLIO_OBSERVATIONS.md](PORTFOLIO_OBSERVATIONS.md).

`canonical_media` is not portfolio actual-spend authority. `OPTIMIZATION_READY` is not emitted.
