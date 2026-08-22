# PROMPT — PreM3 Data Foundation Design
## Discovery, Guided Provisioning, Governance & Pre-Modeling Handoff

**Status:** Product / UX design prompt  
**Audience:** Product design, UX, frontend planning  
**Parent stage:** Data Foundation  
**Primary sublayer:** Guided Data Provisioning  
**Upstream gate:** `BUSINESS_CONTEXT_READY`  
**Source-level gate:** `IMPORT_READY`  
**Environment-level gate:** `DATA_FOUNDATION_READY`  
**Downstream:** Pre-Modeling  
**Version:** `data-foundation/design-v1.0`

---

# 1. Design objective

Design Data Foundation as the durable evidence and measurement-infrastructure layer that follows Business IQ.

The user should not experience this as a connector catalog, upload wizard, or cloud-admin console.

The intended experience is:

> **PreM3 already knows what evidence should exist from Business IQ. It discovers what actually exists, explains what is missing, asks only what cannot be safely determined, and—when authorized—builds and validates the governed measurement foundation.**

The resulting foundation must support not only Meridian/MMM, but also forecasting, MTA/attribution, experiments, simulation, optimization, recommendations, and local MEL.

---

# 2. Product sequence

```text
BUSINESS IQ
What the business means
        ↓
BUSINESS_CONTEXT_READY
        ↓
DATA FOUNDATION
Discover + map + provision + validate + govern
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
Planning + readiness + EDA + remediation + model design
        ↓
MODEL_READY
        ↓
MODELING
```

Core rule:

> **Business IQ defines what PreM3 should look for. Data Foundation discovers, validates, provisions, and governs the evidence.**

---

# 3. Capability hierarchy

```text
Data Foundation
├── Source Coverage Inventory
├── Foundation Provisioning
│   ├── Infrastructure Provisioning
│   ├── Guided Source Provisioning
│   ├── Modeling Asset Provisioning
│   └── Governance & Observability Provisioning
├── Import Readiness
├── Mapping & Harmonization
├── Exposure Integrity
└── Model Readiness
```

Guided Data Provisioning is a subflow inside Data Foundation, not a separate stage.

---

# 4. Reuse the Business IQ shell

Keep the same overall product grammar already established in Business IQ:

- top stage navigation;
- left Foundation / Measurement navigation;
- restrained iconography;
- autosave;
- contextual explanations;
- persistent customer/workspace identity;
- consistent cards, statuses, and receipts.

Suggested Data Foundation subnavigation:

```text
DATA FOUNDATION
Overview
Sources
Infrastructure
Health & gaps
Review
```

Do not expose every backend provisioning enum as navigation.

---

# 5. Data Foundation landing

Use three clear jobs:

## Connect & discover

> **Connect your data environment**  
> Let PreM3 inspect the projects, datasets, tables, transfers, and files you authorize so it can find likely measurement sources.

CTA: `Connect BigQuery`

## Map sources & evidence

> **Map sources & evidence**  
> PreM3 uses Business IQ and the provider registry to identify which tables, files, or platforms likely contain the evidence your business needs.

CTA: `Review discovered sources`

## Build Data Foundation

> **Build Data Foundation**  
> PreM3 creates the approved datasets, tables, views, transfers, scheduled queries, routines/UDFs, quality checks, lineage, and monitoring required for the measurement environment.

CTA: `Build foundation`

---

# 6. Business IQ handoff

Do not re-ask what Business IQ already knows.

Inherit:

- KPI / outcome;
- measurement objective;
- markets / geography;
- material channels;
- channel roles;
- promotions;
- seasonality;
- pricing;
- inventory;
- competition;
- business events;
- prior-evidence availability;
- customer journey;
- budget decision process;
- acknowledged unknowns.

Show this explicitly:

> **Based on your Business IQ, PreM3 will look for:**

```text
✓ Revenue / transactions
✓ Paid Search
✓ Paid Social
✓ Connected TV
✓ Promotions
✓ Seasonal demand
? Competitive demand
? Inventory constraints
```

CTA: `Start discovery`

---

# 7. Source Coverage Inventory

The primary Data Foundation UX is a Source Coverage Inventory, not a generic connector grid.

Each source should resolve:

```text
Business concept / channel
        ↓
Provider
        ↓
Current source location
        ↓
History
        ↓
Cadence / freshness
        ↓
Geo / grain / metrics
        ↓
Current state
        ↓
Recommended action
```

Default source card:

