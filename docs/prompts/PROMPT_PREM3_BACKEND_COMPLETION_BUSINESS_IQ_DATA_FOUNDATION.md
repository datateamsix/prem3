# BACKEND COMPLETION PROMPT — Business IQ + Data Foundation
## Close the Design-to-Backend Contract Before Commit / PR

**Repository:** `datateamsix/prem3`  
**Existing working branch:** `feature/prem3-data-foundation-backend`  
**Do not create another feature branch unless branch-base repair requires it.**  
**Goal:** Backend-complete support for all data-bearing Business IQ and Data Foundation MVP mock-ups and approved refinement specs.

---

# 0. Current status

The first Data Foundation implementation pass reports:

- isolated `app/data_foundation/`;
- typed `DataFoundationContext`;
- Business IQ snapshot → evidence requirements;
- metadata-first BigQuery discovery;
- bounded SQL/query budget;
- bound `prem3-modeling` Drive root;
- deterministic quality engine;
- immutable/pinned transformations;
- approval-bound Foundation Plans;
- `prem3_modeling` provisioning;
- workspace-scoped API;
- deterministic proof and tests.

Treat that as the **foundation**, not the final completion state.

The finish line for this branch is now:

> **Every data-bearing interaction, state, finding, preview, lifecycle object, and readiness concept visible in the current Business IQ + Data Foundation MVP designs has an explicit backend contract, durable source of truth, API/service operation, authority rule, and test.**

---

# 1. Branch provenance is a release blocker

The branch was reported as created from Mission 11 at:

```text
02cec50
```

The original requirement was to branch from current `origin/main`.

Before committing:

```bash
git fetch origin --prune
git rev-parse origin/main
git merge-base origin/main HEAD
git log --oneline --decorate --graph --max-count=30
```

Determine whether the branch is actually based on the current main lineage.

If `02cec50` is not current `origin/main` or a valid descendant incorporating it:

1. preserve the current working tree safely;
2. rebase onto current `origin/main` or recreate the feature branch from `origin/main`;
3. reapply the work;
4. rerun tests.

Do **not** open a PR with ambiguous branch ancestry.

Document:

```text
base_main_sha
feature_branch_base_sha
branch_repair_required
```

in the PR.

---

# 2. Create a Design Support Matrix before more implementation

Add:

```text
docs/backend/BUSINESS_IQ_DATA_FOUNDATION_DESIGN_SUPPORT_MATRIX.md
```

For every current Business IQ + Data Foundation screen/component, record:

| UX capability | Backend contract | Source of truth | API/service operation | Deterministic vs agentic | Status | Tests |
|---|---|---|---|---|---|---|

Use:

```text
IMPLEMENTED
PARTIAL
MISSING
EXTERNAL_DEPENDENCY
```

No current mock-up behavior may remain implicit.

This matrix is the acceptance artifact for backend completeness.

---

# 3. Business IQ is currently incomplete

The current implementation reportedly only consumes:

```text
BusinessProfileSnapshot → EvidenceRequirementSet
```

and provides no Business IQ persistence.

That is insufficient for the current product.

Business IQ must become a first-class durable backend domain.

Do not implement Business IQ UI in this branch.

Implement its **data/services/contracts**.

---

# 4. BusinessProfile

Implement durable, workspace-scoped:

```text
BusinessProfile
```

Required high-level domains:

```text
business_identity
measurement_objective
markets
customer_journey
marketing_portfolio
decision_process
commercial_drivers
competition
business_events
prior_evidence
open_questions
profile_metadata
```

Preserve custom text rather than coercing unsupported answers to `OTHER`.

---

# 5. BusinessProfile versioning

Business IQ is not a mutable singleton with no history.

Support:

```text
BusinessProfileVersion
BusinessProfileSnapshot
```

Every material edit creates or advances a version.

Persist:

```text
profile_id
version
workspace_id
created_at
updated_at
updated_by
schema_version
fingerprint
```

Historical Measurement Cycles must be able to reference the exact profile snapshot that applied at the time.

---

# 6. Business fact provenance

Implement a typed fact/provenance model.

Suggested:

```text
BusinessFact
```

