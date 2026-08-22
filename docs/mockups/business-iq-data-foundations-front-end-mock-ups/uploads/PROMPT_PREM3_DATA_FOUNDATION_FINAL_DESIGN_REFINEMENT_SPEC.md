# PREM3 DATA FOUNDATION — FINAL DESIGN REFINEMENT SPEC / PROMPT
## Discovery, Data Engineering Assessment, Guided Provisioning, Governance, Continuous Health & Pre-Modeling Handoff

**Status:** Canonical design / mock-up handoff  
**Audience:** Product design, UX, prototype/mock-up team  
**Stage:** Data Foundation  
**Upstream:** Business IQ / `BUSINESS_CONTEXT_READY`  
**Source-level gate:** `IMPORT_READY`  
**Environment-level gate:** `DATA_FOUNDATION_READY`  
**Downstream:** Pre-Modeling  
**Canonical BigQuery dataset:** `prem3_modeling`  
**Canonical Google Drive root:** `prem3-modeling/`  
**Version:** `data-foundation/design-final-v1.0`  
**Date:** 2026-08-22  

---

# 1. Purpose

Design the PreM3 **Data Foundation** experience as the durable evidence, data-engineering, provisioning, and governance layer that follows Business IQ.

This should **not** feel like:

- a connector catalog;
- a cloud-admin console;
- a long technical wizard;
- a generic data upload screen;
- a questionnaire asking the user things PreM3 can discover itself.

It should feel like:

> **PreM3 already knows what evidence should matter from Business IQ. It connects to the customer-approved data environment, discovers what exists, determines what each source probably is, tests whether the data is structurally trustworthy, explains the problems that matter, asks only about ambiguous business meaning, previews the exact cleanup/infrastructure plan, executes only approved actions, and proves the resulting foundation is healthy.**

The customer should leave Data Foundation with:

> **A governed, monitored BigQuery measurement foundation whose source identity, lineage, data quality, refresh behavior, schemas, transformations, and unresolved limitations are known.**

---

# 2. Why this stage matters

Data Foundation powers the rest of PreM3.

Its outputs should later support:

- Meridian / MMM;
- forecasting;
- attribution / MTA;
- incrementality / experiments;
- scenario planning;
- Monte Carlo;
- recommendations;
- portfolio optimization;
- decision tracking;
- outcome measurement;
- customer-local MEL.

Therefore:

> **Do not design Data Foundation exclusively around Meridian inputs.**

It creates reusable, governed evidence first.

---

# 3. Product sequence

```text
BUSINESS IQ
What the business means
        ↓
BUSINESS_CONTEXT_READY
        ↓
DATA FOUNDATION
Discover + assess + resolve + provision + validate + govern
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
Planning + readiness + EDA + remediation + model design
        ↓
MODEL_READY
        ↓
MODELING
        ↓
OPTIMIZATION
```

Canonical distinction:

> **Business IQ establishes meaning.  
> Data Foundation establishes trustworthy evidence.  
> Pre-Modeling decides whether that evidence can support the intended model.**

---

# 4. Production workflow — remove the visible “Scenarios” block

The current prototype includes a top-level **Scenario** switcher such as:

- Mature BigQuery
- Mixed environment
- No PreM3 dataset
- New channel
- Business/data contradiction
- Revoked authorization

These are useful for:

- prototype review;
- demo fixtures;
- QA;
- frontend fixture states later;
- integration testing.

They should **not appear in the production workflow**.

The customer should never have to decide:

> “Which scenario am I?”

PreM3 should infer it.

Example:

```text
Customer connects authorized environments
        ↓
PreM3 discovers:
• Google Ads in BigQuery
• Meta via Fivetran
• CTV files in Drive
• no prem3_modeling dataset
        ↓
System automatically follows the appropriate mixed-environment path
```

Keep scenario states behind the scenes as prototype/development fixtures only.

---

# 5. Replace the long-screen mental model with five macro phases

Production Data Foundation should use five stable conceptual phases:

```text
1. CONNECT
2. DISCOVER & ASSESS
3. RESOLVE & PLAN
4. BUILD & VERIFY
5. OPERATE
```

## 1 — CONNECT

- BigQuery;
- Google Drive;
- customer GCP project selection;
- discovery permissions.

## 2 — DISCOVER & ASSESS

- inherited Business IQ evidence requirements;
- provider/source discovery;
- provider registry;
- metadata;
- lineage;
- source profiling;
- data quality;
- cross-source alignment.

## 3 — RESOLVE & PLAN

Only items needing a decision:

- ambiguous source binding;
- missing evidence;
- provider prerequisite;
- data-quality semantic ambiguity;
- business/data contradiction;
- cleanup recommendations;
- Foundation Plan.

## 4 — BUILD & VERIFY

- permissions;
- approval;
- deterministic provisioning;
- staging/canonical transformations;
- first-load QA;
- quality validation;
- receipts;
- `DATA_FOUNDATION_READY`.

## 5 — OPERATE

- freshness;
- quality drift;
- schema drift;
- authorization health;
- source replacement;
- new channels;
- ongoing evidence coverage;
- Pre-Modeling handoff.

---

# 6. Reuse the established PreM3 product shell

Carry forward the Business IQ interaction language.

Recommended persistent application structure:

```text
┌───────────────────────────┬────────────────────────────────────────┐
│ FOUNDATION                │                                        │
│ ✓ Business Intelligence   │ Data Foundation                        │
│ ● Data Foundation         │ Current workspace                      │
│                           │                                        │
│ MEASUREMENT               │ Main working surface                   │
│   Pre-Modeling    LOCKED  │                                        │
│   Modeling        LOCKED  │ Source cards / quality / plan / QA     │
│                           │                                        │
│ DATA FOUNDATION           │                                        │
│   Overview                │ Contextual guidance                    │
│   Sources                 │                                        │
│   Quality                 │ Primary actions                        │
│   Foundation Plan         │                                        │
│   Health & operations     │                                        │
└───────────────────────────┴────────────────────────────────────────┘
```

Optional `Review` section can appear during initial setup.

Do **not** expose every backend state as a navigation item.

---

# 7. First screen — connect the data environment

BigQuery and Google Drive should be presented together on the first Data Foundation screen.

Heading:

> # Connect your data environment

Supporting copy:

> PreM3 uses BigQuery for governed measurement data and Google Drive for approved file-based data and evidence. Connect the environments you want PreM3 to inspect. PreM3 only reads the scopes and locations you authorize.

---

## 7.1 BigQuery card

### Purpose

> **BigQuery**  
> Discover existing datasets, tables, views, transfers, scheduled queries, lineage, and source health. PreM3 ultimately builds the governed measurement foundation here.

Possible states:

```text
Not connected
Discovery access granted
Foundation-management access granted
Needs reauthorization
```

CTA:

> `Connect BigQuery`

or:

> `Review BigQuery access`

---

## 7.2 Google Drive card

### Purpose

> **Google Drive**  
> Give PreM3 one controlled repository for CSVs, spreadsheets, historical exports, experiment readouts, prior MMMs, promotion calendars, and other file-based evidence.

Possible states:

```text
Not connected
Connected · prem3-modeling found
Connected · folder setup needed
Needs reauthorization
```

CTA:

> `Connect Google Drive`

---

