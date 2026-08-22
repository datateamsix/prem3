# PROMPT — PreM3 Data Foundation Refinement Pass #2
## Discovery Hints, Breadcrumb Navigation, Rich Source Metadata & Data Preview / Transformation Preview

**Status:** Design refinement addendum  
**Audience:** Product design / UX / mock-up team  
**Applies to:** Canonical `PREM3 DATA FOUNDATION — FINAL DESIGN REFINEMENT SPEC / PROMPT`  
**Purpose:** Refine the Data Foundation experience without changing the previously approved architecture  
**Version:** `data-foundation/design-refinement-2.0`  
**Date:** 2026-08-22

---

# 1. Objective

Apply the following refinements to the existing Data Foundation mock-ups.

Do **not** redesign the overall architecture.

Preserve the approved production model:

```text
CONNECT
    ↓
DISCOVER & ASSESS
    ↓
RESOLVE & PLAN
    ↓
BUILD & VERIFY
    ↓
OPERATE
```

This pass should improve:

1. subflow navigation;
2. discovery targeting before connection;
3. source-level metadata visibility;
4. geography / market awareness;
5. data-quality visibility at discovery time;
6. direct inspection of source data;
7. before/after transformation proof;
8. consistency between source preview, transformation preview, and verified canonical output.

The design principle for this pass is:

> **Whenever PreM3 makes an important claim about a dataset, give the user a short path to inspect the evidence behind it.**

---

# 2. Breadcrumb navigation — retain and standardize

The newly added breadcrumb pattern is approved.

Use breadcrumbs throughout Data Foundation to show the user where they are inside the current subflow.

Example:

```text
Data Foundation / Connect / Connect data stores
```

Discovery:

```text
Data Foundation / Discover & Assess / Discovery
```

Source detail:

```text
Data Foundation / Sources / Paid Search / Data Preview
```

Transformation:

```text
Data Foundation / Sources / Paid Search / Transformation Preview
```

Foundation Plan:

```text
Data Foundation / Resolve & Plan / Foundation Plan
```

## Breadcrumb role

The left rail answers:

> **Where am I in PreM3 overall?**

The breadcrumb answers:

> **Where am I inside the current Data Foundation workflow?**

These are complementary.

## Requirements

- Breadcrumb items should be clickable when navigation is valid.
- Do not show fake hierarchy merely to fill space.
- Preserve user state when navigating backward.
- If a source detail is opened from Discovery, returning should restore the same discovery table/filter state.
- Avoid breadcrumb depth greater than 4 levels unless required.

---

# 3. BigQuery connection card — add optional discovery hints

Before `Connect BigQuery`, add an optional input:

> **Datasets to prioritize — optional**

Supporting copy:

> If you already know where marketing or business data lives, add dataset names to help PreM3 focus discovery. Leave blank and PreM3 will inspect authorized metadata.

Placeholder:

```text
marketing, commerce, crm, analytics
```

After entry, convert values to chips:

```text
[ marketing × ] [ commerce × ] [ crm × ]
```

## Important semantics

These values are **discovery hints**, not source truth.

Default behavior:

```text
Prioritize these datasets first
        ↓
Continue metadata discovery within the authorized project
```

Do not imply that PreM3 will ignore all other authorized datasets unless the user explicitly requests it.

---

# 4. Optional strict BigQuery scope

Consider a secondary control:

```text
□ Only inspect these datasets
```

If selected:

> PreM3 limits discovery to the named datasets.

This control is useful for:

- enterprise privacy;
- very large projects;
- data-owner restrictions;
- cost-conscious discovery.

If enabled, it becomes an actual discovery boundary rather than a prioritization hint.

Use clear wording to distinguish:

```text
PRIORITIZE
vs
ONLY INSPECT
```

---

# 5. Google Drive connection card — add equivalent discovery hints

Before `Connect Google Drive`, add:

> **Folders or sources to prioritize — optional**

Supporting copy:

> If you already know where file-based measurement data lives inside `prem3-modeling`, add source or folder names. Leave blank and PreM3 will inspect the authorized root.

Possible placeholder:

```text
Meta Ads, promotions, experiments
```

or path-oriented:

```text
sources/meta_ads, business_data/promotions, evidence/experiments
```

The interface may support natural-language source names and normalize them after connection.

Example chips:

```text
[ Meta Ads × ]
[ Promotions × ]
[ Experiments × ]
```

---

# 6. Drive discovery hints never broaden authorization

Drive hints apply **only inside the authorized `prem3-modeling` root**.

They do not grant access to:

- unrelated folders;
- customer My Drive root;
- shared drives outside the approved root;
- arbitrary file paths.

The design should preserve:

> **PreM3 only looks inside the authorized `prem3-modeling` repository.**

---

# 7. Connect screen refinement

Suggested visual composition:

```text
CONNECT YOUR DATA ENVIRONMENT

┌────────────────────────────────────┐
│ BigQuery                           │
│ REQUIRED                           │
│                                    │
│ Governed analytical foundation     │
│                                    │
│ Datasets to prioritize — optional  │
│ [ marketing, commerce, crm      ]  │
│                                    │
│ [ Connect BigQuery ]               │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│ Google Drive                       │
│ OPTIONAL                           │
│                                    │
│ Controlled raw / file evidence     │
│                                    │
│ Sources/folders to prioritize      │
│ [ Meta Ads, promotions          ]  │
│                                    │
│ [ Connect Google Drive ]           │
└────────────────────────────────────┘
```

Preserve the current explanation of:

```text
DISCOVERY ACCESS · NOW
FOUNDATION-MANAGEMENT · LATER
```

This remains an important trust pattern.

---

# 8. Discovery table — add Scope

The Discovery / Source Coverage table should add a `Scope` column.

Use **Scope** rather than only `Geo`, because the value may describe:

- market;
- geographic level;
- regional grouping;
- global/national/local scope.

Examples:

```text
United States · DMA
United States · National
US + Canada · Country
EMEA · Country
Global · Market
Unknown
```

---

# 9. Scope provenance

Scope should retain how it was determined.

Examples:

```text
United States · DMA
Detected

United States · DMA
Inferred from filename

United States · National
Provided by user
```

Possible sources:

- deterministic schema inspection;
- distinct-value profiling;
- provider metadata;
- Business IQ scope;
- filename/path;
- user confirmation.

Do not give filename inference the same authority as deterministic schema evidence.

---

# 10. Discovery table — add Data Quality

Add a compact `Quality` column to the main Discovery table.

Recommended states:

```text
Healthy
2 review
1 blocker
Not assessed
```

Do **not** use a single opaque numeric quality score as the authoritative UI.

Recommended table:

| Requirement | Source | Scope | History | Quality | Status |
|---|---|---|---:|---|---|
| Revenue | Shopify | US · DMA | 42 mo | Healthy | Source found |
| Paid Search | Google Ads | US · DMA | 43 mo | Healthy | Source found |
| Paid Social | Meta Ads | US · National | 31 mo | 2 review | Source found |
| Video / CTV | DV360 | US · DMA | 11 mo | 1 review | Partial |
| Promotions | Merch calendar | US | 36 mo | 2 review | Partial |

---

# 11. Do not conflate Quality and Readiness

Keep these concepts separate.

## Data Quality

Answers:

> **What did the deterministic tests find?**

Examples:

```text
Healthy
2 review
1 blocker
```

## Import Readiness

Answers:

> **Does the source satisfy the governed source/import contract?**

Examples:

```text
Ready
Needs review
Blocked
Not evaluated
```

A source can have:

```text
Data quality
Healthy

Import readiness
Not evaluated
```

or:

```text
Data quality
2 review

Import readiness
Ready with Pre-Modeling review
```

