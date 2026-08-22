# BACKEND DEVELOPMENT PROMPT — PreM3 Data Foundation Runtime
## BigQuery + Google Drive Discovery, Deterministic Data Engineering, Transformation Planning, Guided Provisioning & Governed Readiness

**Repository:** `datateamsix/prem3`  
**Target base:** latest `origin/main`  
**Recommended branch:** `feature/prem3-data-foundation-backend`  
**PR target:** `main`  
**Work mode:** parallel feature development; do **not** stack on another feature branch  
**Primary product stage:** Data Foundation  
**Upstream:** Business IQ / `BUSINESS_CONTEXT_READY`  
**Source gate:** `IMPORT_READY`  
**Environment gate:** `DATA_FOUNDATION_READY`  
**Downstream:** Pre-Modeling  
**Canonical BigQuery dataset:** `prem3_modeling`  
**Canonical Drive root:** `prem3-modeling/`  

---

# 0. Mission

Build the backend plumbing required for the PreM3 **Data Foundation** workflow.

The implementation must allow PreM3 to:

1. inherit evidence requirements from Business IQ;
2. bind authorized BigQuery and Google Drive locations;
3. discover likely measurement sources without asking the customer questions the system can answer itself;
4. use the provider registry to identify and characterize sources;
5. run deterministic source-level data engineering assessments;
6. distinguish observed facts from agent interpretation;
7. compile transparent Transformation Previews;
8. execute only authorized deterministic transformations;
9. preserve customer raw data as immutable;
10. materialize governed staging/canonical assets in customer BigQuery;
11. create approved Data Foundation infrastructure and recurring ingestion;
12. produce source-level `IMPORT_READY` proof;
13. produce environment-level `DATA_FOUNDATION_READY` proof;
14. persist receipts, lineage, quality findings, and operational health for downstream Pre-Modeling and future engines;
15. continuously monitor freshness, schema drift, quality drift, and authorization state.

The architecture principle is:

> **The agent reasons. Deterministic systems observe, transform, validate, and prove.**

Do not make an LLM the owner of source identity, query results, quality checks, transformations, or readiness.

---

# 1. Mandatory first step — bounded review of the current codebase

Do **not** review the entire repository.

Before writing code, perform a focused review of only the paths and systems related to Data Foundation.

Record the result in:

```text
docs/backend/DATA_FOUNDATION_CURRENT_STATE_REVIEW.md
```

The review must include the current `origin/main` SHA and a short overlap report for in-flight remote branches / PRs.

## 1.1 Branch and remote inspection

Start with:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git status
git rev-parse HEAD
git branch -r
```

Then inspect open PRs / active branches **only to identify overlapping paths**.

Do not use another feature branch as the base.

Do not copy or cherry-pick another team's work without explicit approval.

As of the planning review that produced this prompt, open stacked backend PRs existed around MEL / coordinator work. Re-check current reality before coding.

Document:

```text
main_sha
open_prs_relevant_to_app_core_tools_registry
remote_branches_with_path_overlap
files_likely_to_conflict
integration_strategy
```

---

# 2. Required feature branch

Create the branch from the freshly updated `main`:

```bash
git checkout -b feature/prem3-data-foundation-backend
```

Recommended branch name:

> **`feature/prem3-data-foundation-backend`**

Why:

- follows existing `feature/prem3-*` naming;
- explicitly distinguishes this from design/frontend work;
- broad enough to include discovery, ETL, quality, provisioning, and runtime contracts;
- avoids implying it is stacked on Mission 2 or another backend branch.

If this exact branch already exists, stop and report rather than silently reusing it.

---

# 3. Parallel-development safety

Another team is working in parallel.

Therefore:

## 3.1 Do not branch from their feature branch

This branch must remain based on `main`.

## 3.2 Minimize edits to shared monoliths

Prefer new Data Foundation packages/modules over expanding:

```text
app/core/run_coordinator.py
```

Do not turn the current pre-modeling run coordinator into the Data Foundation orchestrator.

Create a separate domain/service boundary.

## 3.3 Do not duplicate in-flight auth/control-plane work

If tenant/auth/API/Firestore systems exist only in another in-flight branch:

- inspect their public contracts/path ownership for integration awareness;
- do not recreate a competing auth/control plane;
- define ports/interfaces that can later be wired into those systems;
- record expected integration points in:

```text
docs/backend/DATA_FOUNDATION_PARALLEL_INTEGRATION_NOTES.md
```

If those systems have landed on `main` by the time this work begins, use them.

## 3.4 No frontend changes

Do not modify:

```text
frontend/
```

unless the task is only to update generated shared contract artifacts already owned by backend tooling.

No UI implementation belongs in this branch.

---

# 4. Current relevant architecture — verify before coding

The following was observed on `main` during prompt preparation and must be verified again.

## 4.1 Existing deterministic profiling

Current:

```text
app/tools/profiling.py
```

already includes useful primitives for:

- row/column counts;
- dtypes;
- missing counts;
- exact duplicate counts;
- duplicate-group counts;
- duplicate detection by subset;
- grain inference;
- non-summable field detection.

Do not throw these away.

Generalize or compose them into the Data Foundation quality engine.

---

## 4.2 Existing deterministic remediation

Current:

```text
app/tools/remediation.py
```

already includes:

- explicit-format date normalization;
- exact duplicate removal;
- numeric normalization;
- explicit channel-label mapping;
- campaign→channel aggregation guarded by summability;
- daily→weekly aggregation guarded by summability.

These functions copy the source frame rather than mutating it.

Preserve that principle.

Extend safely rather than replacing with a generic arbitrary transform executor.

---

## 4.3 Existing validation

Current:

```text
app/tools/validation.py
```

already proves examples such as:

- date format;
- required missingness;
- grain uniqueness;
- weekly grain;
- numeric spend;
- channel fields;
- provenance completeness.

These rules currently serve model-readiness flows.

Data Foundation needs **separate quality/import rules**.

Do not overload existing `MR-*` semantics for Data Foundation checks.

Create dedicated rule IDs / quality contracts.

---

## 4.4 Existing BigQuery parity proof

Current:

```text
app/tools/bigquery_inspect.py
```

independently reads BigQuery after publication and checks:

- destination identity;
- row count;
- schema;
- descriptions;
- partitioning;
- clustering;
- keys;
- nulls;
- fingerprints;
- semantic fields;
- provenance.

This is an excellent proof pattern.

Reuse the **read-back verification philosophy** for Data Foundation.

Important:

`bigquery_inspect.py` currently reads the final model table with `SELECT *`.

That behavior is appropriate for a bounded final model artifact.

It is **not** the discovery strategy for arbitrary customer datasets.

Data Foundation discovery must be metadata-first and bounded.

---

## 4.5 Current BigQuery integration is thin

Current:

```text
app/integrations/bigquery.py
```

is essentially a client constructor using configured project/location.

It is not a tenant-scoped Data Foundation integration layer.

Do not put arbitrary customer project IDs into global settings.

Create context-bound adapters whose resource authority is supplied server-side.

---

## 4.6 Existing provider registry

Current:

```text
app/registry/
```

already provides typed provider knowledge, including concepts such as:

- provider ID;
- category;
- report family;
- export formats;
- grain;
- date fields;
- filename hints;
- summable metric hints;
- non-summable rates;
- Meridian fit/gaps;
- field semantics;
- provider quirks;
- source references.

This is a major Data Foundation dependency.

Extend registry contracts carefully for discovery/provisioning capability.

Do not create a second provider registry.

---

## 4.7 Existing provenance

Current:

```text
app/tools/provenance.py
```

already records deterministic transformation evidence with:

- source/output URIs;
- source/output SHA;
- row counts;
- parameters;
- reason;
- rule ID;
- tool;
- timestamp;
- status.

Preserve this pattern.

Data Foundation receipts should reuse/generalize this lineage model rather than introduce opaque transform logs.

---

## 4.8 Existing raw immutability / fail-closed coordinator philosophy

The current coordinator and repo rules already establish:

- raw input immutable;
- deterministic tools own mutations;
- transformation provenance required;
- fail closed on invalid transitions;
- agent supplies IDs, not transform parameters;
- durable receipts are authoritative.

Data Foundation must strengthen this pattern, not weaken it.

---

# 5. Read these files — and only the relevant parts

At minimum, inspect:

```text
AGENTS.md