## 7.3 Connection requirements

BigQuery is required before `DATA_FOUNDATION_READY`.

Google Drive is optional if the customer has no file-based evidence.

The user may connect either first.

Once the necessary environments are authorized:

> `Start discovery`

---

# 8. Authentication vs data authorization

Make this distinction explicit:

```text
Signed into PreM3
≠
Authorized PreM3 to inspect BigQuery / Google Drive
```

Use concise explanatory copy.

Do not make users leave the workflow to discover they need data authorization.

Inline connection/reconnection should return them to the same Data Foundation state.

---

# 9. Separate discovery permission from build permission

This is a core enterprise trust pattern.

---

## 9.1 Discovery access

Requested first.

Used only for approved discovery activities such as:

- list accessible projects/datasets;
- read metadata;
- schemas;
- partitions;
- views;
- routines;
- transfer configuration;
- scheduled-query/job history;
- authorized Drive root;
- bounded profiling of shortlisted sources.

Copy:

> **Discovery access lets PreM3 investigate the measurement environment. It does not let PreM3 create or change foundation resources.**

---

## 9.2 Foundation-management access

Requested only after the customer approves a Foundation Plan requiring mutation.

May include:

- create dataset;
- create tables/views;
- create routines/UDFs;
- create scheduled queries;
- create approved transfers;
- create ingestion jobs;
- create monitoring;
- narrowly scoped IAM where supported.

Copy:

> **PreM3 requests build permissions only after you approve the exact Foundation Plan.**

Long-running ingestion should use an authorized non-human runtime identity rather than depending on the individual user session.

---

# 10. BigQuery project selection

Heading:

> **Choose the Google Cloud project PreM3 should inspect**

The user is choosing the **customer-owned authority scope**, not asking PreM3 to create a GCP project.

Example project card:

```text
acme-analytics

Location
US

Datasets
9

Tables & views
412

Likely measurement sources
6

Current access
Discovery ready
```

Action:

> `Use this project`

Possible alternative:

> `Use for discovery only`

if the customer has read but not build permissions.

---

# 11. No GCP project creation

Make this explicit.

PreM3 does **not** create customer Google Cloud projects as part of standard Data Foundation onboarding.

If the authorized project does not yet contain a PreM3 dataset, the later Foundation Plan proposes:

```text
CREATE
acme-analytics.prem3_modeling
```

PreM3 creates:

- datasets;
- tables;
- views;
- UDFs/routines;
- scheduled queries;
- transfer configurations;
- data contracts;
- monitoring;

inside an approved customer project.

---

# 12. Google Drive as a controlled evidence repository

Drive should not be treated as a later fallback page.

It is a first-class **file intake plane**.

BigQuery and Drive have distinct roles:

```text
GOOGLE DRIVE
Controlled raw/file evidence

        ↓

PREM3 DATA ENGINEERING ASSESSMENT

        ↓

BIGQUERY
Governed analytical foundation
```

Do not create two competing systems of record.

---

# 13. Canonical Drive root

Preferred root:

```text
prem3-modeling/
```

PreM3 should inspect only this authorized root for file-based Data Foundation discovery.

Copy:

> **PreM3 only looks inside the `prem3-modeling` folder for file-based measurement data and evidence.**

Benefits:

- predictable discovery;
- lower privacy surface;
- easier agency/customer instructions;
- durable file conventions;
- stable provenance.

---

# 14. Drive root setup

After Drive authorization:

```text
Looking for
prem3-modeling/
```

## If found

```text
✓ prem3-modeling found
27 files
6 recognized source folders
```

## If missing

Offer:

> **Create the PreM3 folder structure**

Actions:

- `Create with PreM3`
- `I’ll create it myself`

If manually created:

```text
prem3-modeling
```

must be the preferred canonical root.

---

# 15. Canonical Drive structure

Recommended:

```text
prem3-modeling/
│
├── sources/
│   ├── google_ads/
│   ├── meta_ads/
│   ├── microsoft_ads/
│   ├── dv360/
│   ├── trade_desk/
│   ├── spotify_ads/
│   ├── shopify/
│   ├── salesforce/
│   └── custom/
│
├── business_data/
│   ├── promotions/
│   ├── pricing/
│   ├── inventory/
│   ├── distribution/
│   ├── sales_activity/
│   └── external_controls/
│
├── evidence/
│   ├── experiments/
│   ├── prior_mmm/
│   ├── lift_studies/
│   ├── attribution/
│   └── benchmarks/
│
├── exports/
│
├── reports/
│
└── system/
    ├── manifests/
    ├── receipts/
    └── archive/
```

User-facing onboarding may simplify this to:

```text
prem3-modeling/
├── sources/
├── business_data/
├── evidence/
└── exports/
```

PreM3 may manage system folders behind the scenes.

---

# 16. Explicit provider slugs

Use:

```text
meta_ads/
google_ads/
spotify_ads/
```

Do not use:

```text
meta/
```

because it can be confused with metadata.

Do not use:

```text
other/
```

Custom source example:

```text
sources/custom/regional_tv_agency/
```

---

# 17. Per-provider Drive structure

Internally:

```text
sources/
└── meta_ads/
    ├── incoming/
    ├── processed/
    ├── rejected/
    └── archive/
```

The customer generally needs to know only:

```text
sources/meta_ads/incoming/
```

PreM3 manages lifecycle folders automatically where authorized.

---

# 18. File naming convention

Preferred canonical logical filename:

```text
<source_slug>__<data_role>__<grain>__<start_date>__<end_date>__v<version>.<ext>
```

Examples:

```text
meta_ads__campaign_delivery__daily__2026-01-01__2026-03-31__v01.csv

google_ads__campaign_performance__daily__2025-01-01__2025-12-31__v02.csv

spotify_ads__campaign_delivery__weekly__2026-01-01__2026-06-30__v01.csv

promotions__calendar__daily__2025-01-01__2026-12-31__v03.csv
```

Rules:

- lowercase;
- snake_case;
- ISO dates;
- explicit version;
- no spaces in canonical name;
- no ambiguous `final`, `new`, `latest`.

---

# 19. Do not burden users with destructive renaming

If a customer drops:

```text
Meta Export FINAL June.csv
```

PreM3 should preserve the original file and register:

```text
Original
Meta Export FINAL June.csv

Canonical identity
meta_ads__campaign_delivery__daily__2026-06-01__2026-06-30__v01.csv
```

Preserve:

- original filename;
- fingerprint;
- location;
- canonical registration;
- ingestion timestamp.

Strict conventions should create automation, not clerical work.

---

# 20. Business IQ → Data Foundation handoff

Do not re-ask Business IQ.

Inherit:

- KPI / business outcome;
- measurement objective;
- markets / geography;
- marketing channels;
- channel roles;
- customer journey;
- budget decision process;
- promotions;
- seasonality;
- pricing;
- inventory;
- competition;
- business events;
- prior evidence availability;
- acknowledged unknowns.

Show this explicitly.

Heading:

> **What PreM3 will look for**

Example:

```text
✓ Revenue / transactions
✓ Paid Search
✓ Paid Social
✓ Connected TV
✓ Promotions
✓ Seasonal demand
? Inventory constraints
? Competitive demand
✓ Prior experiment evidence
```

CTA:

> `Start discovery`

---

# 21. Evidence requirements

Each Business IQ concept should become an evidence requirement.

Example:

```text
Paid Search

Business role
Media · demand capture

Needed by
MMM · attribution

Why PreM3 expects it
Business IQ says Paid Search is material.

Evidence
Searching...
```

Another:

```text
Inventory constraints

Business role
Potential control / operational driver

Why PreM3 expects it
Business IQ says inventory can reduce marketing activity.

Evidence
Not found
```

The design should make the Business IQ → evidence relationship obvious.

---

# 22. Discovery should search both authorized planes

```text
BUSINESS IQ REQUIREMENT
Paid Social
        ↓
PREM3 DISCOVERY
        ├── BigQuery
        └── Google Drive / prem3-modeling
```

Later provider integrations may add additional discovery planes.

Do not make the user independently inventory BigQuery and Drive.

---

# 23. Metadata-first BigQuery discovery

Discovery sequence:

```text
1. List approved datasets
2. Read tables/views
3. Read schemas
4. Read partitions
5. Match provider registry signatures
6. Read transfer configuration
7. Inspect relevant job lineage
8. Shortlist candidate sources
9. Run bounded row-level profiling only on shortlisted sources
```

Show proof:

```text
412 objects inspected through metadata
6 sources shortlisted
6 bounded profiling queries
```

This is valuable security/cost context.

---

# 24. Provider registry as an active discovery engine

The registry may supply:

- provider names;
- channel/provider mappings;
- export options;
- native transfer availability;
- schema fingerprints;
- expected fields;
- metric meanings;
- typical time fields;
- expected grain;
- geo capability;
- refresh behavior;
- history/backfill limits;
- provider quirks;
- authenticated provisioning support.

Example:

```text
Why PreM3 thinks this is Google Ads

✓ Native BigQuery transfer identifies Google Ads
✓ Registry schema matched 14 of 16 expected fields
✓ Spend field detected
✓ Impression field detected
✓ Click field detected
✓ History aligns with Paid Search activity
```

---

# 25. Discovery result authority

Keep two concepts separate.

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

Do not collapse these into one generic confidence badge.

---

# 26. Do not make users confirm deterministic facts

If identity is objectively established from:

- native transfer metadata;
- provider account identity;
- deterministic registry contract;

show:

```text
VERIFIED SOURCE
```

Action:

> `Review`

not:

> `Confirm source`

Reserve confirmation for actual semantic uncertainty.

---

# 27. Group discovery results

Recommended groups:

## Verified sources

Strong deterministic identity.

## Likely matches

Strong evidence; business meaning needs confirmation.

## Needs your decision

Ambiguous candidate or semantic uncertainty.

## Excluded

Collapsed list of clearly irrelevant objects.

---

# 28. Source Coverage Inventory

The core Data Foundation workspace should be a **Source Coverage Inventory**, not a connector grid.

Each source resolves:

```text
Business concept
Provider
Current source location
Source object/path
History
Cadence
Freshness
Geo
Metrics
Operational health
Data quality
Import readiness
Recommended action
```

---

# 29. Source-card collapsed state

Example healthy source:

```text
GOOGLE ADS · PAID SEARCH
VERIFIED

Coverage
43 months · DMA

Operations
Current · updated 8h ago

Data quality
18 passed · 0 issues

Import readiness
Ready
```

Example issue state:

```text
META ADS · PAID SOCIAL
LIKELY MATCH

Coverage
31 months · National

Operations
Current · updated 14h ago

Data quality
16 passed · 2 review

Import readiness
Needs review
```

Primary action:

> `Review source`

---

# 30. Source detail structure

Recommended detail tabs/sections:

```text
OVERVIEW
QUALITY
COVERAGE
LINEAGE
TRANSFORMATION
```

or a comparable stacked structure.

---

# 31. Data Foundation becomes a data-engineering assessment

Every accepted source receives four assessment pillars:

```text
SOURCE ASSESSMENT

1. Operational Health
2. Contract & Structure
3. Data Quality & Integrity
4. Measurement Coverage
```

---

# 32. Pillar 1 — Operational Health

Assess:

- current accessibility;
- authorization status;
- ingestion automation;
- expected cadence;
- observed cadence;
- most recent load;
- failures;
- late-arrival behavior;
- source owner;
- lineage visibility.

Example:

```text
Operational health

Access
Ready

Expected cadence
Daily

Observed cadence
23–27 hours

Last load
8 hours ago

Failed refreshes
0 in last 30 days

Lineage
Verified native transfer
```

---

# 33. Pillar 2 — Contract & Structure

Assess:

- required fields;
- unexpected/missing fields;
- types;
- parseability;
- expected source grain;
- observed grain;
- unique/natural keys;
- partitioning;
- time field;
- geo fields;
- currency/unit fields;
- registry schema fingerprint.

Example:

```text
Contract & structure

Provider contract
google_ads/2026.08

Required fields
16 / 16

Observed grain
Day × campaign

Expected grain
Day × campaign

Type conflicts
0

Time field
segments_date

Currency
USD
```

---

# 34. Pillar 3 — Data Quality & Integrity

This is a first-class Data Foundation capability.

Run deterministic source tests.

Do **not** replace these with an opaque numeric quality score.

---

# 35. Quality test family — uniqueness

Test:

- exact duplicated rows;
- duplicate natural keys;
- duplicate grain keys;
- reissued connector loads;
- cross-file overlap;
- unexpected row multiplication.

Example:

```text
Exact duplicates
4,812 rows
0.38%

Duplicate date × campaign keys
63
```

---

# 36. Quality test family — completeness

Test:

- required nulls;
- blank values;
- empty strings;
- null keys;
- entirely empty columns;
- unexpected zero-heavy fields;
- missing intervals/partitions.

Example:

```text
campaign_id blank
0%

region blank
31.2%

spend null
0%
```

Do not assume blank means missing in every provider.

Use contracts and semantics.

---

# 37. Quality test family — type & parse consistency

Detect:

- mixed date formats;
- malformed dates;
- numeric values stored as strings;
- percentages as text;
- inconsistent decimal formatting;
- boolean variants;
- encoding problems;
- locale-specific values.

Example:

```text
promotion_depth

Numeric percentages
176 rows

Free text
38 rows

Unparseable
6 rows
```

---

# 38. Quality test family — formatting consistency

Detect:

- whitespace;
- casing;
- inconsistent category labels;
- inconsistent delimiters;
- ID formatting;
- naming variation.

Example:

```text
campaign_type

Prospecting
1,402

prospecting
284

" Prospecting "
17
```

PreM3 can recommend normalization while preserving original values in lineage.

---

# 39. Quality test family — numeric/domain validity

Provider/contract-aware rules may include:

- negative spend;
- negative impressions;
- impossible percentages;
- NaN / infinity;
- currency missing;
- invalid dates;
- future delivery;
- invalid geo codes;
- metric relationship violations where provider semantics support the rule.

Avoid universal assumptions across providers.

---

# 40. Quality test family — temporal integrity

Test:

- missing dates;
- missing periods;
- overlapping periods;
- duplicate partitions;
- future dates;
- late-arriving rows;
- historical reissues;
- discontinuities;
- source pauses;
- stale intervals.

Crucial distinction:

```text
UNKNOWN / MISSING
≠
ZERO
```

---

# 41. Quality test family — referential integrity

Where meaningful:

- campaign → account;
- line item → campaign;
- creative → advertiser;
- geo ID → geo mapping;
- order item → order;
- store → region.

---

# 42. Quality test family — reconciliation

Where control totals exist:

- source vs provider dashboard;
- imported file vs BigQuery staging;
- source spend vs canonical spend;
- source revenue vs finance totals;
- pre/post transform row count;
- pre/post transform amount totals.

---

# 43. Quality test family — drift

Persist historical observations.

Detect:

- schema drift;
- type drift;
- null-rate drift;
- row-volume collapse;
- cardinality shifts;
- new/removed category values;
- unit/currency change;
- freshness degradation;
- geo coverage changes.

---

# 44. Quality summary UX

Avoid:

```text
Quality score: 87
```

Prefer:

```text
DATA QUALITY
Needs attention

18 checks passed
2 review items
1 blocker
```

Overall state:

```text
HEALTHY
NEEDS REVIEW
BLOCKED
UNVERIFIED
```

The findings remain authoritative.

---

# 45. Example detailed quality finding

```text
Duplicate date × campaign keys

Affected
63 keys · 126 rows

Observed evidence
Rows share the same campaign/date but have different
connector sync timestamps.

PreM3 interpretation
These appear to be connector reissues rather than
separate media delivery rows.

Recommended action
Keep the newest synchronized row per verified business key in staging.

Authority
AUTO_SAFE after connector reissue semantics are verified.

Why this matters
Keeping both rows would double-count Paid Social spend.

[ View examples ]
[ Run verification check ]
```

---

# 46. Deterministic + agentic architecture should be visible in the UX

```text
DETERMINISTIC TEST
        ↓
STRUCTURED FINDING
        ↓
AGENT INTERPRETATION
        ↓
RECOMMENDATION
        ↓
AUTHORITY
        ↓
PREVIEW / HUMAN DECISION IF NEEDED
        ↓
DETERMINISTIC TRANSFORM
        ↓
POST-TRANSFORM VALIDATION
        ↓
RECEIPT
```

---

# 47. Deterministic system owns

- row/field counts;
- duplicate detection;
- null checks;
- schema;
- key integrity;
- type checks;
- partition/freshness;
- lineage;
- reconciliation;
- transform execution;
- validation;
- readiness gates.

---

# 48. Agent owns

- explanation;
- bounded root-cause hypotheses;
- provider-aware interpretation;
- prioritization;
- recommendation;
- identifying the business question required to resolve ambiguity;
- explaining downstream measurement consequences.

---

# 49. Agent guardrails

The agent does not:

- invent passed tests;
- write arbitrary unapproved SQL;
- overwrite customer raw sources;
- infer missing media as zero without proof;
- override deterministic blockers;
- fabricate geography;
- choose destructive aggregation simply to make modeling easier.

---

# 50. “Ask the business question, not the transform question”

Signature interaction.

Example:

Deterministic finding:

```text
11 promotion periods overlap.
```

Do not ask:

> “Should PreM3 sum the discount depth or take the deepest discount?”

Ask:

> **Can multiple promotions apply to the same customer/order at the same time?**

Answers:

- Yes
- No
- Only certain promotion types
- Not sure

Then PreM3 recommends a transformation based on the business rule.

---

# 51. Evidence-triggered Business IQ clarification

Keep as a signature cross-layer interaction.

Example:

```text
Data Foundation observed
Paid Social has no delivery Apr 1–May 15.

Business IQ says
Paid Social is always-on.
Inventory can reduce marketing.

Question
Was Paid Social intentionally paused during this period?

[ Yes ]
[ No ]
[ Not sure ]
```

If Yes:

> Business Profile update proposed

If No:

> Data-quality investigation created

If Not sure:

> Period remains explicitly ambiguous

Every answer produces state/provenance, not just chat text.

---

# 52. Google Drive file discovery

Drive discovery should not present every file as an independent object.

PreM3 should group files into **logical source series**.

Example:

```text
I found 12 files that appear to be monthly Meta Ads exports.

Logical source
Meta Ads · Paid Social

Coverage
Jan–Dec 2025

Files
12

Schema versions
2

Missing months
0

Cross-file overlap
2 days
```

---

# 53. Drive file quality tests

Drive-based sources receive the same assessment as BigQuery sources.

Also test:

- extension;
- delimiter;
- encoding;
- sheet names;
- header consistency;
- repeated header rows;
- blank rows;
- formula cells;
- file naming pattern;
- duplicate file fingerprints;
- schema consistency across exports;
- missing expected files;
- overlapping file ranges.

---

# 54. Example Drive source

```text
META ADS · PAID SOCIAL

Location
Google Drive

Path
prem3-modeling/sources/meta_ads/incoming/

Files
12 monthly CSVs

Coverage
Jan–Dec 2025

Operations
Manual · last file 11 days ago

Data quality
Needs review
• 2 schema versions
• 418 overlapping duplicate rows

Import readiness
Not ready
```

---

# 55. Unclassified Drive file review

If a file is misplaced or at root:

```text
UNCLASSIFIED FILE

May spend final.xlsx

PreM3 thinks
Meta Ads · Paid Social

Evidence
Provider-like fields
Date range
Spend + impressions

Recommended source
sources/meta_ads/incoming/

[ Accept & register ]
[ Choose another source ]
[ Ignore ]
```

Do not force broad Drive crawling.

---

# 56. BigQuery + Drive convergence

Examples:

## Drive history + BQ current source

```text
BigQuery
Meta begins Jan 2026

Drive
Meta CSVs Jan 2024–Dec 2025
```

PreM3:

> Use Drive as governed historical backfill and BigQuery as ongoing source.

## Drive feeds BigQuery

If lineage proves the BQ table is already generated from Drive:

> Treat BigQuery as canonical and Drive as retained raw-file evidence.

No parallel truths.

---

# 57. Cross-source alignment

Keep this as a core Data Foundation assessment.

Evaluate:

- common temporal overlap;
- time zones;
- currencies;
- geo compatibility;
- source grain;
- KPI/media window;
- channel coverage;
- duplicate source overlap;
- treatment/media overlap;
- unit compatibility.

Example:

```text
Cross-source alignment

Longest media history
43 months

Shortest material media history
11 months

KPI history
42 months

Common window
11 months

Geo
KPI            DMA
Paid Search    DMA
Paid Social    National

Status
REVIEW NEEDED
```

---

# 58. Current vs projected alignment

Before Foundation Build:

```text
CURRENT
Time zones       2 standards
Currency         2 representations
Duplicate risk   DV360 raw + rollup
```

Projected:

```text
AFTER PLAN
Reporting zone   America/New_York
Currency         USD
Canonical DV360  raw daily only
```

Label clearly:

> **Projected after approved plan**

After execution:

> **Verified result**

---

# 59. Coverage gaps vs quality findings

Keep these separate.

## Coverage Gap

Evidence missing or insufficient.

Examples:

- no inventory data;
- no competition signal;
- short video history.

## Quality Finding

Evidence exists but structure is unreliable.

Examples:

- duplicates;
- malformed values;
- null keys;
- missing periods;
- drift.

Present together in:

> **Issues & Actions**

