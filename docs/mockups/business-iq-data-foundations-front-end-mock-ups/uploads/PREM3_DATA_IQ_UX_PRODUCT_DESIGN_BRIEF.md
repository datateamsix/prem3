# PreM3 Data IQ — UX / Product Design Brief

**Status:** Proposed canonical strategic design handoff  
**Owner:** Data IQ strategy / product architecture  
**Primary consumers:** Product design, UX, frontend planning, backend planning, data engineering, applied modeling  
**Companion specifications:** `BUSINESS_PROFILE_V1_SPEC.md`, `BUSINESS_IQ_UX_DESIGN_BRIEF.md`, import/publish governance contracts, PreM3 long-term product/business context  
**Version:** `data-iq/1.1`  
**Date:** 2026-08-20  

---

# 1. Purpose

This brief defines the target **Data IQ** onboarding and data-foundation experience for PreM3.

Data IQ is not merely a file-upload screen, BigQuery connector, or one-time data-quality assessment.

Its purpose is to establish a **durable, governed measurement data foundation** that PreM3 can use for:

- Meridian / MMM;
- forecasting;
- experiments and incrementality;
- future MTA / attribution workflows;
- scenario analysis;
- Monte Carlo simulation;
- recommendations;
- portfolio optimization;
- outcome tracking;
- customer-local MEL.

### Core product statement

> **Business IQ tells PreM3 what the business means. Data IQ establishes what evidence exists, where it lives, how reliable it is, and how it will stay usable over time.**

The user should leave Data IQ with more than “files connected.”

They should leave with:

> **A governed BigQuery measurement foundation whose sources, refresh behavior, schemas, quality, provenance, and downstream contracts are known.**

---

# 2. Relationship to Business IQ

Business IQ and Data IQ are complementary systems.

```text
BUSINESS IQ
What the business means
        ↓
BUSINESS_CONTEXT_READY
        ↓
DATA IQ
What evidence exists and how it is governed
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
Planning → Readiness → EDA → Remediation → Model handoff
        ↓
MODEL_READY
        ↓
MODELING
```

Business IQ should supply Data IQ with:

- material marketing channels;
- broad channel roles;
- KPI meaning;
- relevant markets / geographies;
- known business events;
- prior-evidence availability;
- important commercial drivers;
- known marketing pauses or launches;
- measurement objective.

Data IQ must **not ask the user to re-enter these concepts**.

Instead, it should ask:

> **Where is the evidence for each thing Business IQ says matters?**

Example:

```text
Business IQ:
Paid Search is a material demand-capture channel.

Data IQ:
Which provider supplies Paid Search data?
Where does it live?
How often is it refreshed?
What history is available?
Is geo-level data available?
Are spend and execution metrics both present?
```

---

## 2.1 Discovery-first operating principle

Data IQ should default to:

> **Discover → infer → show evidence → ask the user to confirm or correct.**

It should not default to asking the customer to manually document infrastructure that PreM3 can inspect itself.

Business IQ gives Data IQ a semantic search target. If Business IQ identifies `Paid Search`, `Paid Social`, `Video`, `Email`, and `Revenue`, Data IQ should use those concepts to search the customer environment for matching evidence rather than presenting a blank inventory form.

```text
BUSINESS IQ
Paid Search
Paid Social
Video
Email
Revenue
      ↓
DATA REQUIREMENT COMPILER
      ↓
PROVIDER REGISTRY
likely providers + expected fields + export patterns
      ↓
BIGQUERY METADATA DISCOVERY
      ↓
TARGETED LIGHTWEIGHT PROFILING
      ↓
SOURCE CANDIDATES + EVIDENCE
      ↓
USER CONFIRMATION ONLY WHERE NEEDED
```

This makes the provider registry a **discovery accelerator**, not just a mapping reference.

## 2.2 Registry-assisted discovery

For each Business IQ requirement, the provider registry should narrow the search space using known provider characteristics such as:

- channel families commonly served by the provider;
- known export/API mechanisms;
- common BigQuery destination naming patterns where documented;
- expected field names and semantic signatures;
- time fields;
- spend fields;
- execution/exposure fields;
- conversion fields;
- geo fields;
- unit/currency quirks;
- common grains;
- known export limitations;
- source documentation and trust level.

Example:

```text
Business IQ requirement
Paid Search
      ↓
Registry candidates
Google Ads
Microsoft Advertising
Search Ads 360
      ↓
Expected signatures
cost / spend
impressions
clicks
campaign identifiers
date / time
optional geo fields
      ↓
BigQuery metadata scan
      ↓
Candidate tables ranked
```

The registry does **not** prove that a discovered table has the business meaning PreM3 assigns to it. It supplies prior evidence that makes discovery faster and more accurate. Ambiguous semantics remain confirmation-required.

## 2.3 Automated Data IQ answer matrix

