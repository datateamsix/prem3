# PreM3 Planning & Optimization — Backend Mission Plan
## Investment Plan → Marketing Investment Portfolio → Governed Asset Allocation & Optimization

**Status:** Proposed sequential backend execution plan  
**Date:** 2026-08-26  
**Source specifications:** Investment Plan / Budget Ingestion and Marketing Portfolio Asset Allocation & Optimization  
**Parallelism:** Can begin immediately in parallel with MTA M5-02A  
**Recommended mission namespace:** `P6-*`

---

## 1. Architecture

Treat this as three bounded capabilities sharing one portfolio contract:

```text
Business IQ
  ↓
Investment Plan
Drive-owned approved budget values
  ↓
Marketing Investment Portfolio
transient plan + actuals + evidence + exposure view
  ↓
Optimization
accepted MMM + assumptions + constraints + risk posture
  ↓
Immutable proposal
  ↓
Human decision
  ↓
New Drive Investment Plan version
  ↓
Execution / outcomes / MEL
```

The shared portfolio representation is the center of the architecture.

### Non-negotiable boundaries

- One canonical `channel_id` / market identity across BIQ, Data Foundation, MMM, MTA, Planning, and Decision Intelligence.
- Google Drive owns budget workbook bytes, allocation amounts, scenario values, and recommended allocation values.
- Firestore stores references, fingerprints, states, receipts, and approval metadata only.
- Amount-bearing `PortfolioView` and optimization responses are transient, private/no-store, excluded from logging/APM/analytics/session replay/caches.
- `ACTUAL_YTD` is never labeled an approved plan.
- Optimization creates proposals; it does not mutate an active plan or activate media.
- Accepted MMM response evidence is the primary causal return engine.
- MTA can contribute tactical/recent journey evidence but never substitutes attribution weights for MMM response curves.
- Meridian native fixed-budget optimization comes before custom risk-aware optimization.

---

## 2. Sequential backend missions

```text
P6-00  Planning & Portfolio Architecture Freeze
   ↓
P6-01  Drive-Native Investment Plan Foundation
   ↓
P6-02  Shared Portfolio Snapshot + Dashboard Read Model
   ↓
P6-03  Actuals + Measurement Coverage + Portfolio Observations
   ↓
P6-04  Optimization Readiness + Portfolio-to-Model Mapping
   ↓
P6-05  Native Meridian Fixed-Budget Optimization
   ↓
P6-06  Scenario Artifacts + Proposal Governance + Plan Revision
   ↓
P6-07  Flexible Budget + Future Assumptions + Advanced Constraints
   ↓
P6-08  Exposure Risk & Delivery Health Integration
   ↓
P6-09  Risk-Aware Marketing Investment Frontier
   ↓
P6-10  Decision Outcomes + MEL Learning Closure
```

P6-00 through P6-03 are model-independent and can run now.

P6-04 can be developed against accepted-model contracts while modeling work continues.

P6-05 requires an accepted MMM for final live acceptance.

MTA is not a blocker for P6-05.

---

## 3. P6-00 — Planning & Portfolio Architecture Freeze

**Goal:** Freeze bounded contexts, privacy boundaries, persisted-versus-transient contracts, canonical dimensions, states, and route namespaces.

### Deliverables

Create/reuse:

```text
InvestmentPlan
BudgetDriveSourceVersion
BudgetColumnMapping
InvestmentPlanValidationReceipt

PortfolioSnapshotRef
PortfolioBaselineKind
PortfolioDimensionMapping

PortfolioView
PortfolioSummary
PortfolioAllocationView
QuarterlyPortfolioView
PortfolioEvidenceCoverage
PortfolioObservation
PortfolioSourceFreshness

OptimizationProposalRef
```

Freeze value semantics:

```text
PLANNED
APPROVED
COMMITTED
FLEXIBLE
ACTUAL
FORECAST_AT_COMPLETION
REMAINING
RECOMMENDED
```

Freeze bounded domains:

```text
app/investment_planning/**
app/investment_optimization/**
```

Freeze the persisted/transient rule:

```text
PortfolioSnapshotRef = durable metadata
PortfolioView = transient values
OptimizationProposalRef = durable metadata
Optimization result artifact = customer-owned Drive
```

### Required privacy tests

Prove amount-bearing contracts cannot be serialized into control-plane persistence and that responses are private/no-store.

---

## 4. P6-01 — Drive-Native Investment Plan Foundation

**Goal:** Deliver the optional Investment Plan end-to-end with Google Drive as source of truth.

### Scope

Add optional Drive binding fields:

```text
budgets_folder_id
budget_templates_folder_id
budget_plans_folder_id
```

Provision idempotently beneath existing:

```text
prem3-modeling/
  budgets/
    templates/
    plans/
    scenarios/
    proposals/
```

Implement:

```text
Business-IQ-aware XLSX template
CSV/XLSX parser
column mapping
market/channel resolution
initiative roll-up
mixed-grain guard
blank-vs-zero semantics
Decimal currency handling
Drive version/checksum concurrency guard
deterministic validation
```

Only deterministic code emits:

```text
INVESTMENT_PLAN_READY
```

This receipt stays optional and does not broaden BIQ/DF/MMM/MTA readiness.

### Privacy proof

```text
Drive → contains values
Firestore → metadata only
PreM3 GCS → no budget artifact
logs/traces → no amounts or cells
```

---

## 5. P6-02 — Shared Portfolio Snapshot + Dashboard Read Model

**Goal:** Build the one portfolio abstraction used by both Planning and Optimization.

Persist:

```text
PortfolioSnapshotRef
```

Assemble per authorized request:

```text
PortfolioView
```

Authority order:

```text
request/tenant authority
→ pinned Business IQ
→ selected baseline ref
→ authorized Drive plan values
→ governed Data Foundation actuals
→ evidence references
→ deterministic totals/shares/variance
→ private/no-store response
```

Support four states:

```text
PLAN + ACTUALS
PLAN ONLY
ACTUALS ONLY
NEITHER
```

Actual-only must render as an observed-spend portfolio, never as an approved plan.

Read models:

```text
overview
channel allocation
market allocation
quarterly profile
plan vs actual
remaining / variance
source freshness
```

All totals must reconcile using `Decimal`.

---

## 6. P6-03 — Actuals + Measurement Coverage + Portfolio Observations

**Goal:** Connect the portfolio to the wider evidence system before optimization.

### Actuals

Consume Data Foundation actual-spend contracts with:

```text
source
currency
freshness
as_of
reconciliation state
market_id
channel_id
```

Stale/partial actuals remain explicitly stale/partial.

### Measurement coverage

Attach accepted references for:

```text
MMM
MTA
experiments/calibration
brand evidence where valid
```

Coverage is multi-label, not a score.

### Deterministic observations

Implement rules for:

```text
pacing variance
concentration
committed capital
plan line without actual source
actual source without plan line
allocation without accepted measurement
stale model evidence
stale spend source
```

Gemini may explain deterministic observations later but does not create their truth state.

MTA can plug in whenever available; P6-03 does not wait for it.

---

## 7. P6-04 — Optimization Readiness + Portfolio-to-Model Mapping

**Goal:** Deterministically map planning grain to model-supported grain and prove optimization feasibility.

Create:

```text
PortfolioToModelMapping
OptimizationReadinessReceipt
OptimizationObjective
OptimizationHorizon
ScenarioAssumptions
OptimizationConstraintSet
RiskPosture
```

Planning may be:

```text
market × channel × quarter
```

while accepted MMM may support a coarser grain.

Every unsupported line requires an explicit policy:

```text
HOLD_BASELINE
EXPERIMENT_RESERVE
EXCLUDE_FROM_OPTIMIZATION
APPROVED_PROXY
```

Never infer missing evidence = zero value.

Readiness requires:

```text
baseline pinned
Business IQ pinned
accepted model + health approval
portfolio/model mapping complete
objective valid
currency/period aligned
future assumptions explicit
constraints feasible
unsupported lines resolved
solver/version config pinned
```

Ends at:

```text
OPTIMIZATION_READY
```

No recommendation yet.

---

## 8. P6-05 — Native Meridian Fixed-Budget Optimization

**Goal:** Ship the first causal budget-allocation engine using Meridian's native optimizer.

MVP:

```text
fixed total budget
→ maximize expected incremental KPI/revenue
```

Create:

```text
MeridianBudgetOptimizerAdapter
```

Adapter owns:

```text
PreM3 portfolio/config
→ Meridian inputs
→ BudgetOptimizer
→ normalized PreM3 result
```

Initial constraints:

```text
channel min/max
locked allocations
max movement
selected period
supported geographies
future cost/media-unit assumptions
```

### Mandatory parity gate

Before shipping custom risk logic, prove PreM3 normalized output matches Meridian native output within approved tolerance using identical model/grid/budget/bounds/assumptions.

Sensitive results are written to customer Drive. Firestore stores only `OptimizationProposalRef`.

---

## 9. P6-06 — Scenario Artifacts + Proposal Governance + Plan Revision

**Goal:** Turn optimizer output into a governed decision workflow.