Filters:

```text
Coverage
Quality
Operations
Business meaning
```

---

# 60. Consequence classes

Use:

```text
FOUNDATION_BLOCKER
SOURCE_BLOCKER
PREMODEL_BLOCKER
PREMODEL_REVIEW
ADVISORY
```

Examples:

```text
Duplicate Paid Social business keys
SOURCE_BLOCKER
```

because canonical spend could double-count.

```text
Paid Social national-only
PREMODEL_REVIEW
```

because source may enter the foundation but affects model design.

---

# 61. Source acquisition paths

Every unresolved source routes to one of four paths.

## Existing source

> Discover and validate.

## Supported automation

> Set up with PreM3.

## Manual prerequisite/export

> Generate exact prerequisite/export plan.

## No evidence

> Create a collection plan.

This should be visible as an action recommendation, not a complex decision tree the customer must understand.

---

# 62. Platform-only provider path

Example:

```text
Programmatic Display
Display & Video 360

Location
Platform only

Registry capability
Prerequisite then automate

Prerequisite
DTV2 delivery bucket

Status
ACTION NEEDED
```

Action:

> `Set up with PreM3`

---

# 63. “PreM3 can” vs “You need to”

Every prerequisite screen should show ownership.

Example:

```text
PreM3 can

✓ create BigQuery transfer after DTV2 exists
✓ scope it to approved advertiser
✓ validate first sync
✓ create source interfaces
✓ monitor freshness and schema

You need to

• request DTV2 from DV360 support/agency
• provide approved bucket
```

CTA:

> `Generate prerequisite request`

---

# 64. Data Quality Overview — add as a high-value core screen

Heading:

> # Data Quality Overview

Example:

```text
6 sources assessed

128 checks passed
5 review items
2 blockers

By category

Uniqueness            1 blocker
Completeness          Healthy
Types & formatting    2 review
Temporal integrity    1 blocker
Reconciliation        Healthy
Schema                 1 review
```

Source summary:

```text
Google Ads      Healthy
Meta Ads        Blocked · duplicates
Shopify         Healthy
Braze           Review · T+2 watermark
DV360           Review · short history
Promotions      Review · formatting / overlaps
```

---

# 65. Data Intelligence Brief

Add a curated agentic summary after discovery/assessment.

Heading:

> # PreM3 Data Intelligence Brief

Suggested sections:

## What PreM3 found

- 6 of 8 expected sources exist.
- 4 have automated ingestion.
- 2 are customer-managed.
- 1 source exists only in Drive.
- 1 material channel has no source.

## Data-quality findings

- Meta contains duplicate business keys.
- Promotion depth uses mixed formats.
- Video rollup overlaps raw DV360.
- Braze is T+2 by design and should not be treated as stale.

## PreM3 can mend

- dedupe verified reissued rows;
- normalize deterministic types;
- convert provider-specific cost units;
- normalize blanks/nulls;
- create stable source-interface views;
- register late-arrival watermarks.

## Needs your decision

- was the six-week Paid Social gap intentional?
- can promotions stack?

## Carries into Pre-Modeling

- national-vs-DMA mismatch;
- short video history;
- unavailable competition data.

Every line must trace to structured findings.

---

# 66. Learning philosophy

Carry forward from Business IQ:

> **Teach through consequence, not curriculum.**

Examples:

### Duplicate keys

> If the same campaign/day appears twice, spend may be double counted before a model ever sees it.

### Missing vs zero

> Zero means no delivery occurred. Missing means PreM3 does not know. Treating one as the other can materially change measurement.

### Geography

> Geo variation only helps when outcomes and media are available at compatible geographic levels.

### Grain

> PreM3 can safely aggregate detail. It cannot recreate detail that the source already lost.

### Lineage

> Lineage lets PreM3 prove where a modeled value came from and identify upstream changes.

Keep explanations one or two sentences with optional `Learn why`.

---

# 67. Transformation Preview — make this a signature Data Foundation interaction

Before any cleanup/canonicalization:

```text
SOURCE

marketing.meta_ads_campaign_daily

1,244,391 rows
4,812 exact duplicates
63 duplicate business keys
6-week unresolved gap

        ↓

PROPOSED STAGING TRANSFORM

✓ preserve source untouched
✓ keep newest verified connector revision per key
✓ cast spend to NUMERIC
✓ normalize blanks → NULL
✓ normalize timezone metadata
! preserve six-week gap as UNKNOWN
  pending business clarification

        ↓

EXPECTED STAGING RESULT

1,239,516 rows
0 duplicate grain keys
required types valid
gap remains explicit
```

Primary action may be:

> `Review cleanup plan`

or the transform becomes part of the consolidated Foundation Plan.

---

# 68. Raw source immutability

Reusable trust statement:

> **Your source data stays untouched.**

Visual:

```text
CUSTOMER RAW SOURCE
read-only / immutable
        ↓
PREM3 STAGING
versioned transformations
        ↓
CANONICAL FOUNDATION
governed evidence
```

Show this on:

- Transformation Preview;
- Foundation Plan;
- receipts.

---

# 69. Transformation authority

Every cleanup action is classified:

```text
AUTO_SAFE
APPROVAL_REQUIRED
USER_REQUIRED
NOT_RECOMMENDED
```

---

# 70. AUTO_SAFE examples

- trim deterministic whitespace;
- exact safe type conversion;
- convert Google Ads micros using provider contract;
- remove exact duplicate connector reissues after deterministic proof;
- normalize known provider field names;
- map known null/blank representation;
- register provider late-arrival watermark.

---

# 71. APPROVAL_REQUIRED examples

- choose among plausible dedupe keys;
- apply currency conversion policy;
- use historical aggregate for backfill;
- reduce granularity;
- materially alter refresh behavior;
- transform data in a way that may lose detail.

---

# 72. USER_REQUIRED examples

- intentional media pause vs collection failure;
- ambiguous source role;
- overlapping promotion business rule;
- unclear market/geo semantics;
- whether two reports describe the same underlying source.

---

# 73. NOT_RECOMMENDED examples

- fill unknown media periods with zero;
- invent geography;
- disaggregate weekly source to fabricated daily values;
- overwrite raw source;
- discard valid variation to simplify modeling.

---

# 74. High-value Transformation Review screen

Heading:

> # PreM3 proposes 9 cleanup actions

Example:

```text
7 auto-safe
1 approval-required
1 needs your decision

AUTO-SAFE
✓ Normalize Google Ads cost units
✓ Deduplicate verified Meta reissues
✓ Normalize blank/null representation
✓ Parse promotion dates
...

APPROVAL REQUIRED
Video historical backfill from weekly rollup

YOUR DECISION
How do overlapping promotions work?
```

CTA:

> `Review Foundation Plan`

---

# 75. Foundation Provisioning Plan

This is one of the most important screens.

Heading:

> # Review your Data Foundation Plan

Supporting copy:

> PreM3 compiled this plan from your Business IQ, the discovered environment, provider registry capabilities, source assessments, and current permissions. Nothing below will change until you approve the plan.

---

# 76. Five plan domains

Use:

```text
1. Infrastructure
2. Sources & transfers
3. Quality & transformations
4. Canonical measurement assets
5. Governance & observability
```

---

# 77. Infrastructure examples