Once BigQuery access is available, PreM3 should attempt to answer the core source questions programmatically before presenting them to the user.

| Question | Preferred evidence | Expected authority |
|---|---|---|
| Which provider supplies this channel? | transfer/source metadata + registry signature + schema/name evidence | confirmed or likely |
| Where does it live? | project/dataset/table/view metadata | deterministic |
| How often is it refreshed? | declared transfer/scheduled-query config; otherwise observed job/data-arrival cadence | confirmed or inferred |
| What history is available? | partition metadata and/or targeted `MIN/MAX` + continuity profile | deterministic after profiling |
| Is geo-level data available? | schema + distinct-value profiling + coverage over time | detected; user confirms meaning if ambiguous |
| Are spend and execution metrics present? | provider semantic registry + column signatures + profiling | high-confidence semantic mapping |

The UX should distinguish **declared**, **observed**, and **inferred** facts.

Example:

```text
Refresh cadence
Daily — CONFIRMED
Evidence: BigQuery transfer configuration
```

versus:

```text
Refresh cadence
Appears daily — INFERRED
Evidence: 29 successful daily arrivals in the last 30 days
```

## 2.4 Confirmation classes

Avoid exposing arbitrary probability scores as the primary user language.

Use three primary evidence states:

- `CONFIRMED` — authoritative metadata or explicit prior user confirmation establishes the fact;
- `LIKELY` — multiple independent pieces of evidence agree, but semantics are not authoritative;
- `NEEDS_CONFIRMATION` — evidence is ambiguous, conflicting, or incomplete.

Internally, the backend may retain numeric confidence for ranking and evaluation.

A confirmed user correction should become durable tenant-local knowledge with provenance and should improve future source resolution without bypassing deterministic validation.

---

# 3. Product architecture decision

## Data IQ is a data-foundation stage, not a data-upload stage

The foundational design decision is:

> **Regardless of where customer data begins, PreM3 should establish a canonical governed BigQuery measurement layer before downstream modeling workflows depend on it.**

Source data may begin in:

- existing BigQuery tables;
- platform APIs;
- Google Drive;
- CSV / Parquet / JSON;
- customer-created exports;
- CRM / transaction systems;
- prior experiments or analysis artifacts.

But downstream PreM3 workflows should converge toward a controlled measurement substrate.

```text
SOURCE SYSTEMS
      ↓
DISCOVERY / CONNECTION
      ↓
RAW OR LANDING LAYER
      ↓
CANONICAL PREM3 DATA FOUNDATION
      ↓
QUALITY + FRESHNESS + PROVENANCE
      ↓
PRE-MODELING
      ↓
MEASUREMENT ENGINES
```

This gives PreM3 control over naming, table structure, refresh logic, source identity, lineage, data-quality rules, temporal continuity, role mappings, geo mappings, versioning, and downstream compatibility.

---

# 4. Recommended navigation hierarchy

Based on the initial mockup, the left-side stage hierarchy should be:

```text
FOUNDATION
✓ Business Intelligence
→ Data Foundation

MEASUREMENT
🔒 Pre-Modeling
🔒 Modeling
```

When Data IQ is active:

- **Business Intelligence** = completed
- **Data Foundation** = active
- **Pre-Modeling** = locked or upcoming
- **Modeling** = locked

### Main-screen “Next up” card

Change:

```text
Next up
Modeling
Pre-Modeling & EDA
```

to:

```text
Next up
Pre-Modeling
Planning, readiness & EDA
```

or:

```text
Next up
Pre-Modeling
Assess, explore and prepare for Meridian
```

Modeling should appear only after Pre-Modeling reaches `MODEL_READY`.

---

# 5. Data IQ north-star flow

```text
BUSINESS_CONTEXT_READY
        ↓
1. CONNECT GOOGLE / DATA ENVIRONMENT
        ↓
2. ESTABLISH BIGQUERY HOME
        ↓
3. INHERIT BUSINESS IQ CHANNELS + KPI
        ↓
4. DISCOVER EXISTING DATA
        ↓
5. CONFIRM CHANNEL → PROVIDER → SOURCE
        ↓
6. DEFINE REFRESH / CADENCE / HISTORY
        ↓
7. IDENTIFY MISSING SOURCES
        ↓
8. PROVISION PREM3 DATA FOUNDATION
        ↓
9. INGEST / MATERIALIZE
        ↓
10. RUN DATA IQ PROFILING
        ↓
11. RESOLVE EVIDENCE QUESTIONS
        ↓
12. CONFIGURE ONGOING REFRESH
        ↓
13. VERIFY FOUNDATION
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
```

The user should not experience all of these as 13 wizard pages. Several should happen automatically once access is granted.

The UX goal is:

> **Maximum data understanding and infrastructure automation per unit of user effort.**

---