app/core/contracts.py
app/core/state.py
app/core/run_coordinator.py
    - initialization/context
    - profiling/assessment
    - remediation authority
    - publication/proof patterns
    Do not perform a line-by-line review of unrelated EDA/modeling logic.

app/tools/profiling.py
app/tools/remediation.py
app/tools/validation.py
app/tools/provenance.py
app/tools/fingerprints.py
app/tools/safety.py
app/tools/bigquery_inspect.py
app/tools/bigquery_publish.py
app/tools/schema_compiler.py
app/tools/io.py

app/integrations/bigquery.py
app/integrations/gcs.py

app/registry/schema.py
app/registry/loader.py
app/registry/providers/README.md
relevant provider entries in:
app/registry/providers/marketing_advertising_providers.v1.json

tests/unit/test_profiling.py
tests/unit/test_remediation.py
tests/unit/test_provenance.py
tests/unit/test_registry.py
tests/unit/test_bigquery_inspect.py
relevant coordinator / run-tool authority tests
```

Also inspect the currently merged architecture docs relevant to:

- tenancy;
- server-side authority;
- API/control plane;
- BigQuery;
- Drive;
- import/export contracts;

if those docs are present on `main`.

Do not spend time reviewing branding, frontend rendering, MEL internals, or Meridian worker internals except where a contract boundary requires it.

---

# 6. Deliverable from review phase

Before implementation, write:

```text
docs/backend/DATA_FOUNDATION_CURRENT_STATE_REVIEW.md
```

It must answer:

1. What existing primitives can be reused unchanged?
2. What should be generalized?
3. What new package boundaries are required?
4. What code must **not** be modified?
5. What in-flight branches/PRs create merge risk?
6. Which Data Foundation capabilities do not yet exist?
7. What are the exact server-side authority assumptions?
8. What dependencies must be added?
9. What existing tests guard behavior we must preserve?
10. Is the branch correctly based on the current `main` SHA?

Do not begin broad implementation until this review exists.

---

# 7. Proposed package architecture

Prefer a new bounded package:

```text
app/data_foundation/
├── __init__.py
├── contracts.py
├── enums.py
├── context.py
├── service.py
├── readiness.py
├── receipts.py
├── issues.py
│
├── discovery/
│   ├── __init__.py
│   ├── requirements.py
│   ├── candidates.py
│   ├── provider_matching.py
│   ├── lineage.py
│   └── query_budget.py
│
├── quality/
│   ├── __init__.py
│   ├── engine.py
│   ├── checks.py
│   ├── schema.py
│   ├── temporal.py
│   ├── reconciliation.py
│   └── drift.py
│
├── transformation/
│   ├── __init__.py
│   ├── catalog.py
│   ├── planner.py
│   ├── preview.py
│   ├── executor.py
│   └── validator.py
│
├── bigquery/
│   ├── __init__.py
│   ├── adapter.py
│   ├── discovery.py
│   ├── profiling.py
│   ├── provisioning.py
│   └── monitoring.py
│
├── drive/
│   ├── __init__.py
│   ├── adapter.py
│   ├── root.py
│   ├── naming.py
│   ├── files.py
│   ├── grouping.py
│   └── ingestion.py
│
└── provisioning/
    ├── __init__.py
    ├── contracts.py
    ├── planner.py
    ├── executor.py
    ├── bigquery_assets.py
    ├── transfers.py
    └── validation.py
