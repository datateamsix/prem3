# P6 source authority

This document records implementation-baseline override and architectural reconciliation for Planning & Optimization. It does **not** rewrite the three product source documents.

## Canonical product sources (bodies unchanged)

Checked in under `docs/context/`:

1. `PREM3_INVESTMENT_PLAN_BUDGET_INGESTION_FEATURE_SPEC.md`
2. `PREM3_MARKETING_PORTFOLIO_ASSET_ALLOCATION_AND_OPTIMIZATION_SPEC.md`
3. `PREM3_PLANNING_OPTIMIZATION_BACKEND_MISSION_PLAN.md`

Those files remain product/architecture authority for privacy, Drive value ownership, optional Investment Plan, MMM-vs-MTA, proposal immutability, Meridian-native-first optimization, and exposure-integrity guardrails.

## Implementation baseline override

The Investment Plan spec cites architecture baseline `main` at `0d72636c2b7298a29e212ac3b382a52e11933425`.

**P6-00 implementation baseline is:**

```text
9ece5acfaadceed773493018a97dba16eabf4b03
branch: feature/prem3-p6-00-planning-portfolio-architecture
worktree: prem3-p6-00
```

That SHA is the earliest committed surface with Project architecture, Business IQ, Data Foundation, Firestore, Drive, canonical Channel Registry, and cross-method `ChannelBinding`. P6-00 does not cherry-pick or merge `f5a0851`. M3/M5 commits in ancestry are consumed as shared contracts, not owned as runtime.

## Architectural reconciliation (do not treat as product-rule changes)

### Project vs Workspace routes

Source specs use `workspace_id` and `/v1/workspaces/{workspace_id}/investment-plans`.

Repository compatibility: `project_id == workspace_id`. Canonical P6 routes are `/v1/projects/{project_id}/...`. Workspace paths are aliases of one state machine. Planning contracts store both fields and require equality.

### PlanningChannelAllocation.amount

At `9ece5ac`, `PlanningChannelAllocation.amount: float | None` exists on the shared Channel Registry seam. P6 amount authority is Drive-owned `Decimal` on transient `PortfolioView`. P6-00 does not modify `app/domain/channels/bindings.py`. P6 assemblers reject the legacy float as value authority.

### Market identity

Planning requires Identity Graph `CanonicalMarket.market_id`. Display strings are non-authoritative. P6 does not own market identity and does not derive IDs from names, fuzzy labels, or ISO 3166 codes (`"United States"`, `"US"`, `"USA"`). Unresolved identity fails closed and blocks `INVESTMENT_PLAN_READY`. Historical Business IQ market refs join only through `BusinessMarketBinding`. See `BUSINESS_IQ_INTEGRATION_REQUEST` below.

### Channel identity

Planning joins on Channel Registry `channel_id` + `channel_registry_version`. BIQ `MarketingChannel.channel_id` remains profile-local (`bch_*`). Use `registry_channel_id` to bind. Do not invent `planning_channel_id`.

### Actuals as a baseline

The optimization spec allows a governed actual-spend snapshot as a baseline. The mission plan forbids labeling actuals as an approved plan. Both are true: baseline kinds `ACTUAL_YTD` / `GOVERNED_ACTUALS` are distinct from `APPROVED_PLAN`.

### Drive folder layout

The Investment Plan spec freezes `budgets/templates` and `budgets/plans`. The mission plan also names `scenarios/` and `proposals/`. P6-00 freezes all five optional binding fields. P6-01 provisions folders.

## BUSINESS_IQ_INTEGRATION_REQUEST

Requested from Business IQ / Identity Graph, not implemented in P6-00:

1. Durable server-issued `market_id` (not client-supplied display strings).
2. Typed channel↔market references (`MarketingChannel.markets` is untyped strings today).
3. Fail-closed resolution policy owned by IG-00/IG-01, consumed by Planning.

IG-01 closed this request at the contract layer (`CanonicalMarket`, `BusinessMarketBinding`). P6 consumes `app/identity_graph/` and keeps `CANONICAL_MARKET_CONTRACT_INTEGRATED`. Unknown or non-canonical market values still fail closed. Do not reopen P6-00 architecture.

## P6-01 canonical market integration

Join authority remains `market_id × channel_id`:

- `market_id` → Identity Graph `CanonicalMarket`
- `channel_id` → canonical Channel Registry

**Canonical Market source commit:**

```text
53b606a3b3bc529254816b8376d57c181b44a7ec
branch: feature/prem3-ig-01-market-ga4-topology
method: path-checkout of shared Identity Graph files (not an IG-01 branch merge)
```

Do not merge the entire IG-01 branch. Do not duplicate Identity Graph contracts under `app/investment_planning/`.

Files imported from that SHA:

- `app/identity_graph/`
- `docs/backend/CANONICAL_MARKET_IDENTITY.md`
- `docs/backend/BUSINESS_IQ_MARKET_BINDING.md`
- `tests/unit/identity_graph/conftest.py`
- `tests/unit/identity_graph/test_canonical_market.py`
- `tests/unit/identity_graph/test_biq_market_bridge.py`

GA4 topology, Campaign Ledger, and IG-02 are not P6-01 prerequisites. `campaign_id` is optional execution detail when present; it is not part of the canonical P6 portfolio grain and is not required for `INVESTMENT_PLAN_READY`. Continue P6-01 without waiting for IG-02.