```text
Paid Search
Google Ads

Location        BigQuery
History         43 months
Refresh         Daily · last load 8h ago
Geo             DMA available
Metrics         Spend + impressions + clicks
Status          VERIFIED SOURCE

[ Review ]
```

Expanded view may show lineage, account scope, provider limits, registry evidence, schema, owner, and QA.

---

# 8. Discovery-first UX

The core pattern is:

```text
DISCOVER
    ↓
INFER
    ↓
SHOW EVIDENCE
    ↓
ASK ONLY WHEN AMBIGUOUS
    ↓
USER CONFIRMS / CORRECTS
```

Avoid asking:

> Which provider supplies Paid Search?

when BigQuery metadata and registry evidence already strongly identify Google Ads.

Prefer:

> **PreM3 found a likely Paid Search source**

Then show why.

---

# 9. Provider registry as discovery accelerator

Provider registry knowledge may include:

- table naming patterns;
- schema signatures;
- expected fields;
- provider-specific spend/execution semantics;
- export options;
- native transfer availability;
- expected refresh behavior;
- geo capabilities;
- retention/backfill limits;
- known report quirks;
- authenticated provisioning capability.

Example:

```text
Why PreM3 thinks this is Google Ads

✓ BigQuery transfer identifies Google Ads
✓ Registry signature matched 14/16 expected fields
✓ Spend field detected
✓ Impression and click fields detected
✓ History aligns with Paid Search activity
```

If provider identity is deterministic, do not force redundant confirmation.

---

# 10. Evidence semantics

Separate:

## How PreM3 knows

- Verified
- Detected
- Inferred
- User-provided
- Provider-documented
- Unknown

## What the user decided

- Accepted
- Needs review
- Rejected
- Deferred

Do not combine provenance and workflow state into one badge.

---

# 11. Declared vs observed

Never silently replace user declarations with observed facts.

Example:

```text
Refresh cadence

Expected
Daily
Provided by you

Observed
~24–28 hours
Detected from recent loads

Current lag
37 hours

Status
Late
```

Use declared, observed, provider-documented, and unknown states explicitly.

---

# 12. Source location intake

Ask only when discovery cannot resolve it:

> **Where does this data live today?**

- BigQuery
- Google Drive
- Google Cloud Storage
- CSV / spreadsheet
- Another warehouse
- Another cloud-storage provider
- Only inside the provider platform
- Not currently collected
- Not sure
- Add a custom location: `[text]`

No generic `Other`.

---

# 13. Cadence and history intake

Ask only when not observable.

### Expected update cadence

- Continuous / streaming
- Hourly
- Daily
- Weekly
- Monthly
- Manual / ad hoc
- No longer updated
- Not sure
- Custom cadence

### Believed history

- < 3 months
- 3–6 months
- 6–12 months
- 12–24 months
- > 24 months
- Not sure

Later show declared vs observed side by side.

---

# 14. BigQuery connection flow

Preferred path:

```text
Connect Google
      ↓
Choose authorized customer project
      ↓
Discovery-only inspection
      ↓
Select measurement home
      ↓
PreM3 proposes / creates prem3_modeling
```

Important:

> **PreM3 does not create the customer's GCP project.**

It creates approved resources inside an authorized project.

---

# 15. Separate discovery permission from provisioning permission

## Discovery access

Used for:

- projects/datasets metadata;
- schemas;
- partitions;
- routines;
- transfer configs;
- scheduled query/job history;
- bounded profiling.

Copy:

> **Discovery access lets PreM3 investigate your measurement environment. It does not allow PreM3 to create or change resources.**

## Provisioning access

Requested only after a plan requires it.

May include:

- create dataset;
- create table/view;
- create routine/UDF;
- create transfer;
- create scheduled query;
- create approved monitoring;
- narrowly scoped IAM where approved.

Copy:

> **Provisioning access is requested only when you approve a Foundation Plan that requires changes.**

---

# 16. BigQuery discovery results

Group candidate sources into:

## Verified sources
Strong deterministic identity.

## Likely matches
Business confirmation needed.

## Needs your decision
Multiple plausible sources or unclear semantics.

## Not relevant
Collapsed by default.

Example:

```text
Revenue

Likely source
commerce.orders

Evidence
✓ transaction_date
✓ net_revenue
✓ order_id
✓ 42 months history
✓ daily refresh

Alternative
finance.weekly_sales

PreM3 recommendation
Use commerce.orders as canonical revenue.

[ Accept ]
[ Choose another ]
[ Not sure ]
```