```

This is guidance, not a requirement to create empty files.

Keep modules only when they have a clear responsibility.

---

# 8. Server-side authority boundary

Define a typed context such as:

```text
DataFoundationContext
```

It should resolve server-owned:

- tenant/workspace identity;
- project identity;
- selected customer GCP project;
- allowed BigQuery datasets/objects;
- bound Drive root folder ID;
- connection IDs / credential references;
- approved plan ID/version;
- runtime service identity;
- entitlement/capability if available.

The agent/user must **not** pass arbitrary:

```text
project_id
dataset_id
table_id
drive_folder_id
SQL
output path
IAM binding
```

into mutating tools as free-form authority.

User choices identify approved logical resources.

Server-side context resolves physical resources.

---

# 9. Connection contracts

Implement typed connection/binding contracts.

Suggested concepts:

```text
DataConnection
BigQueryConnectionBinding
DriveConnectionBinding
DriveRootBinding
AuthorizationState
DiscoveryCapability
ProvisioningCapability
```

Possible states:

```text
NOT_CONNECTED
AUTHORIZATION_PENDING
AUTHORIZED
DISCOVERY_READY
PROVISIONING_READY
ACCESS_REVOKED
ERROR
```

Do not claim a user is provision-ready merely because OAuth succeeded.

Verify usable access.

---

# 10. Google Drive authority boundary

Google Drive OAuth scopes are not equivalent to folder-level enforcement.

Regardless of OAuth scope:

- bind an explicit `DriveRootBinding`;
- store the root folder ID for `prem3-modeling`;
- reject discovery/mutation outside that root;
- never broadly crawl unrelated Drive content;
- preserve connection provenance.

The user or PreM3 may create the root.

Preferred root name:

```text
prem3-modeling
```

If a user selects an existing folder as the authorized root, persist that binding explicitly.

Do not infer root authority from folder name alone.

---

# 11. Canonical Drive structure

Support the design contract:

```text
prem3-modeling/
│
├── sources/
├── business_data/
├── evidence/
├── exports/
├── reports/
└── system/
```

Provider-specific source example:

```text
sources/meta_ads/incoming/
```

System-managed lifecycle directories may include:

```text
processed/
rejected/
archive/
```

Use explicit provider slugs.

Examples:

```text
meta_ads
google_ads
spotify_ads
```

Do not use `other`.

Custom:

```text
custom/regional_tv_agency
```

---

# 12. Drive file identity

Raw files are immutable evidence.

Persist:

```text
drive_file_id
original_name
canonical_logical_name
parent_folder_id
source_slug
file_fingerprint
mime_type
size
modified_time
discovered_at
registered_at
```

Canonical logical naming:

```text
<source_slug>__<data_role>__<grain>__<start_date>__<end_date>__v<version>.<ext>
```

Do not require destructive rename.

Do not overwrite original files.

---

# 13. Drive file-series grouping

Implement deterministic grouping evidence for recurring file exports.

Candidate grouping signals may include:

- same parent source folder;
- provider registry signature;
- same column/header fingerprint;
- date-range adjacency;
- filename tokens;
- same business role;
- consistent report grain.

Output:

```text
FileSeriesCandidate
```

with evidence and confidence.

Agent may explain grouping.

Deterministic system preserves the actual file membership.

No file may silently move between logical sources without a new decision/receipt.

---

# 14. Business IQ evidence requirements

Data Foundation must consume a typed upstream snapshot rather than re-questioning the user.

Implement a boundary such as:

```text
EvidenceRequirementSet
```

Possible requirement types:

```text
KPI
MEDIA
PROMOTION
PRICING
INVENTORY
DISTRIBUTION
SALES_ACTIVITY
COMPETITION
EXTERNAL_CONTROL
EXPERIMENT_EVIDENCE
PRIOR_MMM
OTHER_CUSTOM
```

Each requirement should preserve:

- Business IQ source fact IDs;
- business role;
- channel ID if applicable;
- market scope;
- expected evidence category;
- downstream use;
- acknowledged unknowns.

Do not hard-code Business IQ UI fields into discovery logic.

---

# 15. BigQuery discovery — metadata first

Implement bounded project/dataset discovery.

Use metadata surfaces such as:

- datasets;
- tables/views;
- schemas;
- partitions;
- labels/descriptions;
- routines;
- transfer configurations if authorized;
- scheduled-query/job lineage where available.

Do not begin discovery with broad `SELECT *`.

Pipeline:

```text
Metadata inventory
        ↓
Registry matching
        ↓
Candidate shortlist
        ↓
Bounded profiling plan
        ↓