with:

```text
fact_id
concept
value
source_type
source_reference
status
created_at
confirmed_at
```

User-facing provenance should support concepts equivalent to:

```text
PROVIDED_BY_USER
FROM_USER_DESCRIPTION
DETECTED_IN_DATA
CONFIRMED_BY_USER
INFERRED_NEEDS_CONFIRMATION
UNKNOWN_ACKNOWLEDGED
```

Do not merge business fact provenance with readiness.

---

# 7. MarketingMix / channel lifecycle

Business IQ must persist a durable marketing portfolio.

Implement a channel object that separates:

```text
business channel
```

from:

```text
provider/platform
```

Suggested:

```text
MarketingChannel
```

with:

```text
channel_id
canonical_name
custom_name
business_roles[]
markets[]
active_from
active_to
lifecycle_status
```

Lifecycle support:

```text
DECLARED
ACTIVE
PAUSED
RETIRED
```

Provider bindings remain Data Foundation objects.

This effective dating is required by Coverage & Continuity.

---

# 8. Commercial drivers / events

Persist structured:

```text
CommercialDriver
BusinessEvent
```

with effective dates / approximate periods where available.

Examples:

- promotions;
- pricing;
- seasonality;
- inventory constraints;
- launches;
- distribution changes;
- competition;
- channel launch/pause.

These objects must be consumable by Data Foundation evidence requirements.

---

# 9. Prior evidence

Implement durable:

```text
PriorEvidenceReference
```

Support:

- evidence type;
- description;
- channel;
- market;
- period;
- KPI;
- optional Drive/file reference;
- provenance;
- availability state.

Do not convert prior evidence into Bayesian distribution parameters automatically.

---

# 10. Business IQ readiness

Implement deterministic:

```text
BUSINESS_CONTEXT_READY
```

The exact UX does not require every ontology field to be populated.

Explicit:

```text
UNKNOWN_ACKNOWLEDGED
```

may satisfy a concept being addressed.

Do not use raw questionnaire completeness percentage as the authority.

---

# 11. Business Intelligence Brief

The profile review screen contains agentic synthesis.

Backend must support a grounded artifact such as:

```text
BusinessIntelligenceBrief
```

Sections:

```text
plain_language_summary
what_matters_most
modeling_considerations
forecasting_considerations
open_questions
next_evidence_requirements
```

Every generated insight must reference:

```text
BusinessFact IDs
```

and/or deterministic business-profile fields.

Persist:

```text
profile_snapshot_id
generated_at
model/version
evidence_refs[]
```

The brief is advisory.

It cannot change BusinessProfile facts.

---

# 12. Business IQ update proposals from Data Foundation

Implement:

```text
BusinessProfileUpdateProposal
```

Example:

```text
Data Foundation finds Paid Social gap
        ↓
Business IQ says always-on
        ↓
User confirms intentional pause
        ↓
Update proposal
        ↓
User accepts
        ↓
New BusinessProfileVersion
```

Persist:

```text
previous_fact
observed_evidence
proposed_fact
decision
decided_by
receipt
```

Data Foundation cannot silently rewrite Business IQ.

---

# 13. Business IQ API/service surface

Provide workspace-scoped operations equivalent to:

```text
GET    business profile
CREATE business profile
PATCH  business profile
GET    profile versions
GET    immutable profile snapshot
GET    Business Intelligence Brief
POST   regenerate brief
GET    update proposals
POST   accept/reject proposal
GET    evidence requirements
```

Use the canonical API runtime already in the repository.

Do not create a second API service.

---

# 14. Customer identity metadata

The Business Profile UI displays:

- organization/business name;
- optional customer logo;
- last edited timestamp;
- profile version.

Backend should expose these through the canonical organization/control-plane metadata or BusinessProfile metadata.

Do not duplicate organization identity if Clerk/control plane already owns it.

---

# 15. Data Foundation — add latest Discovery Hint contracts

The new Connect screen supports:

## BigQuery

```text
datasets_to_prioritize[]
only_inspect_prioritized_datasets
```

## Google Drive

```text
drive_sources_or_paths_to_prioritize[]
```