---

# 17. Google Drive / file path

Google Drive is a secondary evidence/import path, not the canonical measurement plane.

Use for:

- historical CSV exports;
- prior MMMs;
- experiment reports;
- promotion calendars;
- pricing history;
- offline data;
- controls;
- agency files.

Suggested folder:

```text
prem3-modeling/
├── imports/
├── exports/
└── reports/
```

Explain:

> PreM3 may materialize approved file-based evidence into the governed BigQuery foundation.

---

# 18. Source health

Each source should have explicit dimensions:

```text
ACCESSIBILITY
HISTORY
CONTINUITY
FRESHNESS
SCHEMA
GRAIN
GEOGRAPHY
METRIC COVERAGE
REFRESH AUTOMATION
PROVENANCE
```

Example:

```text
Google Ads — Paid Search

Accessibility       Ready
History             43 months
Continuity          3 gaps
Freshness           Late by 13h
Schema              Expected
Grain               Daily
Geography           DMA + national
Metric coverage     Spend + impressions + clicks
Refresh             Automated
Provenance          Verified
```

Avoid a single opaque health/readiness score as authority.

---

# 19. Cross-source alignment

Add a Foundation Alignment section after individual health.

Evaluate:

- common temporal overlap;
- time zones;
- currencies;
- geo compatibility;
- KPI/media overlap;
- time-grain compatibility;
- channel coverage overlap;
- duplicate risk.

Example:

```text
Cross-source alignment

Longest media history          43 months
Shortest material media        11 months
KPI history                    42 months
Common window                  11 months

Geo
KPI                            DMA
Paid Search                    DMA
Paid Social                    National only

Status                         REVIEW NEEDED
```

This is a system-level evidence view.

---

# 20. Gap classes

Use explicit consequence classes:

| Class | Meaning |
|---|---|
| `FOUNDATION_BLOCKER` | Environment cannot be established |
| `SOURCE_BLOCKER` | One required source cannot proceed |
| `PREMODEL_BLOCKER` | Foundation can exist; Pre-Modeling cannot pass |
| `PREMODEL_REVIEW` | Carry forward for modeler judgment |
| `ADVISORY` | Document and proceed |

Do not say all unresolved gaps are non-blocking.

---

# 21. Four acquisition paths

Route each source to one of four paths.

### A. Existing source
**Discover and validate existing data**

### B. Supported automation
**Set up with PreM3**

### C. Manual prerequisite/export
**Generate export or prerequisite plan**

### D. No data
**Create data-collection plan**

The user should always understand what PreM3 can do vs what they need to do.

---

# 22. Guided Data Provisioning

Guided Data Provisioning is the customer-facing permission/approval workflow for approved resource creation.

PreM3 may:

- discover;
- recommend;
- preview;
- request authorization;
- execute approved plans;
- validate;
- issue receipts.

PreM3 may not silently mutate the customer environment.

---

# 23. Foundation Provisioning Plan

Screen heading:

> **Review your Data Foundation Plan**

Supporting text:

> PreM3 compiled this from your Business IQ, discovered environment, provider registry capabilities, and current permissions. Nothing below will be changed until you approve it.

Organize into four domains.

## Infrastructure
- create/reuse `prem3_modeling`;
- dataset location;
- labels/descriptions;
- landing structures;
- approved APIs / narrow IAM where supported.

## Sources & transfers
- reuse existing transfers;
- create supported provider transfers;
- scheduled imports;
- backfills;
- leave customer-managed ETL untouched.

## Modeling data assets
- source-interface views;
- staging;
- canonical media/KPI/control/treatment tables;
- model-input tables;
- stable views.

## Governance & observability
- source registry;
- freshness checks;
- transfer monitoring;
- schema drift;
- reconciliation;
- lineage;
- audit receipts.

---

# 24. Plan action classes

For every resource show:

```text
REUSE
CREATE
CHANGE
CUSTOMER-MANAGED
```

Example:

```text
prem3_modeling dataset       CREATE
Google Ads transfer          REUSE
Meta Fivetran pipeline       CUSTOMER-MANAGED
canonical_media view         CREATE
```

---

# 25. “Will not modify” trust section

Before approval show:

> **PreM3 will not modify**

Examples:

- existing source tables;
- campaign settings;
- bids;
- budgets;
- targeting;
- unrelated datasets;
- customer-managed ETL;
- provider commercial settings.

---

# 26. Permission preview

Example:

```text
Permissions required

BigQuery
✓ Create dataset
✓ Create table/view
✓ Run jobs
✓ Create scheduled query

BigQuery Data Transfer
✓ Create transfer configuration

Not requested
— Campaign management
— Billing administration
— Unrelated datasets
```

Explain why each permission is needed in plain language.

---

# 27. Approval behavior

Approval binds to the exact immutable plan version.

If destination, scope, permissions, schedule, backfill, cost, or material resource actions change:

> **Updated plan — review required**

Do not silently reuse old approval.

Where technically valid, action groups can be separately approved, but dependency-invalid partial approvals must be blocked.

---

# 28. Provisioning progress

Example:

```text
Building Data Foundation

✓ BigQuery dataset ready
✓ Source registry created
✓ Canonical tables created
✓ Google Ads source verified
◌ DV360 transfer — first sync running
○ Governance checks
○ Final validation
```

Support `View details`.

Use distinct states for:

- running;
- waiting for provider;
- customer action needed;
- failed;
- complete.

---

# 29. First-load QA

Never equate connector success with usable data.

After setup, PreM3 validates:

- expected source objects exist;
- expected account scope appears;
- required fields exist;
- time/time zone interpretable;
- currency known;
- history quantified;
- freshness observed;
- schema fingerprint stored;
- duplicate/reissue behavior understood;
- reconciliation performed where available.

---

# 30. Source gate — IMPORT_READY

A source can be:

```text
CONNECTED
but
NOT IMPORT READY
```

`IMPORT_READY` means the source has passed the governed source/import contract and can enter further Data Foundation processing.

It does not mean model-ready.

---

# 31. Environment gate — DATA_FOUNDATION_READY

Environment-level completion requires:

- required infrastructure exists;
- required source paths are resolved;
- required sources are import-ready or carry approved non-blocking exceptions;
- modeling assets exist from pinned contracts;
- governance controls are active;
- first-load QA passed;
- unresolved gaps are typed.

Show explicitly:

> **Data Foundation Ready is not Model Ready.**

---

# 32. Completion screen

```text
DATA FOUNDATION READY

Your governed measurement environment is ready for Pre-Modeling.

BigQuery
acme-marketing-prod.prem3_modeling

Sources
6 import-ready
1 pre-modeling review
1 unavailable

Automation
5 automated
2 customer-managed

Governance
Freshness monitoring active
Schema drift monitoring active
Lineage active
Transfer monitoring active

Next
Pre-Modeling
Planning, readiness, EDA, remediation & model design

[ Continue to Pre-Modeling ]
```

---

# 33. Provisioning receipt

Create a durable human-readable receipt.

```text
Foundation Provisioning Receipt

Plan version
v4

Approved
Aug 21, 2026 · 11:42 AM

Created
• prem3_modeling
• 7 canonical tables
• 4 stable views
• 3 scheduled queries
• 1 DV360 transfer
• 6 governance controls

Reused
• Google Ads transfer
• GA4 export
• Shopify orders

Remaining
• Competitive evidence unavailable
• Streaming Audio history insufficient
```

This is proof, not a log dump.

---

# 34. Persistent operating dashboard

After onboarding, Data Foundation becomes a long-lived operational surface.

```text
Data Foundation
Healthy

Last evaluated
2 hours ago

Sources             8
Healthy             6
Needs attention     1
Unavailable         1

Automated refresh   6
Customer-managed    2

Freshness           7 current / 1 late
History             11–43 months
```

Persistent actions:

- Add channel/provider
- Connect source
- Replace source
- Upload history
- Backfill
- Change refresh
- Reauthorize
- Pause source
- Retire source
- View lineage
- View receipt

---

# 35. Add new channel after onboarding

Example:

```text
+ Add channel

Business IQ
Streaming Audio
Role: Demand creation / Brand building

Data Foundation
Provider not mapped

PreM3 searches for:
• Spotify
• Pandora
• iHeart
• SXM Media
• agency export
```

If no source exists:

```text
Status
COLLECTING

Recommendation
Set up a recurring source now so history can accumulate.

[ Set up with PreM3 ]
[ Upload history ]
[ Create collection plan ]
```

Adding a channel does not automatically mutate an existing MMM.

---

# 36. Evidence-triggered Business IQ clarification

Signature PreM3 pattern:

```text
Data Foundation found
Paid Social has no delivery Apr 1–May 15.

Business IQ says
Paid Social is always-on.
Inventory can affect marketing.

PreM3 asks
Was Paid Social intentionally paused?

[ Yes ]
[ No ]
[ Not sure ]
```