Profile only shortlisted candidates
```

---

# 16. BigQuery discovery query safety

Create a deterministic `QueryBudgetPolicy`.

The LLM must not generate arbitrary SQL.

All profiling SQL is compiled by deterministic code from typed operations.

Support:

- validated identifiers;
- partition predicates;
- selected columns only;
- bounded windows;
- `LIMIT` where appropriate;
- aggregate checks;
- dry-run byte estimation where supported;
- configurable max bytes scanned;
- query timeout;
- safe cancellation;
- query labels for audit.

Reject:

- arbitrary SQL text supplied by agent/user;
- wildcard cross-project scans not explicitly authorized;
- unbounded discovery queries.

---

# 17. Source candidates

Create a typed:

```text
SourceCandidate
```

Include:

```text
candidate_id
evidence_requirement_id
location_type
resource_identity
provider_candidate
provider_match_evidence
registry_version
history_summary
freshness_summary
grain_summary
geo_summary
metric_summary
lineage_summary
quality_summary
authority
```

Use provenance classes:

```text
VERIFIED
DETECTED
INFERRED
USER_PROVIDED
PROVIDER_DOCUMENTED
UNKNOWN
```

Do not mix with user decision state.

---

# 18. Source binding

Once selected/verified, persist:

```text
SourceBinding
```

with:

- logical business requirement;
- provider;
- physical source;
- authority/evidence;
- selected canonical source;
- historical/ongoing role;
- precedence rules;
- approved scope;
- source contract;
- current lifecycle state.

Do not infer that a Drive file and BQ table are independent canonical sources if lineage says they are the same pipeline.

---

# 19. Provider matching

Reuse and extend:

```text
app/registry/
```

Matching evidence may include:

- native transfer metadata;
- table names;
- field signatures;
- provider-specific IDs;
- report grain;
- date fields;
- filename hints;
- export format;
- provider-specific metric semantics.

Build a deterministic evidence vector.

Do not let an LLM simply declare:

```text
this is Meta Ads
```

without evidence.

---

# 20. Extend provider capability metadata carefully

If necessary, extend registry records with versioned optional fields such as:

```text
discovery_signatures
provisioning_capability
native_transfer_type
expected_unique_keys
revision_timestamp_fields
late_arrival_policy
currency_unit_behavior
supported_file_patterns
source_health_rules
```

Maintain backward compatibility with existing registry fixtures/tests.

Registry version must be persisted on assessments/plans.

---

# 21. Source Assessment contract

Implement:

```text
SourceAssessment
```

with four first-class pillars:

```text
OperationalHealthAssessment
ContractStructureAssessment
DataQualityAssessment
MeasurementCoverageAssessment
```

---

# 22. Operational health

Deterministic checks should support:

- access works now;
- expected refresh cadence;
- observed cadence;
- last successful load;
- source event time;
- ingestion event time;
- refresh failures;
- authorization state;
- late-arrival watermark;
- source owner;
- lineage visibility.

Never derive freshness from the UI.

---

# 23. Contract & structure

Assess:

- required fields;
- unexpected fields;
- missing fields;
- physical types;
- parseability;
- expected grain;
- observed grain;
- natural/business key;
- partition field;
- time semantics;
- geo semantics;
- currency/unit semantics;
- schema fingerprint;
- provider contract version.

---

# 24. Data quality engine — mandatory deterministic families

Build a reusable deterministic quality engine.

Each check returns structured evidence.

Use a contract such as:

```text
QualityCheckResult
```

with:

```text
check_id
check_family
status
severity
consequence
source_id
field_ids
observed_count
observed_rate
evidence
rule_version
executed_at
```

Do not return only prose.

---

# 25. Quality family — uniqueness

Implement:

- exact duplicate row detection;
- duplicate natural/business key detection;
- duplicate grain key detection;
- duplicate file fingerprint detection;
- overlapping file-period detection;
- provider/connector reissue detection when revision semantics exist;
- row multiplication checks after transformation/join.

---

# 26. Quality family — completeness

Implement:

- null counts/rates;
- blank/empty-string counts;
- key-field nulls;
- entirely empty columns;
- required-field completeness;
- unexpected all-zero / zero-heavy signals as advisory evidence;
- missing expected partitions/periods.

Do not automatically equate:

```text
blank
null
zero
not applicable
```

---

# 27. Quality family — type & parse consistency

Implement:

- explicit date parse checks;
- mixed date format detection;
- numeric-as-text detection;
- malformed numeric values;
- decimal/thousands separator consistency;
- percent strings;
- boolean variants;
- encoding issues for files;
- unsupported / unparseable values.

---

# 28. Quality family — formatting consistency

Implement deterministic observations for:

- leading/trailing whitespace;
- case variants;
- label variants;
- unexpected delimiters;
- identifier formatting;
- inconsistent category spelling.

Do not automatically merge semantically ambiguous categories.

---

# 29. Quality family — numeric/domain validity

Support provider-/contract-specific rules.

Examples:

- negative spend;
- negative impressions;
- impossible rates;
- NaN / infinity;
- invalid date ranges;
- future media delivery;
- missing currency;
- invalid geo values;
- provider-specific metric relationship checks.

Do not encode naive universal assumptions.

---

# 30. Quality family — temporal integrity

Implement:

- missing expected dates/periods;
- overlapping periods;
- duplicate partitions;
- future dates;
- late arrivals;
- historical revisions;
- stale source intervals;
- continuity gaps.

Critical invariant:

```text
UNKNOWN / MISSING != ZERO
```

Never synthesize zero media merely because expected data has not arrived.

---

# 31. Quality family — referential integrity

Where provider/data contracts support hierarchy:

- account;
- campaign;
- ad group / line item;
- creative;
- advertiser;
- geo;
- orders/order items;
- store/region;
- product hierarchy.

Report orphans and missing parent references.

---

# 32. Quality family — reconciliation

Support deterministic reconciliation when comparison controls exist:

- source file total vs staging;
- source BQ vs canonical;
- source spend vs provider control total;
- source revenue vs finance control;
- pre-transform vs post-transform;
- source-interface view vs materialized output.

Use explicit tolerance contracts.

Do not claim reconciliation if no control exists.

---

# 33. Quality family — drift

Persist baseline observations and detect:

- field added/removed;
- type change;
- schema fingerprint change;
- null-rate shift;
- row-volume collapse/spike;
- category-cardinality shift;
- new/removed categories;
- currency/unit drift;
- geo coverage drift;
- freshness drift.

Drift is ongoing operational evidence, not one-time onboarding.

---

# 34. Quality statuses

Use deterministic states:

```text
PASS
REVIEW
BLOCKER
UNKNOWN
SKIPPED_NOT_APPLICABLE
```

Do not create an opaque score as the authoritative state.

A summary score may exist later only as a convenience layer.

---

# 35. Consequence classes

Use typed consequence:

```text
FOUNDATION_BLOCKER
SOURCE_BLOCKER
PREMODEL_BLOCKER
PREMODEL_REVIEW
ADVISORY
```

Examples:

```text
duplicate spend grain keys
→ SOURCE_BLOCKER
```

```text
media national-only while KPI is DMA
→ PREMODEL_REVIEW
```

---

# 36. Agentic interpretation boundary

Quality checks produce deterministic findings.

The agent may:

- explain;
- prioritize;
- use provider knowledge;
- generate bounded root-cause hypotheses;
- recommend a predefined transform/action;
- ask a business question.

The agent may not:

- modify a check result;
- mark a blocker resolved;
- invent an observed count;
- supply arbitrary transformation SQL;
- convert UNKNOWN to PASS;
- convert missing to zero.

Persist:

```text
observed_fact
agent_interpretation
```

separately.

---

# 37. Transformation catalog

Implement a typed catalog of deterministic transformation actions.

Suggested IDs/classes:

| ID | Transformation | Default authority |
|---|---|---|
| DF-T001 | Trim deterministic whitespace | AUTO_SAFE |
| DF-T002 | Normalize approved blank representation to NULL | AUTO_SAFE |
| DF-T003 | Parse/normalize dates using explicit format | AUTO_SAFE |
| DF-T004 | Safe numeric parsing using explicit locale/format | AUTO_SAFE |
| DF-T005 | Provider unit conversion, e.g. micros→currency | AUTO_SAFE when registry-backed |
| DF-T006 | Remove exact duplicate rows | AUTO_SAFE |
| DF-T007 | Remove verified connector reissues by approved key/revision | AUTO_SAFE only after deterministic proof |
| DF-T008 | Apply explicit category/label mapping | AUTO_SAFE when mapping is unambiguous |
| DF-T009 | Normalize timezone using explicit source timezone | AUTO_SAFE |
| DF-T010 | Normalize validated geo codes using approved mapping | AUTO_SAFE |
| DF-T011 | Aggregate to required grain using summable fields | APPROVAL_REQUIRED if detail is lost |
| DF-T012 | Union a compatible recurring file series | AUTO_SAFE after schema proof |
| DF-T013 | Historical Drive backfill + ongoing BQ precedence | APPROVAL_REQUIRED |
| DF-T014 | Currency conversion across currencies | APPROVAL_REQUIRED / USER_REQUIRED |
| DF-T015 | Resolve ambiguous business-key dedupe | USER_REQUIRED |
| DF-T016 | Resolve overlapping promotion semantics | USER_REQUIRED |
| DF-T017 | Apply registry-backed late-arrival watermark | AUTO_SAFE |
| DF-T018 | Align additive schema versions | AUTO_SAFE if lossless |
| DF-T019 | Drop semantic fields to force compatibility | NOT_RECOMMENDED by default |
| DF-T020 | Fill unknown media periods with zero | NOT_RECOMMENDED |
| DF-T021 | Fabricate lower-grain rows from aggregate history | NOT_RECOMMENDED |
| DF-T022 | Reject duplicate file fingerprint from reingestion | AUTO_SAFE |

This table may be adjusted, but authority must remain explicit.

---

# 38. Transformation authority

Use:

```text
AUTO_SAFE
APPROVAL_REQUIRED
USER_REQUIRED
NOT_RECOMMENDED
```

The default authority is owned by deterministic policy/registry.

The agent cannot promote an action to `AUTO_SAFE`.

---

# 39. Transformation Plan

Create:

```text
TransformationPlan
```

It must include:

- plan ID/version;
- source fingerprint;
- registry/contract version;
- actions;
- authority;
- reason/finding IDs;
- source/target grain;
- fields affected;
- projected row effects where deterministically calculable;
- lossiness flag;
- missingness behavior;
- reconciliation checks required;
- required approval;
- output target;
- rollback/immutability behavior.

Plans are immutable once approved.

Material changes create a new plan version.

---

# 40. Transformation Preview

Before mutation, compile:

```text
TransformationPreview
```

Example machine contract:

```text
input_rows
input_schema_fingerprint
input_content_fingerprint
actions[]
projected_output_rows
projected_schema
projected_grain
preserved_unknowns[]
warnings[]
requires_user_decision[]
```

No mutation occurs during preview.

Where exact output counts require executing a transform, execute in an isolated temporary/staging context without promotion and fingerprint the preview result.

---

# 41. Raw immutability

Never update customer source tables/files in place.

Architecture:

```text
CUSTOMER SOURCE
read-only / immutable
        ↓