# 6. Entry screen — Data Foundation

The initial mockup is conceptually strong.

Recommended three primary actions:

## Card 1 — Connect BigQuery

**Purpose:** establish the customer’s governed measurement environment.

Suggested copy:

> **Connect BigQuery**  
> Connect the Google Cloud project where your marketing and business data lives. PreM3 will use it to discover existing sources and create your governed measurement foundation.

Possible status states:

- `NOT_CONNECTED`
- `CONNECTED`
- `PROJECT_SELECTED`
- `PREM3_DATASET_READY`
- `WRITE_VERIFIED`
- `NEEDS_ATTENTION`

CTA examples:

- `Connect Google Cloud`
- `Choose project`
- `Review connection`

---

## Card 2 — Map channels to data

The current label “Inventory Channels” is close, but the user already supplied channels in Business IQ.

Recommended label:

> **Map channels to data**

Supporting copy:

> Business IQ identified your marketing channels. Now tell PreM3 where the data for each one comes from — or let PreM3 discover it automatically.

```text
Business IQ = WHICH channels matter
Data IQ     = WHICH provider/source supplies evidence for them
```

CTA:

- `Review sources`
- `Map data sources`

---

## Card 3 — Build Data Foundation

Suggested copy:

> **Build Data Foundation**  
> PreM3 creates the governed BigQuery datasets, tables, mappings, quality checks, and refresh workflows that downstream measurement will use.

CTA:

- `Build foundation`
- after complete: `View foundation`

This action should initially remain disabled until required access/source decisions are resolved.

---

# 7. Step 1 — Google connections

The preferred experience is that users connect Google access from Settings or inline during Data IQ.

Required capabilities may include:

- BigQuery read;
- BigQuery write;
- Google Drive;
- optional future Google Ads / GA4 / other API connections.

The frontend should clearly distinguish:

```text
Signed into PreM3
≠
Authorized PreM3 to access Google data
```

Do not force the user to leave Data IQ to discover that a connection is missing.

If not connected, provide an inline connection action and return the user directly to the Data IQ state they left after authorization.

---

## 7.1 Separate discovery access from foundation-management access

Data IQ should not require broad write authority merely to inspect a customer environment.

### Discovery access

Used to:

- list accessible projects/datasets where permitted;
- inspect table/view metadata;
- inspect schemas and partitions;
- inspect routines/UDF metadata;
- inspect transfer and scheduled-query metadata when authorized;
- inspect relevant job history when authorized;
- execute approved, bounded profiling queries against shortlisted sources.

### Foundation-management access

Requested or activated only when the customer chooses **Build Data Foundation**.

Used to:

- create the `prem3_modeling` dataset if absent;
- create tables and views;
- create approved routines/UDFs;
- create or manage PreM3-owned scheduled queries / transfer configurations;
- write/merge canonical data;
- write control-plane receipts, source health, and provenance.

### Long-lived automation identity

Interactive Google OAuth can establish the customer connection and support discovery, but recurring ingestion and scheduled operations should not depend on a human user remaining logged in.

The target enterprise architecture should use an explicitly authorized service identity / workload identity for long-lived PreM3-managed operations inside the customer environment.

This separation should be visible in product language:

```text
Connect & inspect
      ↓
Review what PreM3 found
      ↓
Approve foundation plan
      ↓
Authorize/build managed infrastructure
```

---

# 8. Step 2 — Establish the BigQuery measurement home

## Question

> **Do you already use BigQuery for marketing or business data?**

Options:

- Yes
- No
- Not sure

### If YES

Show available Google Cloud projects the user is authorized to inspect.

Ask:

> **Which project should PreM3 use for your measurement foundation?**

PreM3 should then:

1. inspect accessible datasets;
2. identify whether a `prem3_modeling` dataset already exists;
3. verify access;
4. discover likely marketing / KPI / CRM datasets;
5. allow user confirmation.

### If NO

Recommended user experience:

> **PreM3 can set up the BigQuery measurement foundation for you.**

The system should create or provision the required dataset architecture inside an authorized existing customer GCP project.

Important nuance:

**PreM3 should not casually imply it can create an entire new Google Cloud project unless enterprise deployment and permissions explicitly support project provisioning.**

Safer default:

```text
No measurement dataset exists
        ↓
Choose authorized customer GCP project
        ↓
PreM3 provisions prem3_modeling dataset + architecture
```

If no usable GCP project exists, surface a guided setup path.

### If NOT SURE

PreM3 can inspect accessible projects and explain what it found.

---

# 9. Canonical BigQuery foundation

Recommended canonical dataset:

```text
<customer_project>.prem3_modeling
```

The dataset should become the governed PreM3 measurement plane.

Conceptual structure:

```text
prem3_modeling
│
├── source_registry
├── source_health
├── source_refresh_log
│
├── raw_*
├── staging_*
│
├── canonical_media
├── canonical_kpi
├── canonical_controls
├── canonical_treatments
├── canonical_population
├── canonical_geo
│
├── model_input_*
├── attribution_input_*
├── forecast_input_*
│
├── experiments
├── prior_evidence
│
├── model_results_*
├── attribution_results_*
├── forecast_results_*
├── scenarios_*
├── decisions_*
└── outcomes_*
```

Exact implementation belongs to backend/data engineering, but the UI should communicate the conceptual architecture:

> Sources are organized once and reused across measurement workflows.

---

# 10. Step 3 — Inherit the Business IQ source requirements

Data IQ should automatically generate a **Data Requirement Inventory** from Business IQ.

Example:

```text
Business IQ says we need evidence for:

✓ Revenue
✓ Paid Search
✓ Paid Social
✓ YouTube / Video
✓ Email / CRM
✓ Promotions
✓ Price
? Competition
✓ Geography
```

Each requirement becomes a Data IQ object.

Conceptual contract:

```text
DataRequirement
├── requirement_id
├── business_profile_ref
├── concept
├── canonical_role
├── channel_id
├── importance
├── required_for[]
├── preferred_grain
├── preferred_geo
├── source_status
├── evidence_status
└── gaps[]
```

---

# 11. Step 4 — Channel → provider → source mapping

For each material channel inherited from Business IQ, capture:

```text
Channel
  ↓
Provider
  ↓
Source location
  ↓
Dataset / table / file / API
  ↓
Available history
  ↓
Refresh cadence
  ↓
Grain
  ↓
Geo
  ↓
Metrics
```

Example:

```text
Paid Search
Business role: Demand capture

Provider
[ Google Ads ]

Where is the data today?
○ BigQuery
○ Platform only
○ Google Drive / CSV
○ Another warehouse / file
○ Not sure

Refresh
○ Automated
○ Manual export
○ Ad hoc
○ Unknown

Typical interval
[ Daily ▼ ]

History available
[ ~3 years ▼ ]
```

---

# 12. Provider discovery

Business IQ should not force provider setup. Data IQ resolves providers.

Provider selection must support:

- one provider per channel;
- multiple providers per channel;
- one provider supplying multiple channels;
- unknown provider;
- custom provider;
- agency-managed exports.

The provider registry can help infer:

- APIs;
- export formats;
- common fields;
- typical grain;
- geo availability;
- expected metrics;
- known limitations.

## 12.1 Targeted discovery algorithm

The preferred discovery order should minimize both user effort and warehouse scanning cost:

```text
1. Compile required evidence from Business IQ
2. Retrieve candidate providers/signatures from registry
3. Inspect BigQuery metadata only
4. Match dataset/table/column signatures
5. Inspect transfer/scheduled-query/job lineage when available
6. Shortlist source candidates
7. Run bounded profiling only on shortlisted candidates
8. Rank evidence
9. Ask the user to confirm ambiguous semantic mappings
```

Do not begin by scanning the contents of every table in the project.

The first pass should be metadata-first. Data scans should be targeted and cost-bounded.

## 12.2 Source evidence card

A mature BigQuery customer should see a review experience like:

```text
Paid Search

Provider                 Google Ads             CONFIRMED
Source                   marketing.google_ads  CONFIRMED
History                  43 months
Refresh                  Daily                  CONFIRMED
Geo                      DMA available          DETECTED
Spend                    Available
Execution                Impressions + clicks
Business IQ match        Paid Search

Evidence
✓ provider transfer/source metadata
✓ registry schema signature
✓ spend field semantic match
✓ execution field semantic match

[ Confirm source ]   [ This isn't right ]
```

The user is reviewing PreM3's evidence, not performing the discovery themselves.

---

# 13. Source-location states

Each provider/source should have an explicit current location:

- `BIGQUERY`
- `PLATFORM_API`
- `GOOGLE_DRIVE`
- `CSV_LOCAL`
- `PARQUET_LOCAL`
- `OTHER_WAREHOUSE`
- `MANUAL_REPORT`
- `NOT_COLLECTED`
- `UNKNOWN`

“We run Meta” must never imply “we possess usable Meta history.”

---

# 14. Step 5 — BigQuery discovery scan

Once an authorized project is selected, offer:

> **Scan for existing measurement data**

PreM3 can inspect metadata first before querying table contents.

Candidate actions:

1. list datasets;
2. list tables/views;
3. inspect names/descriptions;
4. inspect schemas;
5. inspect partition/time columns;
6. estimate row counts;
7. infer likely providers;
8. infer canonical roles;
9. compare discovered assets to Business IQ requirements.

Suggested result:

```text
PreM3 found 12 likely measurement sources

HIGH CONFIDENCE
✓ marketing.google_ads_daily
✓ marketing.meta_campaigns
✓ commerce.orders
✓ analytics.ga4_events

REVIEW
? finance.weekly_sales
? crm.opportunities

NOT RELEVANT
○ tmp_backup_2024
○ sandbox_test
```

The user confirms or rejects candidate mappings.

PreM3 must never silently assume semantic role from a table name alone.

## 14.1 Discovery surfaces

Where authorized, the discovery service should inspect:

- dataset metadata;
- tables and views;
- columns / nested field paths;
- partitions;
- table options/descriptions/labels where useful;
- routines / UDFs;
- transfer configurations and run history;
- scheduled-query configurations;
- query/job history that can reveal referenced and destination tables;
- object modification and freshness metadata.

This enables Data IQ to infer both **what data exists** and **how it gets there**.

## 14.2 Lineage and operational discovery

A useful Data IQ result may be a chain rather than a single table:

```text
raw_google_ads
      ↓
scheduled transformation
      ↓
google_ads_clean
      ↓
weekly reporting aggregate
```

PreM3 should attempt to identify the most appropriate source for its canonical foundation instead of simply choosing whichever table name matches first.

Candidate recommendation factors may include:

- semantic completeness;
- raw vs derived status;
- history;
- freshness;
- stability;
- lineage clarity;
- provider fidelity;
- aggregation loss;
- downstream dependence risk.

The user must be able to override the recommendation.

---

# 15. Step 6 — Basic exploratory profiling

After a source is selected and access authorized, Data IQ should run **lightweight exploratory queries**.

This is not yet official Meridian EDA.

Data IQ profiling should establish:

### Structural
- columns;
- types;
- row count;
- partitioning;
- table/view type;
- date fields;
- likely primary grain.

### Temporal
- earliest date;
- latest date;
- expected cadence;
- missing periods;
- duplicates;
- latency;
- most recent refresh;
- history length.

### Geographic
- national vs geo;
- geo fields;
- geo cardinality;
- geo completeness;
- changing geo values.

### Metric
- spend availability;
- exposure availability;
- KPI availability;
- units;
- currencies;
- null rates;
- zero rates;
- variance;
- obvious non-summable rate metrics.

### Operational
- table refresh behavior;
- partition freshness;
- source owner if available;
- scheduled query existence;
- last update signal where available.

## 15.1 Profiling safety and cost discipline

Data IQ should prefer the cheapest authoritative evidence first:

1. metadata;
2. partition metadata;
3. transfer/job metadata;
4. bounded aggregate profiling;
5. row sampling only when necessary.

Profiling queries should be:

- deterministic;
- read-only;
- parameterized/generated from server-owned source identity;
- dry-run or cost-estimated where practical;
- subject to bytes-billed limits / project policy;
- logged with query purpose and source;
- prevented from reading unrelated candidate tables once the source is rejected.

The agent should never be allowed to invent arbitrary BigQuery paths or raw SQL against arbitrary customer objects.

---

# 16. Data IQ source health

Each source should receive a structured health summary rather than a single opaque score.

Recommended dimensions:

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

Accessibility       READY
History             38 months
Continuity          3 gaps found
Freshness           Updated 8 hours ago
Grain               Daily
Geography           National only
Metric coverage     Spend + impressions + clicks
Refresh             Automated daily
Provenance          CONFIRMED
```

---

# 17. Refresh and cadence inventory

For every provider/source, capture or infer:

### Refresh mechanism
- platform API;
- BigQuery Data Transfer / native export;
- scheduled query;
- external ETL / ELT;
- manual CSV;
- Google Drive drop;
- agency export;
- unknown.

### Refresh cadence
- hourly;
- daily;
- weekly;
- monthly;
- irregular;
- manual;
- unknown.

### Expected data latency
- same day;
- T+1;
- T+2;
- weekly close;
- monthly close.

### Desired canonical cadence

Raw cadence and modeling cadence are separate:

```text
Google Ads raw refresh: daily
Canonical foundation: daily
MMM model input: weekly
Forecasting input: daily
```

This is why Data IQ must be broader than a Meridian-only setup flow.

---

# 18. Missing-source paths

If Business IQ identifies a material channel but no usable source exists, classify the gap.

Example states:

- `SOURCE_FOUND`
- `SOURCE_PARTIAL`
- `SOURCE_NOT_CONNECTED`
- `SOURCE_NOT_COLLECTED`
- `HISTORY_INSUFFICIENT`
- `UNKNOWN`

Example action:

```text
TikTok
No historical source found.