If yes:
> Business Profile update proposed

If no:
> Data quality investigation created

The answer must create a real state/action.

---

# 37. “PreM3 Data Intelligence Brief”

Add a curated agentic summary.

```text
PREM3 DATA INTELLIGENCE BRIEF

What PreM3 found
• 6 of 8 expected sources already exist in BigQuery.
• Google Ads and GA4 use automated native exports.
• Paid Social is customer-managed through Fivetran.
• Streaming Audio has no historical source.
• Promotion history exists in Drive but is manual.
• Revenue and most media overlap for 31 months.

What matters most
1. Paid Social has 3 unexplained gaps.
2. Streaming Audio has no usable historical evidence.
3. Paid Social is national-only while KPI is DMA-level.
4. Promotion history is available but not automated.

PreM3 recommends
• investigate Paid Social gaps before Pre-Modeling;
• materialize promotion history into the foundation;
• begin Streaming Audio collection immediately;
• carry the national-vs-geo mismatch into model design.
```

The brief complements—not replaces—the detailed source inventory.

---

# 38. Customer learning philosophy

Carry forward:

> **Teach through consequence, not curriculum.**

Use short applied explanations.

### Refresh cadence
> A source expected daily but arriving weekly can create false zeroes and distort channel variation.

### History
> Continuous history gives PreM3 more business cycles and variation to evaluate during Pre-Modeling.

### Geography
> Geo variation can help measurement only when media and outcomes exist at compatible levels.

### Spend + execution
> Spend shows investment; execution metrics describe what media was actually delivered.

### Lineage
> Lineage lets PreM3 prove where a modeled value came from and detect upstream changes.

These are optional and contextual.

---

# 39. “PreM3 can” vs “You need to”

Every unresolved source should make ownership clear.

Example:

```text
DV360 prerequisite

PreM3 can
✓ create the BigQuery transfer after DTV2 is available
✓ validate first sync
✓ create source interfaces
✓ monitor freshness

You need to
• ask your agency / DV360 support to provision DTV2
• provide the approved bucket

[ Generate prerequisite request ]
```

---

# 40. DV360 guided-provisioning vertical slice

Because DV360 is the initial executable provider, mock a complete path.

## Initial state

```text
Programmatic Display
Display & Video 360

Location
Platform only

Registry capability
Prerequisite then automate

Prerequisite
DV360 DTV2 bucket

Status
ACTION NEEDED

[ Set up with PreM3 ]
```

## Prerequisite

Explain that DTV2 must be provisioned by DV360 support/agency.

Actions:

- Generate prerequisite request
- I already have DTV2
- Defer

## Plan preview

```text
REUSE
GCP project
acme-marketing-prod

CREATE
prem3_modeling

CREATE
PreM3 - DV360 - DTV2 Daily Transfer

SCOPE
Approved advertiser

SCHEDULE
Daily · 06:00 UTC

VALIDATION
7-day validation backfill

MONITORING
Transfer health
Freshness
Schema
Expected views
```

Then show permissions and exact approval.

---

# 41. Ongoing governance

Monitor:

- authorization expiration;
- transfer failure;
- stale partitions;
- missing intervals;
- schema field changes;
- type changes;
- row-count collapse;
- null spikes;
- currency/unit drift;
- geo changes;
- source disappearance.

Example:

```text
Paid Search
Needs attention

Expected
Daily

Observed
No successful update for 51 hours

Likely cause
Transfer failed twice

[ Review ]
```

---

# 42. Engine-specific implications

Data Foundation may surface consequences without making final model decisions.

Example:

```text
Streaming Audio

History      9 weeks
Refresh      Healthy
Source       Import ready

Measurement implications
MMM          insufficient history — review later
Forecasting  usable as recent driver
MTA          event-level data unavailable
```

This reinforces:

> source readiness ≠ engine eligibility.

---

# 43. Pre-Modeling handoff

Primary CTA:

> **Continue to Pre-Modeling**

Supporting copy:

> PreM3 will now evaluate whether the governed evidence can support the measurement objective defined in Business IQ.

Preview:

- Scope & plan
- Readiness assessment
- Data repair/remediation
- Official Meridian EDA
- Business–evidence reconciliation
- Model Design Brief

---

# 44. Required screens

Design at least:

1. Data Foundation landing
2. Inherited Business IQ evidence requirements
3. Google discovery authorization
4. BigQuery project selection
5. Discovery in progress
6. Discovery results
7. Verified source
8. Likely-source confirmation
9. Ambiguous-source decision
10. Source health
11. Cross-source alignment
12. Gap review
13. Google Drive/file path
14. Platform-only source
15. Guided provisioning eligibility
16. Foundation Provisioning Plan
17. Permission preview
18. Approval state
19. Provisioning progress
20. First-load validation
21. Provisioning receipt
22. Data Foundation Ready
23. Persistent dashboard
24. Add channel/provider
25. Replace source
26. Reauthorization/stale source
27. Evidence-triggered Business IQ question
28. Pre-Modeling handoff
29. DV360 prerequisite
30. DV360 guided provisioning

---

# 45. Required prototype scenarios

## Mature BigQuery
Most sources already exist. PreM3 largely discovers and confirms.

## Mixed environment
Google Ads in BQ, Meta through Fivetran, CTV CSV in Drive, promotions spreadsheet.

## No PreM3 dataset
Authorized GCP project exists; PreM3 provisions approved measurement assets.

## Platform only
DV360 requires prerequisite then automated transfer.

## Stale source
Existing table has not refreshed for three days.

## Geo mismatch
KPI DMA, Search DMA, Social national-only.

## New channel
Streaming Audio added after onboarding; no history yet.

## Business/data contradiction
Business IQ says always-on, data shows six-week gap.

## Partial approval
Infrastructure/Google sources approved; Drive deferred.

## Revoked authorization
Previously import-ready source loses access.

---

# 46. Color semantics

Carry forward a strict state language:

```text
INDIGO   active / selected / navigation
CYAN     deterministically verified / completed
GREEN    user-declared business importance / positive business state
AMBER    review / caution / waiting on customer
RED      blocked / failed
GRAY     neutral / unknown / inactive
```

Do not use green for deterministic Data Foundation verification if green already means “Important” in Business IQ.

---

# 47. Design acceptance criteria

## Discovery
- Business IQ requirements are inherited.
- Registry knowledge visibly reduces discovery effort.
- Authorized BigQuery assets can be discovered automatically.
- Deterministic sources do not require redundant confirmation.
- Ambiguous business meaning does require confirmation.

## Evidence
- Declared and observed values remain distinct.
- Provider documentation is distinct from observed behavior.
- History/freshness/geo/grain/metric coverage are visible.
- Cross-source alignment is represented.

## Provisioning
- Guided Data Provisioning remains inside Data Foundation.
- Plan shows REUSE / CREATE / CHANGE / CUSTOMER-MANAGED.
- Permissions are shown before approval.
- “Will not modify” is explicit.
- Material plan changes require new approval.
- Provisioning progress reflects deterministic state.

## Readiness
- `CONNECTED` ≠ `IMPORT_READY`.
- `IMPORT_READY` is source-level.
- `DATA_FOUNDATION_READY` is environment-level.
- `MODEL_READY` remains downstream.
- Empty provisioned structures never look like validated data.

## Lifecycle
- Data Foundation persists after onboarding.
- Users can add/pause/retire channels.
- Sources can be replaced/reauthorized.
- Health monitoring is first class.
- Data evidence can trigger Business IQ clarification.
- New channels can accumulate history before model inclusion.

## UX
- Same overall shell/design language as Business IQ.
- Icons clarify rather than decorate.
- Users are not forced to understand cloud implementation detail.
- “Why this matters” explanations are concise and contextual.
- The agent provides a curated Data Intelligence Brief.
- The next stage is clearly Pre-Modeling.

---

# 48. North star

The user should leave Data Foundation thinking:

> **“PreM3 knew what data should exist from our business profile, found most of it itself, showed us what was reliable and what was missing, built only the infrastructure we approved, and proved the resulting environment was healthy before asking us to move forward.”**

The conceptual progression is:

```text
WHAT SHOULD EXIST?
Business IQ
        ↓
WHAT EXISTS?
Discovery
        ↓
WHAT DOES IT MEAN?
Registry + profiling + confirmation
        ↓
WHAT IS MISSING?
Coverage + health + gaps
        ↓
WHAT SHOULD BE BUILT?
Foundation Provisioning Plan
        ↓
WHAT MAY PREM3 CHANGE?
Permissions + approval
        ↓
WHAT ACTUALLY WORKS?
First-load QA + receipts
        ↓
WHAT IS READY FOR PRE-MODELING?
DATA_FOUNDATION_READY
```

That is the target Data Foundation experience.