SOURCE INTERFACE
        ↓
PREM3 STAGING
versioned deterministic cleanup
        ↓
CANONICAL FOUNDATION
governed evidence
```

Drive raw files remain unchanged.

Existing customer BQ tables remain unchanged unless an explicit future feature says otherwise.

---

# 42. Transform execution

Transform executor accepts:

```text
approved_plan_id
action_ids
```

not free-form parameters from the agent.

Server retrieves the pinned plan.

Executor must verify:

- current source fingerprint matches approved plan;
- approval is current;
- action authority allows execution;
- required user decisions exist;
- destination is server-authorized;
- raw source is not destination;
- plan dependencies are satisfied.

Fail closed on mismatch.

---

# 43. Transform idempotency

Required:

- same source fingerprint + same plan version must not duplicate outputs;
- repeated execution returns prior successful receipt or safely verifies output;
- changed source fingerprint invalidates stale preview/approval;
- changed plan version requires new approval;
- file same name + different fingerprint becomes a new version, not silent overwrite.

---

# 44. Transform validation

After execution, prove:

- output exists;
- output schema matches plan;
- output grain matches plan;
- unique keys satisfy contract;
- expected missingness preserved;
- row delta matches expected behavior;
- amount/control totals reconcile;
- no unauthorized source mutation;
- lineage complete;
- input/output fingerprints persisted.

Only then may action become `APPLIED`.

---

# 45. Drive ingestion pipeline

Implement:

```text
Drive discovery
        ↓
File registration/fingerprint
        ↓
Logical series grouping
        ↓
File quality assessment
        ↓
Transformation Preview
        ↓
Approved ingestion
        ↓
BQ staging
        ↓
Post-load QA
        ↓
Source binding
```

The Drive root is evidence storage, not the analytical source of truth.

---

# 46. Drive file parsers — MVP

Support at minimum:

```text
.csv
.xlsx
```

If Parquet is already supported safely by existing IO primitives, include it.

CSV:

- delimiter detection/contract;
- encoding;
- header;
- blank rows;
- repeated headers.

XLSX:

- workbook/sheet inventory;
- selected sheet contract;
- formula-cell handling;
- merged/header issues;
- types.

Do not silently choose among multiple plausible worksheets.

Surface a `USER_REQUIRED` decision when semantics are ambiguous.

---

# 47. Drive file-series quality

Assess:

- schema fingerprint by file;
- schema versions;
- missing expected periods;
- overlapping periods;
- duplicate file fingerprints;
- duplicate rows across files;
- file freshness;
- naming compliance;
- logical source consistency.

Do not penalize a file merely for a noncanonical original filename.

Naming compliance is advisory when PreM3 can safely register canonical identity.

---

# 48. BigQuery + Drive convergence

Implement source-precedence plans.

Example:

```text
Drive history
2024-01-01 → 2025-12-31

BigQuery ongoing
2026-01-01 → present
```

Create a typed `SourceContinuityPlan`.

It must define:

- historical source;
- ongoing source;
- cutoff;
- overlap handling;
- reconciliation;
- canonical precedence;
- lineage.

Do not combine automatically if overlapping data disagree.

---

# 49. BigQuery Foundation provisioning

Implement deterministic planning/execution for:

```text
prem3_modeling
```

Do not create a GCP project.

Provision inside the approved customer project.

At minimum support plans for:

- dataset;
- tables;
- views;
- scheduled queries;
- routines/UDFs when required;
- labels/descriptions;
- source registry tables;
- quality/health tables;
- receipts/lineage tables;
- canonical measurement assets.

---

# 50. Suggested MVP BigQuery assets

Do not create empty architecture for its own sake.

Create only assets actually used by the implemented workflow.

Likely contracts:

```text
source_registry
source_health
source_refresh_log
data_contracts
quality_findings
lineage_edges
transformation_receipts
foundation_receipts
```

Canonical data layers may use explicit naming:

```text
src_<provider_or_role>_*
stg_<provider_or_role>_*
canonical_media
canonical_kpi
canonical_treatments
canonical_controls
canonical_population
```

Future engine-specific views may be added later.

Do not duplicate existing model-consumption tables unnecessarily.

---

# 51. Infrastructure plan actions

Use:

```text
REUSE
CREATE
CHANGE
CUSTOMER_MANAGED
```

Each plan action includes:

- resource type;
- fully resolved server-side target;
- reason;
- dependencies;
- permission requirements;
- cost/risk metadata where available;
- validation method.

---

# 52. Foundation Plan

Create:

```text
FoundationPlan
```

Five sections:

```text
INFRASTRUCTURE
SOURCES_AND_TRANSFERS
QUALITY_AND_TRANSFORMATIONS
CANONICAL_ASSETS
GOVERNANCE_AND_OBSERVABILITY
```

Plan is immutable.

Persist a fingerprint.

Approval binds to exact plan ID/version/fingerprint.

---

# 53. Plan safety

Reapproval required when material plan fields change, including:

- project/dataset;
- source;
- provider account;
- Drive root;
- permissions;
- transfer schedule;
- backfill window;
- transformation semantics;
- aggregation;
- currency conversion;
- resource creation.

Do not silently apply previous approval.

---

# 54. Guided provider provisioning

Build the general provider-provisioning interface.

For MVP, support at least the plumbing required for the intended DV360 vertical slice if current project credentials/Google APIs make it feasible.

Contract:

```text
ProviderProvisioner
plan()
validate_prerequisites()
execute()
check_status()
validate_first_sync()
```

Provider states:

```text
PLATFORM_ONLY
PREREQUISITE_REQUIRED
PROVISIONING_ELIGIBLE
PLAN_READY
APPROVED
PROVISIONING
FIRST_SYNC
QA_REVIEW
IMPORT_READY
```

Do not claim automated provisioning for providers that require unsupported prerequisites.

---

# 55. DV360 prerequisite boundary

If DTV2 must be provisioned externally:

return structured:

```text
PREREQUISITE_REQUIRED
```

with:

- exact prerequisite;
- provider/account scope required;
- what PreM3 can do afterward.

Do not fake provisioning completion.

---

# 56. Scheduled ingestion / refresh

Create a typed abstraction for recurring ingestion.

For each source persist:

```text
expected_cadence
observed_cadence
latest_expected_period
latest_observed_period
watermark
late_arrival_policy
refresh_owner
```

Never hide a customer-managed pipeline behind a PreM3-managed status.

---

# 57. Source-level `IMPORT_READY`

Implement a deterministic evaluator.

A source may reach `IMPORT_READY` only when required conditions are proven.

At minimum evaluate:

- source binding resolved;
- access verified;
- contract/schema known;
- required fields present;
- no source blockers;
- required transform plan executed;
- post-transform QA passed;
- lineage/provenance complete;
- freshness state known;
- currency/time semantics known;
- source output exists;
- receipt persisted.

Typed non-blocking Pre-Modeling review findings may remain.

Do not reuse `MODEL_READY`.

---

# 58. Environment-level `DATA_FOUNDATION_READY`

Implement a separate deterministic evaluator.

Must prove:

- approved customer project;
- `prem3_modeling` exists;
- required source coverage resolved;
- required sources are `IMPORT_READY` or have explicit allowed exceptions;
- canonical assets exist;
- required governance tables/checks exist;
- first-load source QA passed;
- canonical QA passed;
- current approvals valid;
- unresolved gaps typed;
- receipts accessible.

No LLM can return this state.

---

# 59. Readiness state relationship

Preserve:

```text
CONNECTED
        ↓