Do not collapse these into one score.

---

# 12. Discovery source status

The current `SOURCE FOUND / SOURCE PARTIAL / PREM3 PROVIDED` status remains useful.

Clarify its meaning as **coverage/discovery status**, not quality/readiness.

Possible discovery statuses:

```text
SOURCE FOUND
SOURCE PARTIAL
SOURCE NOT FOUND
PREM3 PROVIDED
NEEDS DECISION
```

Then Quality and Import Readiness remain separate dimensions.

---

# 13. Source card — surface richer physical metadata

In each source detail/card, add core physical characteristics.

At minimum surface:

```text
Total rows
Partitioning
Clustering
```

where applicable.

Example:

```text
SOURCE DETAILS

Table
marketing.google_ads_daily

Provider
Google Ads

Total rows
14,882,419

Partitioning
segments_date · DAY

Clustering
customer_id, campaign_id

History
43 months

Current grain
Day × campaign

Scope
United States · DMA

Last update
8 hours ago
```

---

# 14. Total row count

Show the detected number of rows:

```text
14.9M rows
```

with exact value available on hover/detail:

```text
14,882,419
```

If the count is approximate because only metadata estimation is available, label:

```text
~14.9M rows
Estimated
```

Do not display an estimated count as exact.

---

# 15. Partitioning metadata

For BigQuery tables, surface:

```text
Partitioning
segments_date · DAY
```

or:

```text
Partitioning
_ingest_date · DAY
```

Possible states:

```text
Partitioned
Not partitioned
Unknown
Not applicable
```

If ingestion-time partitioned, label it correctly.

Avoid implying that every detected time field is the actual partition field.

---

# 16. Clustering metadata

Show clustering columns when present:

```text
Clustering
customer_id, campaign_id
```

If none:

```text
Clustering
None
```

Use this as structural information, not a quality warning by itself.

---

# 17. Additional high-value physical metadata

Where space permits, source detail may also show:

```text
Object type
Table / View / External table / Materialized view

Dataset location
US

Table size
4.8 GB

Last modified
Aug 22, 2026 · 08:12

Partition count
1,308

Column count
37
```

Do not overcrowd the collapsed source card.

Use the expanded Overview tab for this metadata.

---

# 18. Suggested source detail Overview layout

```text
GOOGLE ADS · PAID SEARCH
VERIFIED SOURCE

OVERVIEW

Source
marketing.google_ads_daily

Provider
Google Ads

Object
Partitioned BigQuery table

Rows
14.9M

Columns
37

History
43 months

Grain
Day × campaign

Scope
US · DMA

Partitioning
segments_date · DAY

Clustering
customer_id, campaign_id

Freshness
8h ago · expected daily

Lineage
Native Google Ads transfer
```

---

# 19. Source detail navigation

Add a reusable source-detail subnavigation:

```text
OVERVIEW
QUALITY
DATA PREVIEW
COVERAGE
LINEAGE
TRANSFORMATION
```

Depending on available width, tabs may become secondary nav or segmented links.

This structure should remain consistent across:

- BigQuery sources;
- Drive logical sources;
- later transformed/staging sources.

---

# 20. Add Data Preview tab

This is approved.

Purpose:

> **Let the user inspect real source evidence without leaving PreM3.**

Default:

> **Show the 5 most recent rows**

where a verified time field exists.

---

# 21. BigQuery Data Preview behavior

Behind the scenes, PreM3 compiles a bounded query similar to:

```sql
SELECT <bounded_columns>
FROM <server_resolved_table>
ORDER BY <verified_time_field> DESC
LIMIT 5
```

Important:

- SQL is compiled deterministically.
- Table is resolved server-side.
- Agent/user does not supply arbitrary SQL.
- Query is bounded.
- Preview is read-only.
- Source remains unchanged.

---

# 22. Data Preview UI metadata

Show:

```text
Showing
5 most recent rows

Sorted by
segments_date ↓

Source
marketing.google_ads_daily

Preview mode
Read only
```

If appropriate:

```text
Query scanned
12.4 MB
```

This is optional but can improve enterprise trust.

---

# 23. No verified time field

If PreM3 cannot confidently identify the ordering field:

Do not say:

> Most recent rows

Instead say:

> **5 sample rows**

and:

```text
No verified time field is available for deterministic recency sorting.
```

Possible action:

> `Review time field`

---

# 24. Drive Data Preview

For Drive sources:

```text
Showing
5 most recent parsed rows

From
meta_ads__campaign_delivery__daily__2026-06-01__2026-06-30__v01.csv

File
Meta Export FINAL June.csv

Preview mode
Read only
```

For a logical file series, allow the preview to indicate which file supplied the rows.

---

# 25. Data Preview table behaviors

MVP:

- 5 rows;
- horizontal scroll;
- column labels;
- column type hint;
- null/blank visual treatment;
- most recent sort where known.

Optional later:

```text
5 / 25 / 100
```

Do not add arbitrary filtering/query-building in this design pass.

---

# 26. Highlight relevant source issues in Data Preview

Where helpful, use subtle annotations.

Example:

```text
campaign_type
Prospecting
prospecting
" Prospecting "
```

Quality finding:

> 3 formatting variants detected

Or:

```text
date
2026-08-21
08/20/2026
```

Quality finding:

> Mixed date formats detected

Do not make the table visually noisy.

Use inline markers, row emphasis, or issue callouts sparingly.

---

# 27. Data Preview should link to Quality findings

Example:

> `2 visible quality findings in preview`

Clicking opens:

```text
QUALITY
```

with the full deterministic evidence.

Preview is evidence inspection.

Quality remains authoritative.

---

# 28. Make Data Preview a reusable PreM3 primitive

Define three modes:

```text
SOURCE_PREVIEW
TRANSFORMATION_PREVIEW
CANONICAL_PREVIEW
```

These modes should share a consistent visual language.

---

# 29. SOURCE_PREVIEW

Question:

> **What is actually in the source?**

Shows:

- real rows;
- source metadata;
- current schema;
- detected issues.

---

# 30. TRANSFORMATION_PREVIEW

Question:

> **What does PreM3 propose to change?**

Shows:

```text
BEFORE
real source sample

vs

PROPOSED AFTER
deterministically transformed sample
```

plus action summary.

---

# 31. CANONICAL_PREVIEW

Question:

> **What did PreM3 actually produce?**

Shown only after execution.

Uses verified output.

Includes:

- output source/table;
- output rows;
- post-transform quality;
- reconciliation;
- receipt link.

---

# 32. Transformation Preview — before / proposed after

Example:

```text
BEFORE

date        campaign       spend       region
08/21/26    Brand          $2,104.20   north east
08/21/26    Brand          $2,104.20   north east
08/20/26    Prospecting    $1,892      Northeast
```

Proposed:

```text
AFTER

date        campaign       spend       region
2026-08-21  Brand          2104.20     Northeast
2026-08-20  Prospecting    1892.00     Northeast
```

Then:

```text
Proposed actions

✓ 1 verified duplicate removed
✓ Date normalized
✓ Spend converted to numeric
✓ Region labels normalized

Raw source
UNCHANGED
```

---

# 33. Transformation Preview must preserve authority

Each action shows:

```text
AUTO_SAFE
APPROVAL_REQUIRED
USER_REQUIRED
NOT_RECOMMENDED
```

Example:

```text
AUTO_SAFE
Normalize date format

AUTO_SAFE
Remove exact verified duplicate

AUTO_SAFE
Convert spend to numeric

USER_REQUIRED
Determine whether six-week Paid Social gap was intentional
```

Do not preview the unresolved action as though it has already been applied.

---

# 34. Unknown values remain unknown in preview