- create `prem3_modeling`;
- dataset location;
- labels/descriptions;
- landing structures;
- approved APIs;
- narrow service permissions.

---

# 78. Sources & transfers examples

- reuse native Google Ads transfer;
- create DV360 transfer;
- import approved Drive source;
- schedule recurring file materialization;
- leave Fivetran Meta pipeline customer-managed;
- backfill approved history.

---

# 79. Quality & transformations examples

```text
AUTO_SAFE
Meta Ads
Remove verified connector reissues

AUTO_SAFE
Google Ads
Convert micros → currency

AUTO_SAFE
Promotions
Normalize deterministic date/format types

USER_REQUIRED
Promotions
Define overlap/stacking rule

APPROVAL_REQUIRED
Video
Use weekly historical rollup before raw history begins
```

---

# 80. Canonical measurement assets examples

- source-interface views;
- staging contracts;
- canonical media;
- canonical KPI;
- controls;
- treatments;
- geo/population;
- evidence tables;
- MMM input views;
- forecasting input views where useful;
- stable current views.

---

# 81. Governance & observability examples

- source registry;
- source assessments;
- schema fingerprints;
- freshness monitoring;
- continuity monitoring;
- quality drift;
- transfer monitoring;
- lineage;
- reconciliation;
- approval receipts;
- transform receipts.

---

# 82. Plan resource action classes

Every item shows:

```text
REUSE
CREATE
CHANGE
CUSTOMER-MANAGED
```

Example:

```text
prem3_modeling dataset          CREATE
Google Ads transfer             REUSE
Meta Fivetran pipeline          CUSTOMER-MANAGED
canonical_media                 CREATE
DV360 schedule                  CREATE
Promotion loader                CREATE
```

---

# 83. “PreM3 will not modify” section

Before approval show:

> **PreM3 will not modify**

Examples:

- existing customer source tables;
- advertising campaigns;
- bids;
- budgets;
- targeting;
- unrelated Drive content;
- unrelated BigQuery datasets;
- customer-managed ETL;
- provider billing/commercial settings.

---

# 84. Permission preview

Before approval:

```text
Permissions required

BigQuery
✓ Create prem3_modeling
✓ Create tables/views
✓ Run jobs
✓ Create scheduled queries

Data Transfer
✓ Create approved transfer configuration

Google Drive
✓ Read prem3-modeling
✓ Create/manage approved PreM3 folder paths if authorized

Not requested
— Campaign management
— Provider billing administration
— Unrelated Drive folders
— Unrelated BigQuery datasets
```

Explain each permission in plain language.

---

# 85. Approval binding

Approval applies to an exact immutable plan version.

If PreM3 changes materially:

- destination;
- account scope;
- permissions;
- schedule;
- backfill;
- cost;
- resource creation;
- transformation behavior;

show:

> **Updated plan — review required**

Do not reuse previous consent silently.

---

# 86. Partial approvals

Support independent approval groups only when dependencies permit.

Example:

```text
[✓] Infrastructure
[✓] Google-native ingestion
[ ] Drive file ingestion
[✓] Governance controls
```

If invalid:

> **This partial approval cannot be executed because canonical assets require the BigQuery infrastructure above.**

---

# 87. Build & provisioning progress

Example:

```text
Building Data Foundation

✓ prem3_modeling ready
✓ source registry created
✓ source-interface views created
✓ Google Ads source verified
✓ Meta cleanup applied
◌ Drive promotion import running
○ Governance checks
○ Canonical QA
```

Use distinct states for:

- running;
- waiting for provider;
- customer action required;
- failed;
- completed.

---

# 88. First-load validation must have two layers

## Source validation

> Did the expected source arrive correctly?

Check:

- object exists;
- expected account scope;
- fields;
- time;
- currency;
- history;
- freshness;
- fingerprint;
- duplicate behavior.

## Canonical validation

> Did PreM3 transform the source correctly?

Check:

- expected output grain;
- unique business keys;
- no unexpected row loss;
- no duplicate canonical keys;
- missingness preserved;
- totals reconcile;
- units/currency correct;
- category mappings;
- full source→staging→canonical lineage.

---

# 89. Source-level `IMPORT_READY`

A source can be:

```text
CONNECTED
but
NOT IMPORT_READY
```

`IMPORT_READY` means:

> The source passed the governed import/source contract and can enter downstream canonical processing.

It does **not** mean:

> model-ready.

---

# 90. Environment-level `DATA_FOUNDATION_READY`

Requires:

- required BigQuery infrastructure exists;
- required source paths resolved;
- required sources import-ready or approved as non-blocking exceptions;
- canonical measurement assets exist;
- governance/observability active;
- source QA passed;
- canonical QA passed;
- unresolved issues are typed.

Display:

> **Data Foundation Ready is not Model Ready.**

---

# 91. Data Quality Receipt

Create a durable source-level receipt.

Example:

```text
DATA QUALITY RECEIPT

Source
Meta Ads

Assessment
quality/v1.0

Source rows
1,244,391

Findings
2 blockers
1 review item

Transforms applied
✓ remove verified connector reissues
✓ normalize null representation
✓ cast spend

Not resolved
! six-week gap remains explicit

Post-transform proof
✓ 0 duplicate grain keys
✓ spend parity 100.00%
✓ required fields complete
✓ source unchanged

Status
IMPORT_READY with PREMODEL_REVIEW
```

---

# 92. Drive Import Receipt

Example:

```text
DRIVE IMPORT RECEIPT

Source
Meta Ads historical exports

Path
prem3-modeling/sources/meta_ads/incoming/

Files evaluated
12

Accepted
12

Rejected
0

BQ destination
prem3_modeling.stg_meta_ads

Raw files modified
No

Status
Import ready
```

---

# 93. Foundation Provisioning Receipt

Example:

```text
FOUNDATION PROVISIONING RECEIPT

Plan
v4

Approved
Aug 22, 2026 · 10:37 AM

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

Left untouched
• Meta Fivetran
• source tables
• campaign settings

Remaining
• competitor evidence unavailable
• CTV history review
```

Receipt should feel like proof, not logs.

---

# 94. Before / after proof

This could be one of the strongest product moments.

Before execution label:

> **Projected after plan**

Example:

```text
BEFORE

Sources                 8
Automated               4
Quality blockers        3
Unknown gaps            2
Schema variants         5
Canonical lineage       Partial
Time zones              2

PROJECTED AFTER PLAN

Automated               6
Quality blockers        0
Unknown gaps            1
Schemas                  normalized in staging
Canonical lineage       complete
Reporting zone          America/New_York
```

After execution:

> **Verified result**

Never present projected improvement as actual before validation.

---

# 95. Data Foundation Ready screen

Example:

```text
DATA FOUNDATION READY

Your governed measurement environment is ready for Pre-Modeling.

BigQuery
acme-analytics.prem3_modeling

Sources
5 import-ready
1 import-ready with review
1 waiting on provider
1 unavailable

Data quality
142 deterministic checks passed
0 source blockers
3 Pre-Modeling review findings

Automation
5 automated
2 customer-managed

Governance
Freshness monitoring active
Schema drift monitoring active
Quality drift active
Lineage active
```

Then:

> **Next — Pre-Modeling**  
> Planning, readiness, EDA, remediation, and model design.