SOURCE_DISCOVERED
        ↓
IMPORT_READY
        ↓
DATA_FOUNDATION_READY
        ↓
PRE-MODELING
        ↓
MODEL_READY
```

Do not modify existing `MODEL_READY` semantics in this branch.

---

# 60. Missing data integrity rule

Add explicit tests and guardrails:

```text
MISSING != ZERO
```

If expected source data has not arrived:

- mark period incomplete/unknown;
- source freshness fails;
- source may leave `IMPORT_READY`;
- downstream canonical layer must not synthesize zero delivery unless a separately proven business rule says zero.

This is a critical product invariant.

---

# 61. Cross-source alignment

Implement a deterministic:

```text
CrossSourceAlignmentAssessment
```

Support:

- common temporal window;
- KPI/media overlap;
- timezone compatibility;
- currency compatibility;
- geo compatibility;
- grain compatibility;
- source overlap/double-count risk;
- treatment/media overlap;
- provider source version conflicts.

Output typed `PREMODEL_REVIEW` findings where appropriate.

Data Foundation observes compatibility.

Pre-Modeling decides model suitability.

---

# 62. Receipts

Create durable typed receipts.

At minimum:

```text
SourceAssessmentReceipt
DataQualityReceipt
TransformationReceipt
DriveImportReceipt
FoundationProvisioningReceipt
DataFoundationReadyReceipt
```

Every receipt includes:

- tenant/workspace/project context reference;
- source IDs;
- plan/version;
- input fingerprints;
- output fingerprints;
- rule versions;
- counts/checks;
- timestamp;
- identity that executed;
- status;
- unresolved findings.

---

# 63. Persistence

Follow the existing project philosophy:

> meaningful state must be durable.

If the shared Firestore/control-plane repository is available on current `main`, use it for control-plane objects.

Otherwise:

- define repository ports;
- persist evidence/receipts using the existing durable artifact approach for this branch;
- avoid creating a competing control-plane implementation;
- document how to wire to the in-flight control-plane branch.

BigQuery should remain the governed measurement/data plane.

Do not use process memory as truth.

---

# 64. Monitoring

Implement an evaluation service capable of re-running operational/quality checks.

Monitor:

- auth revoked;
- source unavailable;
- stale source;
- transfer/job failure;
- missing partitions;
- schema change;
- null-rate drift;
- row-volume drift;
- category drift;
- currency/unit drift;
- geo drift;
- duplicate recurrence;
- file-series missing period.

Monitoring must reuse the same deterministic quality contracts used at onboarding.

---

# 65. Re-evaluation behavior

When monitoring finds a blocker:

- persist new finding;
- update source health;
- invalidate `IMPORT_READY` if policy requires;
- reevaluate `DATA_FOUNDATION_READY`;
- do not delete prior receipts;
- preserve historical state transitions.

A prior receipt proves what was true then, not what is true now.

---

# 66. Agent integration

Do not begin by creating a new free-form agent.

First implement deterministic services.

Then expose narrowly scoped agent tools such as:

```text
inspect_data_foundation
list_source_findings
request_quality_explanation
propose_registered_transformation
request_business_clarification
```

Mutating agent tools should accept IDs only:

```text
foundation_plan_id
transformation_plan_id
finding_id
source_id
```

not arbitrary SQL/paths/parameters.

---

# 67. Agent outputs

The agent can build a Data Intelligence Brief from structured evidence.

It cannot determine:

```text
PASS
BLOCKER
IMPORT_READY
DATA_FOUNDATION_READY
```

Those are deterministic.

Persist observation vs interpretation separately.

---

# 68. API/service surface

Frontend implementation is not part of this branch, but backend contracts must be consumable later.

Create a clean `DataFoundationService`.

Suggested operations:

```text
get_overview()
list_connections()
discover()
get_evidence_requirements()
list_source_candidates()
bind_source()
assess_source()
get_quality_overview()
get_source_assessment()
get_cross_source_alignment()
compile_transformation_plan()
get_transformation_preview()
resolve_user_decision()
compile_foundation_plan()
approve_plan()
execute_plan()
get_provisioning_status()
get_receipts()
evaluate_data_foundation_ready()
reevaluate_health()
```

If the canonical HTTP API runtime has landed on `main`, expose routes through it.

If it has not landed, do **not** create a competing standalone API service solely for this branch.

Instead publish typed service contracts and an integration note.

---

# 69. Schema/export contracts

All user-facing Data Foundation contracts should be Pydantic models and JSON-serializable.

If the repo's schema-export mechanism exists on `main`, include these contracts in it.

Do not hand-maintain duplicate frontend types.

---

# 70. Recommended core models

At minimum:

```text
EvidenceRequirement
EvidenceRequirementSet

DataConnection
BigQueryConnectionBinding
DriveConnectionBinding
DriveRootBinding

SourceCandidate
SourceBinding
SourceContract
SourceCoverageInventory

OperationalHealthAssessment
ContractStructureAssessment
DataQualityAssessment
MeasurementCoverageAssessment
SourceAssessment

QualityCheckResult
QualityFinding
QualityOverview
CrossSourceAlignmentAssessment

TransformationAction
TransformationPlan
TransformationPreview
TransformationExecutionReceipt