Drive hints must never expand beyond the bound `prem3-modeling` root.

BigQuery strict mode must be enforced by discovery code, not just UI copy.

Persist discovery request/provenance.

---

# 16. Source scope / geography

Discovery and source detail now display:

```text
Scope
```

Implement:

```text
SourceScope
```

Support:

```text
market_scope[]
geo_level
geo_field
geo_values_summary
provenance
```

Provenance may include:

```text
SCHEMA_DETECTED
PROFILE_DETECTED
PROVIDER_METADATA
FILENAME_INFERRED
USER_PROVIDED
BUSINESS_IQ_INFERRED
UNKNOWN
```

Filename inference must not have deterministic authority equal to schema/profile evidence.

---

# 17. Source physical metadata

Every source assessment should expose applicable physical metadata.

For BigQuery:

```text
object_type
exact_or_estimated_row_count
column_count
table_size_bytes
dataset_location
last_modified
partitioning_type
partitioning_field
partition_count
clustering_fields[]
```

For views:

- do not claim physical partition/clustering;
- expose object type and lineage;
- row count may be sampled/observed/unknown.

For Drive logical sources:

```text
file_count
total_rows
schema_versions
column_count
date_range
latest_file_at
folder_path
```

Do not emit meaningless null labels where the concept is not applicable.

---

# 18. Data Preview — mandatory backend capability

Implement reusable:

```text
DataPreview
```

Modes:

```text
SOURCE_PREVIEW
TRANSFORMATION_PREVIEW
CANONICAL_PREVIEW
```

---

# 19. BigQuery source preview

Default behavior:

```text
5 most recent rows
```

only when a verified time field exists.

Compiled deterministic query:

```sql
SELECT <approved columns>
FROM <server-resolved source>
ORDER BY <verified time field> DESC
LIMIT 5
```

Requirements:

- no arbitrary SQL;
- server-resolved table;
- selected safe columns only;
- read only;
- bounded query budget;
- source scope enforced;
- preview query evidence/bytes available.

If no verified time field:

```text
5 sample rows
```

not “most recent.”

---

# 20. Preview sensitive-data policy

A generic `SELECT * LIMIT 5` is not acceptable.

Implement deterministic field safety.

At minimum:

- registry sensitivity hints where available;
- deny/mask obvious emails;
- phones;
- names if customer-level;
- addresses;
- raw user/device identifiers where not required;
- authentication/secrets.

Return:

```text
masked_fields[]
omitted_fields[]
```

Preview must be safe by default.

---

# 21. Drive source preview

For Drive logical file sources:

- preview parsed rows;
- identify contributing file;
- preserve original filename;
- bound row count;
- apply the same sensitive-field policy;
- do not mutate file.

---

# 22. Transformation Preview

The current transform system must return a user-consumable preview contract.

Implement:

```text
TransformationPreview
```

with:

```text
source_preview
proposed_output_preview
actions[]
authority[]
input_row_count
projected_or_preview_output_row_count
row_delta
schema_before
schema_after
grain_before
grain_after
partitioning_proposed
clustering_proposed
unknowns_preserved[]
raw_source_unchanged=true
```

Do not present unresolved `USER_REQUIRED` actions as applied.

---

# 23. Canonical Preview

After execution and validation:

```text
CanonicalPreview
```

must expose:

```text
output_resource
actual_row_count
actual_schema
partitioning
clustering
quality_summary
reconciliation_summary
latest_rows
receipt_id
```

This creates the proof chain:

```text
SOURCE
→ PROPOSED
→ VERIFIED OUTPUT
```

---

# 24. Measurement Cycle — new first-class backend domain

Implement:

```text
MeasurementCycle
```

A customer may run recurring:

```text
Q1 2026 MMM
Q2 2026 MMM
Q3 2026 MMM
```

Required fields:

```text
cycle_id
workspace_id
name
cadence
data_cutoff
target_window_start
target_window_end
target_window_status
business_profile_snapshot_id
created_at
updated_at
state
```

Target window status:

```text
PROVISIONAL
CONFIRMED_DOWNSTREAM
```

Data Foundation must not finalize the model window.

---