Options:
[ Connect TikTok ]
[ Upload historical CSV ]
[ Create collection plan ]
[ Mark unavailable ]
```

The output becomes part of Pre-Modeling planning.

---

# 19. Google Drive role

Google Drive is a **secondary evidence/import channel**, not the canonical data foundation.

Recommended use cases:

- historical CSV exports;
- prior MMM reports;
- experiment evidence;
- pricing calendars;
- promotions;
- offline data;
- agency files;
- controls;
- manually maintained business datasets.

Canonical Drive folder:

```text
prem3-modeling/
├── imports/
├── exports/
└── reports/
```

Data IQ should materialize approved usable data into the governed BigQuery layer when appropriate.

---

# 20. CSV / file import UX

For file-based sources, identify:

- provider;
- channel / role;
- time field;
- expected cadence;
- time coverage;
- geo;
- file update behavior;
- one-time history vs ongoing source.

PreM3 may infer candidates and ask for confirmation.

---

# 21. Step 7 — Provision the foundation

Once enough source decisions are made, present a **Foundation Plan**.

Example:

```text
PreM3 will create:

BigQuery
✓ prem3_modeling dataset
✓ source registry
✓ canonical KPI tables
✓ canonical media tables
✓ controls / treatments structure
✓ source health tables
✓ model input layer

Automation
✓ Google Ads daily refresh
✓ Meta daily refresh
✓ CRM daily transformation
✓ Shopify / revenue daily transformation
✓ weekly canonical integrity checks

Monitoring
✓ freshness checks
✓ continuity checks
✓ schema-change detection
✓ failed-refresh alerts
```

Primary CTA:

> **Build Data Foundation**

This is a consequential infrastructure action and should show exactly what will be created before execution.

---

# 22. PreM3-managed refresh workflows

Long-term, Data IQ should remove recurring data engineering work.

Possible mechanisms include:

- BigQuery Data Transfer Service;
- scheduled queries;
- provider APIs;
- Cloud Run jobs;
- Workflows;
- Cloud Scheduler;
- Pub/Sub / event-driven ingestion;
- customer ETL integration where already established.

The UI should abstract implementation unless the user asks for technical detail.

---

# 23. Data contracts and conventions

Data IQ should establish explicit contracts for:

- provider identity;
- source object;
- canonical role;
- time field;
- geo field;
- currency;
- units;
- expected grain;
- refresh cadence;
- latency;
- schema fingerprint;
- version identity;
- lineage;
- destination mapping.

Future source changes should produce detectable contract changes.

---

# 24. Schema drift and freshness monitoring

Data Foundation persists after onboarding.

Monitor for:

- source table missing;
- authorization expired;
- schema field removed;
- field type changed;
- new field added;
- freshness missed;
- scheduled job failed;
- unexpected row collapse;
- null increase;
- currency change;
- geo coverage change;
- channel disappeared;
- duplicate growth.

These become actionable Data IQ findings.

---

# 25. Evidence-triggered Business IQ questions

The two foundational layers should improve each other.

Example:

```text
Data IQ observed:
Paid Social spend is absent for 6 weeks.

Business IQ knows:
Paid Social is normally always-on.

PreM3 asks:
Was Paid Social intentionally paused during these six weeks?

[ Yes ]
[ No ]
[ Not sure ]
```

The answer updates Business IQ and changes interpretation.

---

# 26. Data IQ conceptual contract

Recommended high-level semantic object:

```text
DataProfile
├── profile_id
├── schema_version
├── tenant_scope
├── workspace_scope
├── business_profile_ref
├── google_connections[]
├── bigquery_home
├── source_requirements[]
├── sources[]
├── provider_bindings[]
├── role_assignments[]
├── source_health[]
├── refresh_policies[]
├── data_contracts[]
├── lineage[]
├── quality_findings[]
├── access_findings[]
├── data_gaps[]
├── infrastructure_plan
├── automation_plan
├── readiness
├── version
├── fingerprint
├── created_at
└── updated_at
```

---

# 27. Source object

```text
DataSource
├── source_id
├── provider_id
├── channel_ids[]
├── canonical_roles[]
├── source_location_type
├── source_identity
├── project
├── dataset
├── object
├── format
├── grain
├── geo_scope
├── time_field
├── earliest_available
├── latest_available
├── history_length
├── refresh_method
├── refresh_cadence
├── expected_latency
├── schema_fingerprint
├── version_identity
├── access_state
├── import_state
├── health_state
└── provenance
```

---

# 28. Data IQ readiness state

Do not reuse `IMPORT_READY` or `MODEL_READY` as the overall Data IQ completion state.

Recommended stage state:

> `DATA_FOUNDATION_READY`

Meaning:

- the measurement BigQuery home is established;
- required permissions are verified;
- relevant sources are discovered or explicitly marked unavailable;
- source roles are mapped;
- freshness / continuity / history are known;
- ingestion / materialization paths are established;
- canonical foundation infrastructure exists;
- ongoing refresh plans are known;
- unresolved gaps are explicitly represented;
- PreM3 has enough evidence to enter Pre-Modeling.

This does **not** mean the data is Meridian model-ready.

---

# 29. Governance-state separation

The UX must preserve distinct concepts:

```text
CONNECTED
        ↓