FoundationPlanAction
FoundationPlan
FoundationApproval
ProvisioningStep
ProvisioningRun

SourceAssessmentReceipt
DataQualityReceipt
DriveImportReceipt
FoundationProvisioningReceipt
DataFoundationReadyReceipt
```

Avoid giant untyped dictionaries.

---

# 71. Testing strategy

This branch requires substantial deterministic tests.

Use:

```text
tests/unit/data_foundation/
tests/integration/data_foundation/
tests/fixtures/data_foundation/
```

where practical.

---

# 72. Quality-engine unit tests

Cover all mandatory families:

- exact duplicates;
- key duplicates;
- nulls;
- blanks;
- empty columns;
- type parse;
- mixed dates;
- numeric parse;
- formatting;
- domain rules;
- temporal gaps;
- overlap;
- late arrivals;
- referential integrity;
- reconciliation;
- schema drift;
- null-rate drift;
- row-volume drift;
- category drift.

Every rule should have:

- pass fixture;
- fail fixture;
- boundary fixture.

---

# 73. Transformation tests

For each transformation:

- source input unchanged;
- deterministic output;
- idempotency;
- expected row change;
- expected schema;
- provenance/fingerprint;
- fail closed on invalid parameter/contract;
- correct authority.

---

# 74. Negative transformation tests

Must prove:

- unapproved plan cannot execute;
- changed source fingerprint invalidates plan;
- ambiguous dedupe cannot auto-run;
- unsupported currency conversion cannot auto-run;
- missing data not zero-filled;
- aggregate source cannot be fabricated into lower-grain detail;
- source destination cannot equal raw source;
- agent cannot pass arbitrary SQL;
- agent cannot choose arbitrary output path.

---

# 75. Drive tests

Must prove:

- access outside bound root rejected;
- root creation idempotent;
- wrong-folder files remain unregistered until classified;
- same fingerprint is not ingested twice;
- same filename + changed fingerprint is versioned;
- file-series grouping deterministic given same evidence;
- original filename preserved;
- logical canonical identity stable;
- schema-version detection works;
- overlapping file periods detected;
- rejected files never enter canonical layer.

---

# 76. BigQuery discovery tests

Use mocks/emulators/fixtures where possible.

Prove:

- metadata-first;
- candidate shortlist;
- no unbounded `SELECT *` discovery;
- identifier validation;
- project/dataset scope enforced;
- query budget enforced;
- partition predicate compiled where required;
- dry-run/budget failure fails closed.

---

# 77. BigQuery provisioning tests

Prove:

- dataset creation idempotent;
- existing compatible resource → REUSE;
- incompatible resource → CHANGE/REVIEW, not overwrite;
- labels/descriptions preserved/validated;
- table/view contracts verified after creation;
- scheduled queries verified;
- first load read-back proof;
- no GCP project creation.

---

# 78. Approval tests

Prove:

- approval bound to exact plan fingerprint;
- plan change invalidates approval;
- approval cannot be reused across workspace/project/source;
- partial approval obeys dependency graph;
- stale approval fails closed.

---

# 79. Readiness tests

`IMPORT_READY`:

- pass happy path;
- source blocker fails;
- unknown semantic decision fails;
- allowed `PREMODEL_REVIEW` can pass if policy permits;
- missing receipt fails;
- freshness unknown fails where required.

`DATA_FOUNDATION_READY`:

- happy path;
- missing `prem3_modeling` fails;
- required source not import-ready fails;
- allowed unavailable source with typed exception behaves per policy;
- canonical QA failure fails;
- monitoring/governance missing fails if required;
- no pathway allows LLM string to force readiness.

---

# 80. Multi-tenant / authority negative tests

If tenant/control-plane context exists on main:

- cross-tenant source access denied;
- cross-tenant plan execution denied;
- Drive root from other tenant denied;
- BQ project from other tenant denied;
- agent cannot override server-owned context.

If that context is not yet merged, write these as integration expectations in the parallel integration note rather than building a second tenant subsystem.

---

# 81. Regression protection

Existing:

```text
profiling
remediation
provenance
BigQuery publish/parity
MODEL_READY
Meridian EDA
```

must continue to pass.

This branch must not weaken existing Dataset A golden proofs.

Run the existing applicable test suite before PR.

---

# 82. Suggested implementation order

## Phase A — review + contracts

- current-state review;
- branch;
- package skeleton;
- enums/contracts;
- repository/adapter ports.

## Phase B — connections + discovery

- BQ binding;
- Drive binding/root;
- BQ metadata discovery;
- Drive inventory;
- evidence requirements;
- provider matching;
- source candidates.

## Phase C — deterministic source assessment

- four pillars;
- quality engine;
- quality overview;
- cross-source alignment.

## Phase D — Transformation Preview

- catalog;
- plan;
- authority;
- preview;
- immutable source guarantee.

## Phase E — deterministic transform execution

- safe transforms;
- Drive file ingestion;
- source-interface/staging output;
- post-transform QA;
- receipts.

## Phase F — Foundation Plan / provisioning

- BQ dataset/assets;
- recurring ingestion abstractions;
- Drive→BQ materialization;
- plan approval;
- deterministic executor;
- read-back proof.

## Phase G — readiness + operations

- `IMPORT_READY`;
- `DATA_FOUNDATION_READY`;
- health monitoring;
- drift;
- reevaluation.

## Phase H — agent/service integration

- typed service surface;
- narrow agent tools;
- Data Intelligence Brief evidence payload;
- API wiring only if canonical API runtime exists on main.

---

# 83. MVP priority split

## P0 — must ship in this branch

- branch/review discipline;
- typed contracts;
- BQ + Drive binding abstractions;
- Drive root enforcement;
- evidence requirements;
- BQ metadata discovery;
- Drive file discovery;
- provider registry matching;
- Source Coverage Inventory;
- deterministic quality engine;
- duplicate/null/type/format/temporal tests;
- Source Assessment;
- cross-source alignment;
- Transformation Plan + Preview;
- core safe transforms;
- raw immutability;
- Drive→BQ staging ingestion;
- BigQuery `prem3_modeling` provisioning;
- source/canonical QA;
- receipts;
- `IMPORT_READY`;
- `DATA_FOUNDATION_READY`;
- missing != zero invariant;
- deterministic tests.

## P1 — ship if time allows, but architecture must support

- DV360 executable provisioner;
- richer provider-specific health contracts;
- referential checks for more providers;
- external control reconciliation;
- comprehensive recurring monitors;
- additional Drive file formats;
- richer scheduled-query/routine generation;
- advanced lineage inference from job history.

Do not let P1 prevent P0 correctness.

---

# 84. Explicit non-goals

Do not implement in this branch:

- Business IQ UI;
- Data Foundation UI;
- Pre-Modeling EDA changes;
- Meridian model fitting;
- optimization;
- MTA engine;
- forecasting engine;
- new foundation-model training;
- broad Google Drive crawling;
- arbitrary SQL agent;
- autonomous business-semantic decisions;
- GCP project creation;
- campaign management;
- budget changes;
- bidding changes;
- source overwrite;
- silent imputation;
- zero-filling missing media;
- uncontrolled self-learning.

---

# 85. Required proof fixtures

Create representative Data Foundation fixtures.

At minimum:

## Fixture 1 — clean BigQuery-like source

Passes import checks.

## Fixture 2 — Meta/Fivetran duplicate reissue

- duplicate business keys;
- revision timestamps;
- deterministic dedupe proof.

## Fixture 3 — promotion calendar

- overlapping dates;
- mixed discount formatting;
- requires business decision.

## Fixture 4 — Drive monthly file series

- 12 files;
- two schema versions;
- overlapping rows;
- canonical logical grouping.

## Fixture 5 — missing vs zero

- stale source;
- latest periods absent;
- prove no zero synthesis.

## Fixture 6 — Drive history + BQ ongoing

- backfill continuity plan;
- overlap/reconciliation.

---

# 86. Required observable proof

The final PR should contain a deterministic proof script or integration fixture that demonstrates:

```text
BUSINESS REQUIREMENTS LOADED
        ↓