CTA:

> `Continue to Pre-Modeling`

---

# 96. Persistent Data Foundation dashboard

After onboarding, Data Foundation becomes an operating workspace.

Header:

```text
Data Foundation
Healthy

Last evaluated
2 hours ago
```

Summary:

```text
Sources             8
Healthy             6
Needs attention     1
Unavailable         1

Data quality
148 pass
2 review
0 blockers

Refresh
6 automated
2 customer-managed

Freshness
7 current
1 late

Coverage
11–43 months
```

---

# 97. Persistent source actions

Support:

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
- View quality
- View receipts

---

# 98. Ongoing quality drift

Example:

```text
META ADS
Quality changed

campaign_id null rate

Previously
0.0%

Now
8.2%

Started
Aug 20, 2026

Impact
SOURCE_BLOCKER
```

Agent:

> A schema change appeared on the same date the null rate increased. PreM3 recommends testing whether the customer-managed connector changed report shape.

Observation = deterministic.

Cause = hypothesis.

Action:

> `Run check`

---

# 99. Source authorization failure

Critical integrity rule:

If authorization fails or expected data stops arriving:

```text
UNKNOWN / MISSING
≠
ZERO
```

Never silently synthesize zero spend.

Example UI:

> **Paid Social data is missing for the last two expected periods. PreM3 has not interpreted those periods as zero spend.**

Source may lose `IMPORT_READY`.

Foundation status may degrade to:

> `Needs attention`

until repaired.

---

# 100. New channel / provider lifecycle

Business IQ may later add:

```text
Streaming Audio
Role: Demand creation / Brand building
```

Data Foundation then:

```text
Provider not mapped
9 weeks of history

PreM3 searched:
Spotify
Pandora
iHeart
SXM Media
Drive
BigQuery
```

Actions:

- Set up with PreM3
- Upload history
- Create collection plan

Adding a channel does **not** alter an existing MMM automatically.

It updates:

```text
Business IQ
      ↓
Data Foundation
      ↓
Evidence accumulation
      ↓
Pre-Modeling eligibility
      ↓
Future Model Plan
```

---

# 101. Source readiness vs engine eligibility

Example:

```text
Streaming Audio

Source
Import ready

History
9 weeks

MMM
Not yet recommended

Forecasting
Recent driver potentially usable

MTA
Event-level path data unavailable
```

This demonstrates that Data Foundation is multi-engine.

---

# 102. Pre-Modeling boundary

Data Foundation owns:

- source identity;
- source accessibility;
- schema;
- duplicates;
- blank/null issues;
- formats;
- keys;
- freshness;
- continuity;
- lineage;
- units/currency;
- source drift;
- provider semantics;
- cross-source compatibility;
- deterministic cleanup.

Pre-Modeling owns:

- Meridian-specific EDA;
- model history sufficiency decisions;
- variation;
- collinearity;
- parameter pressure;
- model-relevant outlier judgment;
- causal-role review;
- modeling horizon tradeoffs;
- Model Design Brief.

Canonical distinction:

> **Data Foundation asks: “Can we trust and reproduce the evidence?”  
> Pre-Modeling asks: “Can this evidence support the measurement model we want to estimate?”**

---

# 103. Gross anomalies

Data Foundation may flag obvious engineering anomalies:

```text
Spend increased 1,000×
and provider unit representation changed.
```

It may infer:

> Likely unit/schema change.

It should not decide:

> Remove this outlier because it harms MMM.

That belongs downstream.

---

# 104. Data Engineering Intelligence + MEL

Future evaluated provider lessons may improve detection.

Example:

```text
Provider
Meta via Fivetran

Pattern
Duplicate natural keys after connector migration

Candidate remediation
Keep newest _fivetran_synced per verified key

Validation
Spend parity 100%
Duplicates eliminated

Outcome
Successful
```

A future run may surface this recommendation faster.

But:

> Learned experience may suggest the rule. Current deterministic evidence must prove it applies to this customer/source.

---

# 105. Color semantics

Keep the disciplined PreM3 state system.

```text
INDIGO
Active / selected / product navigation

CYAN
Deterministically verified / completed

GREEN
User-declared business importance / positive business context

AMBER
Review / ambiguity / customer attention

RED
Blocked / failed

GRAY
Unknown / neutral / inactive
```

Data Quality:

```text
PASS       CYAN
REVIEW     AMBER
BLOCKER    RED
UNKNOWN    GRAY
```

Do not use green for technical proof if Business IQ uses green to mean “Important.”

---

# 106. Icon guidance

Use one consistent icon library.

Recommended concepts:

| Meaning | Icon concept |
|---|---|
| Data Foundation | database |
| Discovery | database-search / search |
| BigQuery | database / approved Google mark |
| Drive | folder / approved Google Drive mark |
| Source/provider | plug |
| Quality | shield-check |
| Duplicate | copy / layers |
| Missing | circle-slash |
| Schema | table |
| Key/grain | key |
| Freshness | clock |
| Continuity | calendar-range |
| Drift | activity / compare |
| Reconciliation | equal / scale |
| Transformation | arrows / shuffle |
| Lineage | branch / nodes |
| Approval | check-circle |
| Blocker | alert-octagon |
| Review | alert-triangle |
| Receipt | file-check |
| Owner | user |

Icons clarify labels; they do not replace them.

Avoid “AI magic” visual treatment.

---

# 107. Core screens that every initial setup should support

The production happy path should roughly resolve through these core surfaces:

1. **Data Foundation Overview**
2. **Connect BigQuery + Google Drive**
3. **Choose customer GCP project**
4. **Business IQ evidence requirements**
5. **Discovery & assessment progress**
6. **Source Coverage / Assessment workspace**
7. **Data Quality Overview**
8. **PreM3 Data Intelligence Brief**
9. **Issues requiring decisions**
10. **Transformation Review**
11. **Foundation Provisioning Plan**
12. **Permissions / approval**
13. **Build / verification**
14. **Receipts**
15. **Data Foundation Ready**

This does **not** mean 15 mandatory wizard pages.

Several may be one workspace with panels/routes.

---

# 108. Contextual subflows — only when triggered

Do not require every user to visit:

- ambiguous source choice;
- Drive unclassified-file review;
- DV360 prerequisite;
- missing-source collection plan;
- evidence-triggered Business IQ question;
- provider owner request;
- source replacement;
- revoked authorization;
- new channel;
- manual backfill.

They open only when relevant.

---

# 109. Prototype / QA scenarios to retain behind the scenes

The mock-up team should still create fixture support for:

## Mature BigQuery

Most sources already discovered and healthy.

## Mixed environment

BQ + customer ETL + Drive files.

## No existing PreM3 dataset

Customer GCP project exists; foundation is all planned CREATE actions.

## Platform-only provider

DV360 prerequisite.

## Stale source

Source exists but hasn't refreshed.

## Geo mismatch

KPI and sources incompatible geographically.

## New channel

Streaming Audio added after onboarding.

## Business/data contradiction

Always-on channel has unexplained absence.

## Quality blocker

Duplicate keys would double-count spend.

## File schema drift

Monthly exports changed schema.

## Partial approval

Some plan groups deferred.

## Revoked authorization

Previously healthy source becomes inaccessible.

These are **design fixtures, not user-selectable production scenarios**.