SOURCE_DISCOVERED
        ↓
IMPORT_READY
        ↓
MATERIALIZED / INGESTED
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
        ↓
MODEL_READY
        ↓
PUBLISH_READY
        ↓
MODELING
```

The frontend must never infer these states from counts or percentages.

---

# 30. Data IQ completion screen

Recommended completion treatment:

```text
Your Data Foundation is ready

6 marketing sources connected
1 KPI source connected
3 business-context sources connected
4 automated refresh workflows active
2 source gaps documented

BigQuery foundation
<project>.prem3_modeling

Next
Pre-Modeling
Planning, readiness & EDA

[ Continue to Pre-Modeling ]
```

Surface unresolved items separately.

---

# 31. Pre-Modeling handoff

The next stage should be named:

> **Pre-Modeling**

Potential sub-stages:

```text
PRE-MODELING

1. Scope & Plan
2. Readiness Assessment
3. Data Repair / Remediation
4. Official Meridian EDA
5. Business–Evidence Reconciliation
6. Model Design Brief
7. Model Handoff
```

This stage eventually ends at `MODEL_READY`.

Only then should Modeling unlock.

---

# 32. Long-term multi-engine requirements

Data IQ must not be designed exclusively around Meridian.

## MMM
Needs channel spend/execution, KPI, controls, treatments, geography, time, population, and prior/experiment evidence.

## MTA
Needs event/path data, identity/journey keys where appropriate, timestamps, touchpoints, conversions, and observability metadata.

## Forecasting
Needs KPI history, drivers, calendar, price, promotion, demand, inventory, and macro factors.

## Experiments
Needs treatment assignment, geo/audience, exposure, outcome, experiment dates, and design metadata.

## Monte Carlo / scenarios
Needs model distributions, planning constraints, cost, price, margins where available, budget ranges, and uncertainty inputs.

The canonical foundation should prioritize **reusable evidence objects**, not one Meridian-shaped table.

---

# 33. Suggested main Data Foundation page after setup

The initial three-card orientation page can evolve into an operating dashboard:

```text
DATA FOUNDATION

Foundation status          READY

BigQuery
prem3-prod.prem3_modeling

Sources
9 connected
1 needs attention

Refresh
7 automated
2 manual

Freshness
8 current
1 late

Coverage
36 months media
42 months KPI