Write customer-owned artifacts:

```text
budgets/scenarios/
FY{year}_scenario_{id}_v001.json
FY{year}_scenario_{id}_v001.xlsx

budgets/proposals/
...
```

Workflow:

```text
SCENARIO
→ RECOMMENDED
→ HUMAN APPROVAL
→ NEW INVESTMENT PLAN VERSION
```

Actions:

```text
save scenario
compare compatible scenarios
propose reallocation
approve
modify
reject
```

Approval always creates a new plan version and never overwrites the predecessor.

Persist a metadata-only decision receipt.

---

## 10. P6-07 — Flexible Budget + Future Assumptions + Advanced Constraints

**Goal:** Extend from “how should this budget be allocated?” to “how much should we invest under explicit hurdle rates and future assumptions?”

Add:

```text
B_min / B_max
target ROI
target mROI
future CPM / cost per media unit
future flighting
revenue per KPI
contribution margin
market/quarter constraints
movement limits
funnel-group constraints
experiment reserve
```

If governed revenue/margin conversion does not exist, optimize/report the original KPI and cost per incremental KPI. Never fabricate financial return.

---

## 11. P6-08 — Exposure Risk & Delivery Health Integration

**Goal:** Connect the Exposure Integrity layer directly to the portfolio.

Preserve separately:

```text
served
rendered
measurable
viewable
human
in-target
reach
frequency
IVT
attention/completion
```

Do not invent a universal composite score.

Three allowed optimization roles:

```text
A. model/media-execution input
B. constraint/feasibility guardrail
C. scenario/confidence adjustment
```

Hard constraints require a defensible spend→quality relationship. Otherwise exposure evidence remains a monitoring/approval/scenario guardrail.

---

## 12. P6-09 — Risk-Aware Marketing Investment Frontier

**Goal:** Add PreM3 downside-risk selection only after risk-neutral Meridian parity.

Process:

```text
generate feasible portfolios
→ evaluate posterior/scenario draws
→ expected value
→ probability of improvement
→ lower-tail loss / CVaR
→ concentration / stability
→ remove dominated portfolios
→ select by confirmed RiskPosture
```

Initial postures:

```text
EXPECTED_OUTCOME
BALANCED
CONSERVATIVE
```

Render a:

```text
Marketing Investment Frontier
```

Do not imply native Meridian already optimizes downside risk.

---

## 13. P6-10 — Decision Outcomes + MEL Closure

**Goal:** Learn from recommendation → decision → execution → outcome.

Record governed metadata/references for:

```text
recommendation
human modifications
approval/rejection
execution adherence
realized outcome
exposure-quality realization
prediction error
model/solver stability
```

MEL stores metadata/fingerprints/references, not allocation values.

---

## 14. Immediate parallel plan

Run now:

```text
M5-02A
Real DP6 MTA closure

P6-00
Planning/portfolio contract freeze

P6-01
Drive-native Investment Plan
```

These are cleanly separable.

P6-02 follows P6-00 contracts and can begin while P6-01 is finishing.

---

## 15. Where accepted MMM becomes required

```text
Investment Plan                 no model required
Portfolio dashboard             no model required
Plan vs actual                  no model required
Measurement coverage            model optional
Optimization readiness          accepted MMM required for causal optimization
Native optimization             accepted MMM required
Risk-aware frontier             accepted MMM posterior/scenario evidence required
```

MTA is useful but not a causal optimization dependency.

---

## 16. Recommended frontend design sequence

After P6-00 contracts stabilize:

```text
Design P6-01
Marketing Investment Portfolio + Investment Plan

Design P6-02
Drive Setup + Budget Mapping + Validation

Design P6-03
Plan vs Actual + Measurement Coverage + Exposure Health

Design P6-04
Optimization Setup + Constraint Editor

Design P6-05
Current vs Recommended Portfolio

Design P6-06
Scenario Comparison + Investment Frontier + Decision Approval
```

---

## 17. Recommended next backend prompt

Start with:

```text
P6-00 — Planning & Portfolio Architecture Freeze
```

Its job is to remove ambiguity around:

```text
domain boundaries
canonical market/channel identity
Drive/value authority
persisted vs transient contracts
privacy/no-store enforcement
baseline authority
route namespace
readiness states
proposal authority
generated schemas
```

Do not start P6-00 by provisioning Drive or invoking Meridian.

---

## 18. Governing principle

> **PreM3 does not optimize a spreadsheet. It governs a marketing investment portfolio whose semantics, evidence, assumptions, constraints, recommendations, decisions, and outcomes remain reproducible.**