---

# 110. Design acceptance criteria — workflow

- [ ] Scenario selector removed from production UX.
- [ ] BigQuery + Google Drive appear on first connection screen.
- [ ] Production flow is organized around Connect / Discover & Assess / Resolve & Plan / Build & Verify / Operate.
- [ ] Mature customers can proceed largely through confirmation/review.
- [ ] Fragmented customers receive deeper contextual guidance.
- [ ] Contextual provider/file issue screens are not mandatory for everyone.
- [ ] Stable Data Foundation workspace remains available throughout.

---

# 111. Design acceptance criteria — Drive

- [ ] Canonical root `prem3-modeling/`.
- [ ] User or PreM3 can create it.
- [ ] PreM3 only scans authorized Drive root.
- [ ] Canonical source/business/evidence subfolders exist.
- [ ] Provider slugs are explicit.
- [ ] No generic `other/`.
- [ ] Canonical naming convention exists.
- [ ] Raw filenames are preserved.
- [ ] File series become logical sources.
- [ ] File sources receive deterministic quality assessment.
- [ ] Approved files ultimately converge into governed BigQuery staging/canonical layers.
- [ ] Drive and BQ cannot silently become competing canonical sources.

---

# 112. Design acceptance criteria — source discovery

- [ ] Business IQ evidence requirements are inherited.
- [ ] Registry narrows discovery.
- [ ] BQ metadata is inspected before row-level profiling.
- [ ] Profiling is bounded to shortlisted sources.
- [ ] Deterministic source identity does not require redundant confirmation.
- [ ] Ambiguous business meaning does require confirmation.
- [ ] Discovery evidence is visible.

---

# 113. Design acceptance criteria — data quality

- [ ] Exact duplicate rows detectable.
- [ ] Duplicate natural/grain keys detectable.
- [ ] Null/blank fields visible.
- [ ] Type/parse inconsistencies visible.
- [ ] Formatting inconsistencies visible.
- [ ] Numeric/domain validity visible.
- [ ] Temporal integrity visible.
- [ ] Referential integrity supported where relevant.
- [ ] Reconciliation supported where controls exist.
- [ ] Drift persisted.
- [ ] Findings show count/evidence/consequence.
- [ ] No opaque score replaces test evidence.

---

# 114. Design acceptance criteria — agentic capability

- [ ] Agent interpretations are grounded in deterministic findings.
- [ ] Hypotheses are labeled as hypotheses.
- [ ] Agent connects provider knowledge to findings.
- [ ] Agent asks business questions rather than unnecessary technical transform questions.
- [ ] Recommendations explain downstream consequence.
- [ ] Customer sees what PreM3 can do vs what they must decide.
- [ ] Agent cannot override blockers or technical truth.
- [ ] Data Intelligence Brief prioritizes instead of dumping every finding.

---

# 115. Design acceptance criteria — transformations

- [ ] Transformation Preview exists.
- [ ] Raw sources are visibly immutable.
- [ ] Cleanup actions have authority classes.
- [ ] Row-/grain-changing actions show impact.
- [ ] Unknown missingness is not zero-filled.
- [ ] Canonical transformation is validated.
- [ ] Applied actions produce receipts.
- [ ] Source quality is re-tested after transformation.

---

# 116. Design acceptance criteria — provisioning

- [ ] Guided Data Provisioning remains inside Data Foundation.
- [ ] Plan has five domains.
- [ ] REUSE / CREATE / CHANGE / CUSTOMER-MANAGED are shown.
- [ ] Requested permissions are previewed.
- [ ] “Will not modify” is explicit.
- [ ] Approval binds to exact plan version.
- [ ] Material changes require reapproval.
- [ ] Build progress reflects real deterministic states.

---

# 117. Design acceptance criteria — readiness

- [ ] `CONNECTED` ≠ `IMPORT_READY`.
- [ ] `IMPORT_READY` is source-level.
- [ ] `DATA_FOUNDATION_READY` is environment-level.
- [ ] `MODEL_READY` remains downstream.
- [ ] Provisioned empty structures never look validated.
- [ ] Data quality and canonical QA are part of completion.
- [ ] Unresolved issues are typed and visible.

---

# 118. Design acceptance criteria — persistent operations

- [ ] Source health remains available after onboarding.
- [ ] Quality monitoring persists.
- [ ] Schema drift persists.
- [ ] Freshness monitoring persists.
- [ ] Authorization recovery exists.
- [ ] New channel/provider onboarding exists.
- [ ] Source replacement preserves lineage.
- [ ] Quality receipts remain accessible.
- [ ] Pre-Modeling consumes the resulting evidence instead of rediscovering it.

---

# 119. Customer learning design

Every educational moment should answer:

```text
WHAT PREM3 FOUND
        ↓
WHY IT MATTERS
        ↓
WHAT PREM3 RECOMMENDS
        ↓
OPTIONAL DEEPER EXPLANATION
```

Keep explanations:

- short;
- contextual;
- business-specific;
- optional.

Do not turn Data Foundation into data-engineering training.

---

# 120. Agent voice

Prefer:

> “These 63 duplicate campaign/day keys could double-count Paid Social spend. PreM3 can verify whether they are connector reissues before proposing a staging rule.”

Avoid:

> “Your data is bad.”

Prefer:

> “This six-week absence cannot yet be distinguished from an intentional pause.”

Avoid:

> “There was no Paid Social spend.”

Prefer:

> “PreM3 recommends using the daily raw source because it preserves detail and has a clean lineage path.”

Avoid:

> “This is definitely the correct table.”

unless deterministic evidence supports that claim.

---

# 121. Final north star

The customer should leave Data Foundation thinking:

> **“PreM3 knew what data should exist because it understood our business. It found most of the evidence itself across BigQuery and our controlled Drive repository. It tested whether the data was structurally trustworthy, explained the problems that actually mattered, asked us only about ambiguous business rules, previewed exactly how it would clean and organize the evidence, built only what we approved, and proved the resulting foundation was healthy.”**

The differentiated operating loop is:

```text
BUSINESS MEANING
        ↓
AUTHORIZED DATA PLANES
BigQuery + prem3-modeling Drive
        ↓
REGISTRY-ASSISTED DISCOVERY
        ↓
SOURCE COVERAGE
        ↓
DATA ENGINEERING ASSESSMENT
        ↓
DETERMINISTIC FINDINGS
        ↓
AGENT INTERPRETATION
        ↓
HUMAN SEMANTIC RESOLUTION
        ↓
TRANSFORMATION PREVIEW
        ↓
APPROVED FOUNDATION PLAN
        ↓
DETERMINISTIC PROVISIONING
        ↓
SOURCE + CANONICAL VALIDATION
        ↓
RECEIPTS
        ↓
CONTINUOUS DATA FOUNDATION HEALTH
        ↓
PRE-MODELING
```

The architectural rule:

> **The agent reasons. Deterministic systems observe, transform, validate, and prove.**

The learning rule:

> **Teach through consequence, not curriculum.**

The integrity rule:

> **Unknown is never silently converted into known. Missing is never silently converted into zero.**

And the product boundary:

> **Data Foundation proves the evidence is trustworthy and reproducible. Pre-Modeling determines whether that trustworthy evidence can support the intended model.**