BQ + DRIVE DISCOVERY
        ↓
SOURCE CANDIDATES
        ↓
SOURCE ASSESSMENTS
        ↓
QUALITY FINDINGS
        ↓
TRANSFORMATION PREVIEW
        ↓
APPROVED TEST PLAN
        ↓
TRANSFORM EXECUTION
        ↓
BQ STAGING/CANONICAL OUTPUT
        ↓
POST-TRANSFORM QA
        ↓
IMPORT_READY
        ↓
FOUNDATION PLAN
        ↓
PROVISION / VERIFY
        ↓
DATA_FOUNDATION_READY
```

No fabricated status strings.

---

# 87. Proof expectations

Produce machine-readable proof under a new documented fixture/evaluation path.

Suggested:

```text
evaluation/data_foundation_mvp_proof.json
```

or equivalent.

Include:

- base main SHA;
- feature SHA;
- source fingerprints;
- quality findings;
- transform plan;
- before/after row counts;
- reconciliation;
- BQ contract proof using mocks/local if live cloud not available;
- readiness receipts.

Do not fabricate live cloud proof.

---

# 88. Cloud proof

If customer-like GCP proof is executed:

- use authorized dev/test project only;
- no production customer data;
- no service-account key files;
- no broad IAM;
- record exact project/resources;
- prove resources read back after creation;
- prove Drive root scope behavior;
- prove BQ read/write through intended identity;
- do not claim success from API 200 alone.

If cloud access is unavailable, mark:

```text
LIVE_CLOUD_PROOF_NOT_RUN
```

and keep local deterministic proof honest.

---

# 89. CI / verification

Before PR:

```bash
python -m ruff check app tests scripts
python -m pytest tests/unit
python -m pytest tests/integration -k "not meridian_eda"
python -m pytest tests/regression
python scripts/precloud_check.py
```

Adjust interpreter invocation to repo-supported environment.

Add focused Data Foundation test commands to the PR body.

Do not skip existing regression tests because this is a separate workstream.

---

# 90. PR requirements

Open a PR from:

```text
feature/prem3-data-foundation-backend
```

to:

```text
main
```

PR title recommendation:

> **Build governed PreM3 Data Foundation runtime**

PR body must include:

- main SHA used as base;
- current-state review summary;
- parallel-branch overlap notes;
- architecture;
- new contracts;
- deterministic quality families;
- transformation authority model;
- Drive root boundary;
- BigQuery scope;
- receipts/readiness;
- tests;
- live-cloud proof status;
- explicit non-goals;
- migration/integration notes for the other backend branch.

---

# 91. Merge conflict discipline

Before asking for merge:

```bash
git fetch origin
git rebase origin/main
```

Resolve conflicts carefully.

If parallel backend work lands and introduces:

- TenantContext;
- ExecutionContext;
- Firestore repositories;
- prem3-api service;
- OAuth services;
- contract schema export;

adapt Data Foundation to those canonical systems.

Do not preserve duplicate implementations merely to avoid conflict.

Run full tests after rebase.

---

# 92. Stop conditions

Stop and report before proceeding if any of these occur:

- branch not based on current `main`;
- canonical auth/control-plane integration cannot be determined;
- Drive authorization would require broad unbounded access without server-enforced root binding;
- required transformation cannot be expressed deterministically;
- source identity is ambiguous but no human decision exists;
- proposed transform would overwrite raw data;
- proposed transform fabricates detail;
- unknown media would be converted to zero;
- `IMPORT_READY` would depend on agent prose;
- `DATA_FOUNDATION_READY` would depend on agent prose;
- plan approval cannot be bound to exact immutable plan version;
- project/dataset authority is caller-controlled rather than server-controlled;
- live cloud proof cannot be distinguished from fixture proof.

Do not “make the demo pass” by weakening these boundaries.

---

# 93. Engineering north star

The completed backend should make this product experience truthful:

> **PreM3 knew what data should exist from Business IQ, found the likely evidence across authorized BigQuery and Google Drive, deterministically tested whether that evidence was structurally trustworthy, used the agent only to explain and resolve ambiguity, previewed exact cleanup actions, executed only approved transformations, preserved raw evidence, built the governed `prem3_modeling` foundation, and independently proved the resulting sources and environment were ready for Pre-Modeling.**

The backend loop is:

```text
BUSINESS REQUIREMENTS
        ↓
AUTHORIZED RESOURCE BINDINGS
        ↓
METADATA-FIRST DISCOVERY
        ↓
REGISTRY EVIDENCE
        ↓
SOURCE BINDING
        ↓
DETERMINISTIC QUALITY
        ↓
AGENT INTERPRETATION
        ↓
HUMAN SEMANTIC DECISION
        ↓
PINNED TRANSFORMATION PLAN
        ↓
PREVIEW
        ↓
APPROVED DETERMINISTIC EXECUTION
        ↓
POST-TRANSFORM PROOF
        ↓
IMPORT_READY
        ↓
FOUNDATION PLAN
        ↓
PROVISION + READ-BACK
        ↓
DATA_FOUNDATION_READY
        ↓
CONTINUOUS HEALTH
```

Preserve the governing principles:

> **Raw input is immutable.**

> **Every transformation has provenance.**

> **Missing is not zero.**

> **The agent recommends; deterministic code proves.**

> **Data Foundation proves evidence is trustworthy and reproducible. Pre-Modeling determines whether that evidence can support the intended model.**