[ View sources ] [ View infrastructure ] [ Run health check ]
```

---

# 34. Design principles

## DIQ-01 — Inherit before asking
Do not ask for concepts already captured in Business IQ.

## DIQ-02 — Discover before asking
If PreM3 can inspect metadata or connected sources, do that before presenting manual forms.

## DIQ-03 — Confirm semantics
Discovery proposes mappings; users confirm ambiguous meaning.

## DIQ-04 — BigQuery is the governed measurement plane
Files and APIs are sources. The durable foundation is BigQuery-centered.

## DIQ-05 — Automate recurring work
Eliminate repetitive export, scheduling, and quality-check labor where possible.

## DIQ-06 — Preserve provenance
Every canonical field remains traceable to source and transformation.

## DIQ-07 — Unknown is valid
Missing source knowledge is explicit.

## DIQ-08 — No generic readiness score as authority
Show specific dimensions and blockers.

## DIQ-09 — Separate infrastructure readiness from model readiness
`DATA_FOUNDATION_READY` is not `MODEL_READY`.

## DIQ-10 — Build for all future measurement engines
Serve MMM now and MTA, forecasting, experiments, simulation, and optimization later.

## DIQ-11 — Registry narrows; evidence proves
Use provider knowledge to reduce search space, but never treat a registry match alone as proof of customer-specific semantics.

## DIQ-12 — Metadata before data scans
Discover structure and operational evidence first; profile only shortlisted sources.

## DIQ-13 — Confirmation is targeted
Ask customers to confirm ambiguity, not to manually document facts PreM3 can establish programmatically.

---

# 35. Key UI surfaces for design

The design team should mock up:

1. Data Foundation landing / orientation
2. Google connection state
3. BigQuery project selection
4. No existing BigQuery dataset path
5. Existing BigQuery discovery path
6. Business IQ → Data requirements view
7. Channel → provider mapping
8. Source-location selector
9. Automatic BigQuery discovery results
10. Detected-source confirmation
11. Source profile / health card
12. Missing-source path
13. Drive / CSV import path
14. Foundation Plan review
15. Build / provisioning progress
16. Refresh automation setup
17. Data Foundation Ready
18. Ongoing Data Foundation dashboard
19. Evidence-triggered Business IQ question
20. Pre-Modeling handoff
21. Registry-assisted auto-discovery results
22. Confirmed vs likely vs needs-confirmation evidence states
23. Lineage / refresh explanation panel
24. Discovery-access vs build-access authorization state

---

# 36. Required prototype scenarios

## Scenario A — Existing mature BigQuery environment
PreM3 connects, scans metadata, proposes mappings, profiles sources, creates canonical foundation, and reaches `DATA_FOUNDATION_READY`.

## Scenario B — No measurement dataset yet
PreM3 provisions `prem3_modeling`, connects supported sources, imports historical files, creates canonical tables, configures refresh, and reaches `DATA_FOUNDATION_READY`.

## Scenario C — Mixed environment
Some data is in BigQuery, some in Drive, one source only exists in-platform. Show one unified source inventory.

## Scenario D — Business IQ channel has no evidence
User can connect, upload, create a collection plan, or mark unavailable.

## Scenario E — Source is stale
Distinguish “source exists” from “source is usable and current.”

## Scenario F — National vs geo mismatch
Business IQ says regional performance matters; Data IQ finds national-only media. Surface this for Pre-Modeling.

## Scenario G — Evidence-triggered clarification
A six-week channel gap triggers a business question; the answer updates Business IQ.

---

# 37. Design deliverables

Recommended design package:

1. End-to-end Data IQ flow map
2. Revised foundational navigation
3. Low-fidelity wireframes for primary states
4. High-fidelity Data Foundation landing page
5. High-fidelity existing-BQ happy path
6. High-fidelity mixed-source path
7. High-fidelity Data Foundation Ready state
8. Source inventory / health component system
9. Channel-provider-source mapping pattern
10. BigQuery discovery review pattern
11. Infrastructure Plan review
12. Provisioning progress state
13. Missing / unknown / unavailable states
14. Evidence-triggered Business IQ pattern
15. Ongoing Data Foundation dashboard concept
16. Pre-Modeling handoff
17. Responsive representative states
18. Interaction annotations sufficient for frontend planning

---

# 38. Design acceptance criteria

### User effort
- Business IQ inputs are reused rather than repeated.
- Existing BigQuery assets can be discovered automatically.
- Mature customers progress mostly by confirming findings.
- Less mature customers receive a guided setup path.

### Data clarity
- Provider, channel, source location, history, cadence, and freshness are visible.
- Missing data and unknown data remain distinct.

### Infrastructure
- BigQuery is clearly the canonical PreM3 data foundation.
- The user understands what PreM3 will create before provisioning.
- Refresh and monitoring are first-class concepts.

### Governance
- `IMPORT_READY`, `DATA_FOUNDATION_READY`, `MODEL_READY`, and `PUBLISH_READY` are not visually conflated.
- Google authorization is distinct from PreM3 authentication.
- Ambiguous source mappings require confirmation.

### Product architecture
- Data IQ feeds Pre-Modeling, not Modeling directly.
- Data IQ is reusable for MMM, MTA, forecasting, experiments, and simulation.
- The foundation persists after onboarding as an operational surface.

---

# 39. North-star experience

> **PreM3 already knows what matters from Business IQ. It connects to where your data lives, discovers what is available, identifies what is missing, organizes the evidence into a governed BigQuery foundation, and keeps it healthy over time.**

The flow should progress from:

```text
Where is your data?
```

to:

```text
Here is what PreM3 found.
Here is what the business says should exist.
Here is what the evidence actually contains.
Here is what is missing.
Here is the governed foundation PreM3 built.
Here is what is ready for Pre-Modeling.
```

---

# 39.1 Technical source note for designers

The discovery experience is grounded in capabilities that BigQuery exposes programmatically, including read-only `INFORMATION_SCHEMA` metadata views for warehouse objects, partition and routine metadata, BigQuery job metadata, and BigQuery Data Transfer Service configuration/run information. Scheduled queries are implemented through BigQuery Data Transfer Service.

Design should therefore assume that many source questions can be **pre-populated from evidence** when permissions are present, while always retaining an explicit user confirmation/correction path for business semantics.

Canonical technical references should be maintained by engineering against current official Google Cloud documentation rather than duplicated as static product copy.

---

# 40. Strategic summary

```text
BUSINESS IQ
What the business means
        ↓
DATA IQ
What evidence exists + build the governed measurement foundation
        ↓
PRE-MODELING
Plan + assess + repair + EDA + reconcile + model design
        ↓
MODEL_READY
        ↓
MODELING
Fit + diagnose + refine + accept
        ↓
MEASUREMENT
MMM + MTA + Forecasting + Experiments
        ↓
SCENARIOS / MONTE CARLO
        ↓
PORTFOLIO OPTIMIZATION
        ↓
DECISION
        ↓
OUTCOME
        ↓
MEL
```

Data IQ is not setup plumbing.

> **It is the durable evidence infrastructure on which PreM3's entire Marketing Investment Intelligence system depends.**