# 25. Measurement Cycle cadence

Support:

```text
MONTHLY
QUARTERLY
SEMIANNUAL
ANNUAL
EVENT_BASED
ONE_TIME
CUSTOM
UNKNOWN
```

This is model/measurement refresh cadence, not data-source refresh cadence.

---

# 26. Data cutoff

A cycle needs:

```text
data_cutoff
```

The default should represent the latest **complete** period, not blindly “now.”

Persist whether cutoff was:

```text
DETECTED
USER_SELECTED
```

---

# 27. Provisional target modeling window

Support:

```text
target_window_start
target_window_end
target_window_status=PROVISIONAL
```

A user may:

- provide a target;
- accept a PreM3 recommendation;
- leave it pending until discovery.

Do not encode a universal Meridian history minimum.

Any recommended history target must be advisory with rationale/evidence.

Pre-Modeling later confirms the final model window.

---

# 28. Measurement Cycle version/history

Cycles are durable.

Do not mutate:

```text
Q2 2026
```

into:

```text
Q3 2026
```

Each cycle preserves:

- BusinessProfile snapshot;
- required evidence;
- source coverage;
- assessment findings;
- provisional window;
- later downstream model/window reference.

---

# 29. Effective-dated channel expectations

Coverage logic must use MarketingChannel active periods.

Example:

```text
Streaming Audio
active_from = 2026-04-01
```

Therefore:

```text
2023–Mar 2026
NOT_EXPECTED
```

not:

```text
MISSING
```

This distinction is mandatory.

---

# 30. Coverage & Continuity backend contract

Implement:

```text
CoverageAssessment
```

and:

```text
CoverageSeries
CoverageBucket
CoverageSummary
```

MVP bucket grain:

```text
MONTH
```

Support future weekly.

---

# 31. Coverage bucket states

Required:

```text
VERIFIED_PRESENT
VALID_ZERO
PARTIAL
EXPECTED_BUT_MISSING
UNKNOWN
NOT_EXPECTED
SOURCE_NOT_FOUND
PREM3_PROVIDED
OUTSIDE_TARGET_WINDOW
OVERLAP_UNDER_RECONCILIATION
```

Do not collapse missing and zero.

---

# 32. Coverage inputs

Coverage must derive from:

- Measurement Cycle;
- BusinessProfile snapshot;
- effective-dated channels;
- EvidenceRequirementSet;
- SourceBindings;
- observed time coverage;
- freshness;
- source transitions;
- provider late-arrival policies;
- deterministic quality findings.

---

# 33. Coverage metrics

Calculate:

```text
observed_span
continuous_span
most_recent_continuous_span
longest_gap
latest_observed_period
target_window_coverage
```

At requirement/environment level calculate:

```text
required_sources_meeting_target
continuity_issue_count
shared_continuous_window
shared_continuous_window_start
shared_continuous_window_end
most_limiting_requirement
```

Definitions must be deterministic and documented.

---

# 34. Required Evidence vs All Sources

Coverage API must support:

```text
view=REQUIRED_EVIDENCE
view=ALL_SOURCES
```

Required Evidence is derived from the selected Measurement Cycle's Business IQ snapshot.

Do not infer required channels from all providers discovered.

---

# 35. Source transitions

Implement:

```text
SourceContinuityPlan
```

Example:

```text
Drive Meta history
2024–2025

BigQuery Meta
2026–present
```

Coverage should show one business requirement with a source transition.

Persist:

- source IDs;
- periods;
- precedence;
- overlap;
- reconciliation state.

Unreconciled overlap must not appear as clean verified continuity.

---

# 36. Gap detail contract

Clicking a visual gap requires backend evidence.

Implement:

```text
CoverageGap
```

with categories:

```text
COVERAGE_GAP
SOURCE_FAILURE
BUSINESS_PAUSE
PROVIDER_TRANSITION
PARTIAL_PERIOD
LATE_ARRIVAL
UNKNOWN
```

Include:

```text
period
expected_business_state
observed_data_state
source_health
evidence_refs
recommended_next_action
```

---

# 37. Coverage-triggered Business IQ question

When deterministic evidence conflicts with Business IQ:

```text
CoverageGap
+
BusinessFact
```

may create:

```text
BusinessClarificationRequest
```

Example:

> Was Paid Social intentionally paused during Apr–May 2025?

Answers must update durable state:

- confirmed business pause → BusinessProfileUpdateProposal;
- not paused → Data Foundation quality/coverage issue;
- unknown → preserve unknown.

No chat-only resolution.

---

# 38. Coverage API/service operations

Support operations equivalent to:

```text
create_measurement_cycle
update_measurement_cycle
list_measurement_cycles
get_measurement_cycle

compute_coverage
get_coverage
get_coverage_gap
get_shared_window
get_cycle_requirements
```

Workspace/cycle scoped.

---

# 39. Business IQ + Measurement Cycle relationship

Each cycle pins:

```text
business_profile_snapshot_id
```

If Business IQ changes later:

- future cycles may use the newer snapshot;
- historical cycle remains reproducible;
- current cycle may deliberately create a new cycle revision if product policy allows.

Do not silently replace snapshots.

---

# 40. Business IQ → Data Foundation completeness

The backend should be able to service this full chain:

```text
BusinessProfile
        ↓
BusinessProfileSnapshot
        ↓
BUSINESS_CONTEXT_READY
        ↓
MeasurementCycle
        ↓
EvidenceRequirementSet
        ↓
Data connections
        ↓
Discovery
        ↓
Source candidates
        ↓
Source bindings
        ↓
Source physical metadata
        ↓
Data Preview
        ↓
Source Assessment / Quality
        ↓
Coverage & Continuity
        ↓
Gap clarification
        ↓
Transformation Preview
        ↓
Foundation Plan
        ↓
Execution
        ↓
Canonical Preview
        ↓
IMPORT_READY
        ↓
DATA_FOUNDATION_READY
```

No major mock-up state should be unsupported.

---

# 41. Connection runtime completeness

Before calling the branch backend-complete, determine whether BigQuery and Drive are:

```text
REAL_RUNTIME_ADAPTER
```

or merely:

```text
PORT + TEST DOUBLE
```

The in-memory port is useful for tests but not sufficient for production servicing.

For each integration document:

```text
OAuth/credential owner
connection storage
token refresh
revocation
runtime adapter
root/project binding
live proof status
```

If canonical Google OAuth plumbing already exists, reuse it.

If it exists only on another in-flight branch, document the explicit integration blocker.

Do not fake `CONNECTED` with an in-memory adapter in production runtime.

---

# 42. External connection acceptance rule

For MVP backend completeness:

BigQuery must have a real runtime path for:

- authenticated metadata inspection;
- bounded query execution;
- physical metadata;
- source preview;
- provisioning where authorized.

Google Drive must have a real runtime path for:

- root lookup;
- root creation if approved;
- bounded file inventory;
- file metadata;
- file content read;
- source preview;
- file registration/fingerprint;
- approved ingestion.

If credentials are the only external dependency, mark exactly that.

---

# 43. Exact source-level readiness naming

The product contract is:

```text
IMPORT_READY
```

If internal Data Foundation source state currently says:

```text
READY
```

that is acceptable only as a private internal state.

Public API / receipts / user-facing contract must map unambiguously to:

```text
IMPORT_READY
```

Do not introduce a second ambiguous “Ready” concept.

---

# 44. Agentic briefs must consume structured evidence

Business Intelligence Brief and Data Intelligence Brief may be agent-generated.

They must consume:

```text
typed deterministic/profile evidence
```

and return evidence references.

They cannot become a parallel source of truth.

No brief may set readiness.

---

# 45. Testing — Business IQ

Add tests for:

- create/edit BusinessProfile;
- version increments;
- immutable snapshots;
- custom values preserved;
- UNKNOWN_ACKNOWLEDGED;
- channel active/pause/retire dates;
- profile readiness;
- prior evidence;
- profile update proposal accept/reject;
- intelligence brief evidence references;
- historical snapshots unaffected by future edits.

---

# 46. Testing — discovery refinements

Add tests for:

- prioritization hints;
- strict BQ dataset boundary;
- Drive hints remain inside root;
- source scope/provenance;
- exact vs estimated row count;
- partition/clustering metadata;
- view metadata behavior.

---

# 47. Testing — Data Preview

Prove:

- 5 most recent only with verified time;
- sample behavior without verified time;
- no arbitrary SQL;
- query budget;
- server-resolved resources;
- masked sensitive fields;
- Drive preview bounded;
- no source mutation.

---

# 48. Testing — Coverage & Continuity

Fixtures must include:

## Healthy 36-month coverage

All required evidence continuous.

## Paid Social gap

Expected active, observed missing.

## Valid zero

Rows exist with zero activity; state is `VALID_ZERO`.

## New channel

Streaming Audio begins Apr 2026; prior periods are `NOT_EXPECTED`.

## Stale source

History ends before cycle cutoff.

## Partial period

Expected month partially loaded.

## Drive→BQ source transition

Continuous after reconciliation.

## Overlapping transition

`OVERLAP_UNDER_RECONCILIATION`.

Tests must prove shared window and limiting source.

---

# 49. Testing — cycle versioning

Prove:

```text
Q2 BusinessProfile snapshot != Q3 snapshot
```

where business mix changed.

Q2 remains reproducible.

Streaming Audio can be required in Q3 but absent from Q2 requirements.

---

# 50. Update proof artifact

Expand:

```text
evaluation/data_foundation_mvp_proof.json
```

or create:

```text
evaluation/business_iq_data_foundation_mvp_proof.json
```

The proof should now demonstrate:

```text
BUSINESS PROFILE CREATED
BUSINESS_CONTEXT_READY
PROFILE SNAPSHOT PINNED

MEASUREMENT CYCLE CREATED
PROVISIONAL WINDOW

BQ + DRIVE CONNECTED / BOUND
DISCOVERY HINTS APPLIED

SOURCES DISCOVERED
SCOPE + PHYSICAL METADATA

DATA PREVIEW

QUALITY ASSESSMENT

COVERAGE + CONTINUITY
SHARED WINDOW
GAP CLASSIFICATION

TRANSFORMATION PREVIEW
APPROVED EXECUTION
CANONICAL PREVIEW

IMPORT_READY
DATA_FOUNDATION_READY
```

Live cloud proof remains separately truthful.

---

# 51. Do not commit / PR until the completion review passes

Before commit, the team should return:

```text
A. BRANCH BASE
origin/main SHA
feature merge-base SHA

B. DESIGN SUPPORT MATRIX
0 MISSING P0 capabilities

C. BUSINESS IQ
durable persistence/versioning/API complete

D. DATA FOUNDATION
latest discovery + preview + cycle + coverage contracts complete

E. CONNECTIONS
real adapters vs external dependencies explicitly identified

F. TESTS
all focused + regression suites green

G. PROOF
updated machine-readable proof

H. OPEN GAPS
only explicit P1/non-MVP items
```

Then commit, push, and open the PR.

---

# 52. Finish line

The branch is ready when the backend can truthfully power the current Business IQ and Data Foundation designs without the UI inventing state.

The source-of-truth chain should be:

```text
DURABLE BUSINESS CONTEXT
        ↓
VERSIONED MEASUREMENT CYCLE
        ↓
SERVER-AUTHORIZED DATA CONNECTIONS
        ↓
DETERMINISTIC DISCOVERY
        ↓
INSPECTABLE SOURCE EVIDENCE
        ↓
DETERMINISTIC QUALITY + COVERAGE
        ↓
AGENTIC INTERPRETATION
        ↓
HUMAN SEMANTIC DECISIONS
        ↓
PINNED TRANSFORM / FOUNDATION PLANS
        ↓
APPROVED DETERMINISTIC EXECUTION
        ↓
VERIFIED OUTPUT + RECEIPTS
        ↓
DATA_FOUNDATION_READY
```

The frontend should eventually render backend truth.

It should not have to manufacture:

- Business IQ readiness;
- profile versions;
- source identity;
- scope;
- row counts;
- quality;
- coverage;
- shared windows;
- transformation impact;
- import readiness;
- Data Foundation readiness.

Those belong in the backend.