Important:

```text
UNKNOWN / MISSING
≠
ZERO
```

If a transform cannot safely resolve a missing period:

Preview:

```text
6-week gap
Preserved as unknown
```

Do not display synthesized zeros.

---

# 35. Transformation Preview — row count comparison

Show:

```text
Source rows
1,244,391

Projected staging rows
1,239,516

Difference
-4,875

Explained by
4,812 exact duplicates
63 verified connector reissues
```

If output count is only an estimate:

```text
Projected
```

If the transformation preview actually executes in an isolated preview environment and produces a deterministic count:

```text
Preview result
```

Use accurate wording.

---

# 36. Transformation Preview — physical changes

Show:

```text
Schema

Before
spend STRING
date STRING
region STRING

After
spend NUMERIC
date DATE
region STRING
```

Also:

```text
Grain
Unchanged

Partitioning
Proposed: date

Clustering
Proposed: campaign_id
```

where applicable.

This gives the user visibility into both data content and physical structure.

---

# 37. Canonical Preview after execution

Once the plan is applied and validated:

```text
VERIFIED OUTPUT

Table
prem3_modeling.stg_meta_ads

Rows
1,239,516

Partitioning
date · DAY

Clustering
campaign_id

Quality
18 passed · 0 blockers

Reconciliation
Spend parity 100.00%

Source changed
No

[ View receipt ]
```

Then show the actual latest 5 output rows.

This creates a powerful proof chain:

```text
SOURCE
        ↓
PROPOSED
        ↓
VERIFIED OUTPUT
```

---

# 38. Data Preview should remain read-only

Never provide an inline spreadsheet-like editing experience.

User decisions alter:

- mappings;
- semantic rules;
- approved transformation plan.

They do not directly edit source values through Data Preview.

---

# 39. Discovery table row action

Current action:

```text
Open
```

Approved.

Opening a row should land on:

```text
Overview
```

Source detail tabs then provide:

```text
Quality
Data Preview
Coverage
Lineage
Transformation
```

Returning via breadcrumb/back should preserve:

- `By requirement` / `By confidence`;
- scroll position if feasible;
- current search/filter state.

---

# 40. Discovery table view modes

Keep:

```text
By requirement
By confidence
```

Potential future:

```text
Needs attention
```

Do not add more modes in this refinement unless useful.

---

# 41. “By requirement” remains default

This best reinforces Business IQ → Data Foundation.

Example:

```text
Revenue
Paid Search
Paid Social
Video / CTV
Email / CRM
Promotions
Seasonality
Product launches
Inventory
Competition
Prior evidence
```

The user sees whether the evidence their business needs actually exists.

---

# 42. Source Preview and source quality relationship

Use:

```text
DISCOVERY
What source likely satisfies the requirement?

        ↓

SOURCE OVERVIEW
What is this source?

        ↓

DATA PREVIEW
What does the data actually look like?

        ↓

QUALITY
Can we trust its structure?

        ↓

TRANSFORMATION
What should PreM3 mend?
```

Do not make Data Preview a substitute for the deterministic assessment.

---

# 43. Source physical metadata should power transformation planning

Examples:

### Current

```text
Rows
14.9M

Partitioning
None

Clustering
None
```

Possible Foundation Plan recommendation:

```text
CREATE staging table

Partition by
event_date

Cluster by
campaign_id
```

But optimization recommendations must be deterministic and based on usage/contract.

Do not imply every large table needs clustering.

---

# 44. Source physical metadata should power query safety

For preview/profiling:

If partitioned:

```text
Use bounded partition predicate
```

when possible.

Example:

```text
WHERE event_date >= CURRENT_DATE() - 30
ORDER BY event_date DESC
LIMIT 5
```

Exact implementation belongs to backend.

The design can show:

> **Bounded preview**

without exposing SQL by default.

---

# 45. Optional query-details disclosure

Consider:

> `View query details`

Drawer:

```text
Read-only query
5 rows returned

Data scanned
12.4 MB

Source
marketing.google_ads_daily

Time field
segments_date
```

The actual SQL may be available in a technical details panel later.

Do not make SQL required reading.

---

# 46. Source metadata for views

If source is a view:

```text
Rows
Calculated at query time
```

or use observed row count from bounded count/profile if known.

Partitioning/clustering may apply to underlying tables rather than the view.

Avoid incorrectly presenting view metadata as physical storage metadata.

Example:

```text
Object
View

Partitioning
Not applicable

Underlying lineage
2 tables
```

---

# 47. File-source physical metadata

For Drive logical sources, use analogous metadata:

```text
Files
12

Total source rows
1.28M

Schema versions
2

Current columns
31

Date range
Jan–Dec 2025

Update cadence
Monthly / manual

Last file
11 days ago

Folder
sources/meta_ads/incoming/
```

Partitioning/clustering:

```text
Not applicable
```

until materialized to BigQuery.

---

# 48. Use canonical/physical metadata only when supported

Do not display blank meaningless labels.

Examples:

BigQuery table:

```text
Rows
Partitioning
Clustering
```

Drive file:

```text
Files
Rows
Schema versions
```

BigQuery view:

```text
Object
Underlying sources
Observed rows
```

Adaptive source cards are preferred.

---

# 49. Quality / readiness summary recommendation

On the source Overview header:

```text
Data quality
18 passed · 2 review

Import readiness
Needs review
```

Do not use:

```text
Readiness score 87%
```

If design wants a visual meter, it must remain secondary to explicit findings/status.

---

# 50. Data Preview and security

The design should reflect that preview is bounded and authorized.

Possible footer:

> **Read-only preview from an authorized source. PreM3 does not modify the source.**

Do not expose credentials, tokens, or unrestricted query controls.

---

# 51. Learning moment — Data Preview

Optional helper:

> **Why preview the source?**  
> A table name can suggest what a dataset contains, but the rows, schema, and history provide stronger evidence about whether it actually represents the business concept PreM3 needs.

This is a useful subtle learning moment.

---

# 52. Learning moment — partitioning

Optional:

> **Partitioning**  
> BigQuery partitioning organizes data by a field such as date. PreM3 can use it to inspect recent history more efficiently and to build durable measurement tables.

Keep hidden by default.

---

# 53. Learning moment — clustering

Optional:

> **Clustering**  
> Clustering organizes related records within BigQuery storage. It can make repeated source access more efficient when aligned with how the data is queried.

Do not imply it affects statistical model quality.

---

# 54. Learning moment — row count

Optional:

> **Row count**  
> Size helps PreM3 understand the source's scale and choose safe profiling strategies. More rows do not necessarily mean better measurement evidence.

---

# 55. Updated source-card prototype case

Design a full source-detail case for:

```text
Google Ads · Paid Search
```

with:

```text
14.9M rows
37 columns
43 months
US · DMA
daily grain
partition: segments_date
cluster: customer_id + campaign_id
healthy quality
verified native transfer
```

Include a 5-row Data Preview.

---

# 56. Updated source-card issue prototype

Design:

```text
Meta Ads · Paid Social
```

with:

```text
8.4M rows
31 months
US · National
daily
partitioned
2 review findings
63 duplicate grain keys
4,812 duplicate rows
```

Show:

```text
Overview
Quality
Data Preview
Transformation
```

and a before/after transformation preview.

---

# 57. Drive source prototype

Design:

```text
Meta Ads historical exports
```

with:

```text
12 files
1.28M rows
2 schema versions
Jan–Dec 2025
manual monthly
Google Drive
```

Show:

- logical source grouping;
- Data Preview;
- Drive history + current BQ convergence;
- Transformation Preview into BQ staging.

---

# 58. Breadcrumb prototype cases

Mock at least:

```text
Data Foundation / Connect / Connect data stores

Data Foundation / Discover & Assess / Discovery

Data Foundation / Sources / Paid Social / Data Preview

Data Foundation / Sources / Paid Social / Transformation Preview

Data Foundation / Resolve & Plan / Foundation Plan
```

---

# 59. Design acceptance criteria — connection

- [ ] BigQuery card contains optional dataset prioritization.
- [ ] Drive card contains optional source/folder prioritization.
- [ ] Inputs convert to manageable chips/tokens.
- [ ] Prioritization does not imply authoritative source identity.
- [ ] Optional “only inspect these datasets” is visually distinct from prioritization.
- [ ] Drive hints remain inside authorized `prem3-modeling`.

---

# 60. Design acceptance criteria — discovery

- [ ] Discovery table includes `Scope`.
- [ ] Scope may include market + geo grain.
- [ ] Scope provenance is accessible.
- [ ] Discovery table includes compact Data Quality state.
- [ ] Discovery Status remains separate from Quality.
- [ ] Import Readiness remains separate from both.
- [ ] `By requirement` remains the primary/default view.

---

# 61. Design acceptance criteria — source metadata

- [ ] BigQuery source detail surfaces total row count.
- [ ] Exact vs estimated row counts are distinguished.
- [ ] Partitioning field/type is shown where applicable.
- [ ] Clustering columns are shown where applicable.
- [ ] Object type is represented accurately.
- [ ] Views are not incorrectly treated as physical tables.
- [ ] Drive sources use file-oriented physical metadata instead.

---

# 62. Design acceptance criteria — Data Preview

- [ ] `DATA PREVIEW` exists as a source-detail tab.
- [ ] Default BigQuery preview is 5 most recent rows when a verified time field exists.
- [ ] No verified time field → 5 sample rows, clearly labeled.
- [ ] Preview is read-only.
- [ ] Source and sort field are visible.
- [ ] Preview links naturally to deterministic quality findings.
- [ ] Preview does not become arbitrary SQL/query builder.
- [ ] Drive logical sources can also be previewed.

---

# 63. Design acceptance criteria — Transformation Preview

- [ ] Before/after data examples are shown.
- [ ] Proposed actions are listed.
- [ ] Action authority is visible.
- [ ] Raw source immutability is stated.
- [ ] Source vs projected output row counts are shown where available.
- [ ] Schema/type changes can be shown.
- [ ] Grain changes are shown.
- [ ] Proposed partitioning/clustering can be shown for BQ output.
- [ ] Unknown/missing values remain unknown unless deterministically resolved.
- [ ] Preview is clearly marked as proposed, not applied.

---

# 64. Design acceptance criteria — Verified Output

- [ ] Post-execution output can use the same preview component.
- [ ] Verified output table/source identity shown.
- [ ] Verified row count shown.
- [ ] Partitioning/clustering shown.
- [ ] Post-transform quality shown.
- [ ] Reconciliation shown where available.
- [ ] Receipt link available.
- [ ] User can compare source → proposed → verified result.

---

# 65. Updated design north star

The refined workflow should make the user feel:

> **“PreM3 did not simply tell me that it found a source. I can see what the source represents, how large it is, how it is physically structured, what market/geography it covers, whether the data is healthy, inspect the actual rows, and see exactly what PreM3 proposes to change before anything is transformed.”**

The inspection loop is:

```text
DISCOVERY CLAIM
        ↓
SOURCE METADATA
        ↓
ACTUAL ROW PREVIEW
        ↓
DETERMINISTIC QUALITY
        ↓
TRANSFORMATION PREVIEW
        ↓
APPROVED EXECUTION
        ↓
VERIFIED OUTPUT PREVIEW
        ↓
RECEIPT
```

This should become a reusable PreM3 product pattern.

> **Claims should be inspectable. Transformations should be previewable. Outputs should be provable.**
