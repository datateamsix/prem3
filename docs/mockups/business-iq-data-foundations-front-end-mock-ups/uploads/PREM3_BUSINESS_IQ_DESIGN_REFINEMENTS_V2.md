# PreM3 Business IQ — Design Refinements for V2 Mockups

**Status:** Design refinement handoff  
**Audience:** Product design / UX / frontend design planning  
**Applies to:** Current Business IQ standalone onboarding prototype and the reusable in-product Business IQ surface  
**Version:** `business-iq/design-refinements/1.0`  
**Date:** 2026-08-20  

---

# 1. Objective

The current Business IQ standalone flow is conceptually strong and should be **refined rather than redesigned from scratch**.

The next design pass should preserve its best characteristics:

- compact section-based onboarding rather than a giant form;
- visible conceptual progress;
- explicit `Not sure` / unknown states;
- progressive disclosure;
- “Why PreM3 asks” explanations;
- conversational clarification when bounded answers are insufficient;
- Business Profile review with provenance;
- durable/editable Business IQ rather than one-time intake;
- clear separation between Business IQ and Data IQ.

The V2 refinement should improve four areas:

1. capture a little more **causally and temporally useful business context**;
2. broaden market and channel coverage for enterprise users;
3. reduce generic catch-all options such as **Other**;
4. make the current visual framework reusable as the overall PreM3 in-product interaction pattern.

---

# 2. Canonical product sequence

The Business IQ completion flow should now be:

```text
BUSINESS IQ
What the business means
        ↓
BUSINESS_CONTEXT_READY
        ↓
DATA FOUNDATION
What evidence exists + establish governed data infrastructure
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

## Design change

Remove the current completion fork:

- `I need a data acquisition plan`
- `I already have data`

Replace it with one primary CTA:

> **Continue to Data Foundation**

Data IQ should determine whether the organization:

- already has mature BigQuery data;
- has partial / fragmented data;
- has files but no governed foundation;
- has data only in platforms;
- needs a collection / acquisition plan.

The user should not need to classify their own data maturity before Data IQ has inspected it.

Secondary action:

> **Review my Business Profile**

---

# 3. Global answer-option rule — replace “Other”

## New interaction rule

Avoid using **Other** as a terminal answer choice.

Where a predefined list cannot cover every legitimate answer, use:

> **Enter a custom answer**

or:

> **Add your own**

Selecting it should reveal an inline text field.

Example:

```text
What best describes your business model?

○ Ecommerce
○ Subscription
○ Marketplace
○ Lead generation
○ Retail / physical locations
○ Services
○ Add your own: [________________]
```

## Why

“Other” creates weak Business IQ:

```text
business_model = OTHER
```

Custom text creates usable semantic context:

```text
business_model = "Franchise-based home services marketplace"
```

PreM3 may later propose a normalized category, but the user's original wording should be preserved.

## Required behavior

Custom-entry answers should support:

- raw user text;
- optional normalized candidate;
- provenance;
- user confirmation if PreM3 normalizes it;
- editability in Business Profile review.

---

# 4. Global UI pattern — reuse current layout across the product

The current Business IQ standalone layout is a strong candidate for the **overall in-product PreM3 interaction model**.

Recommended reusable structure:

```text
┌─────────────────────────────┬────────────────────────────────────┐
│                             │                                    │
│ Product / workspace         │ Section title                      │
│                             │ Short explanation                  │
│ FOUNDATION                  │                                    │
│ ✓ Business Intelligence     │ Primary interaction surface        │
│ → Data Foundation           │                                    │
│                             │ Cards / questions / findings        │
│ MEASUREMENT                 │                                    │
│   Pre-Modeling              │ Contextual explanations            │
│   Modeling                  │                                    │
│                             │                                    │
│ Progress / sections         │ Primary CTA                        │
│                             │                                    │
└─────────────────────────────┴────────────────────────────────────┘
```

The same structural grammar can later support:

- Business IQ;
- Data IQ;
- Pre-Modeling;
- model configuration;
- model review;
- source health;
- evidence reconciliation;
- scenario planning.

The content changes, but the interaction language stays familiar.

---

# 5. Iconography guidance

Use icons selectively to improve **recognition and hierarchy**, not as decoration.

## Recommended icon usage

### Main product stages

| Stage | Suggested icon concept |
|---|---|
| Business Intelligence | building / briefcase / lightbulb |
| Data Foundation | database |
| Pre-Modeling | checklist / microscope / search |
| Modeling | chart / function / model nodes |

### Business IQ sections

| Section | Suggested icon concept |
|---|---|
| Business | building |
| Objective | target |
| Markets | globe |
| Marketing Portfolio | megaphone |
| Decision-Making | route / sliders / split arrows |
| Commercial Drivers | gauge / trending arrows |
| Competition | users / crosshair |
| Events | calendar |
| Existing Evidence | flask / document-check |
| Review | clipboard-check |
| Ready | check-circle |

### Reusable semantic indicators

| Meaning | Icon concept |
|---|---|
| Why PreM3 asks | info circle |
| Confirmed | check-circle |
| Provided by user | user |
| Inferred / extracted | spark / wand, used sparingly |
| Data detected | database-search |
| Unknown | help circle |
| Needs review | alert triangle |
| Stale | clock / refresh |
| Edit | pencil |
| Custom answer | plus |
| Add event / evidence | plus-circle |

## Icon rules

- Use one consistent icon library in production.
- Icons should normally accompany text, not replace labels.
- Do not communicate authority or readiness through icons alone.
- Avoid decorative icon clutter inside every chip or radio option.
- Use icons most strongly for navigation, state, provenance, and high-value actions.
- Preserve the current restrained visual language: iconography should clarify structure, not make the interface feel playful.

---

# 6. Welcome / orientation

The current orientation is strong and should stay concise.

## Keep

Core message:

> **Before we look at your data, tell PreM3 how your business works.**

Keep trust cues such as:

- `Not sure` is a valid answer;
- users can update the profile later;
- exact confidential numbers are not required to begin;
- PreM3 uses this context to interpret later evidence.

## Refinement

Avoid a rigid promise such as a precise number of questions because branching can make the experience feel inconsistent with that claim.

Recommended:

> **About 10 minutes for most businesses.**  
> PreM3 only asks follow-up questions when the answer can materially improve planning or measurement.

Optional supporting line:

> As PreM3 learns from your data later, it may ask a small number of additional questions to clarify what the evidence means.

---

# 7. Business identity

The current Business section should remain lightweight.

## Keep baseline concepts

- business model;
- industry / category;
- B2C / B2B / both.

## Example questions

### Business model

> **Which description best matches how your business primarily generates revenue?**

Suggested options:

- Ecommerce
- Subscription
- Marketplace
- Retail / physical locations
- Lead generation
- Professional / managed services
- Franchise / multi-location
- Advertising / media
- Usage-based / transactional
- Add your own: `[text]`
- Not sure

### Industry

> **Which industry or category best describes the business in scope?**

Use searchable choices plus:

> **Add your own category**

### Customer model

> **Who do you primarily sell to?**

- Consumers
- Businesses
- Both consumers and businesses
- Add your own: `[text]`
- Not sure

## Do not add to baseline

Avoid requiring:

- exact revenue;
- employee count;
- valuation;
- exact margin;
- exact LTV;
- exact annual marketing budget.

These can be requested later only when they materially affect the current decision.

---

# 8. Objective & KPI

The current design principle should remain:

> **Lead with the decision.**

## Question 1 — decision

> **What decision do you most want measurement to improve?**

Suggested choices:

- Allocate budget across marketing channels
- Understand incremental channel impact
- Improve marketing efficiency / ROI
- Plan future spend
- Understand geographic performance
- Evaluate a specific channel or strategy
- Reconcile conflicting measurement signals
- Add your own objective: `[text]`
- Not sure yet

Multi-select may be appropriate, but require one **primary** objective.

## Question 2 — modeled outcome

> **What business outcome matters most for this analysis?**

Examples:

- Revenue
- Orders / transactions
- Leads
- Qualified leads
- Bookings
- Subscriptions
- Trials
- Pipeline
- New customers
- App installs / activations
- Add your own KPI: `[text]`
- Not sure

## Question 3 — KPI meaning

> **How does your organization define this outcome?**

Free text with examples.

Example:

> “Revenue means completed ecommerce orders net of refunds.”

## Future-ready refinement — economic decision metric

Architect the UX so a later optional question can distinguish:

```text
Modeled KPI
Orders

Economic decision metric
Revenue / contribution margin
```

Suggested optional follow-up:

> **Do you evaluate marketing using a different financial outcome than the KPI above?**

- No
- Yes → `What financial outcome? [text]`
- Not sure

This does not need to be required in the initial V2.

---

# 9. Markets & geography

The current question “Which market matters most?” is too narrow for the enterprise direction.

## Replace with

> **Which markets are in scope for this measurement program?**

Allow multi-select.

The control should support:

1. predefined global business regions;
2. country search;
3. custom market grouping.

A user may select both a macro-region and specific countries if useful.

---

## 9.1 Recommended predefined regional choices

### Core global regions

- **NA — North America**
  - Common business grouping centered on the United States and Canada.
  - Because Mexico may be classified differently by different organizations, the UI should not silently assume whether Mexico belongs in NA or LATAM.

- **LATAM — Latin America**
  - Latin American markets across Mexico, Central America, the Caribbean where appropriate to the organization, and South America.

- **EMEA — Europe, Middle East & Africa**
  - Broad enterprise grouping covering Europe, the Middle East, and Africa.

- **APAC — Asia-Pacific**
  - Broad Asia-Pacific grouping including East Asia, Southeast Asia, and Oceania.

### Common sub-regions / business clusters

- **MENA — Middle East & North Africa**
- **GCC — Gulf Cooperation Council**
- **ASEAN — Southeast Asian regional grouping**
- **ANZ — Australia & New Zealand**
- **Greater China**
- **SEA — Southeast Asia**
- **SSA — Sub-Saharan Africa**
- **DACH — Germany, Austria & Switzerland**
- **Benelux — Belgium, Netherlands & Luxembourg**
- **CEE — Central & Eastern Europe**
- **APJ — Asia-Pacific & Japan**
- **CALA — Caribbean & Latin America**
- **Americas — North, Central and South American markets**

### Optional / organization-specific grouping support

Organizations sometimes use internal region vocabularies that do not map cleanly to standard definitions.

Provide:

> **Add your own region / market group**

Example:

```text
"US + Canada Enterprise"
"Nordics"
"Southern Europe"
"Tier 1 APAC"
```

### Do not use as primary predefined geographic regions

Avoid putting these into the baseline region selector:

- **PIGS** — dated and potentially derogatory terminology; do not expose in product UI.
- **BRICS** — an economic/political grouping rather than a stable operating geography.
- **AMER** without definition — ambiguous; use `Americas` with a clear description.
- **CIS** as a simple current geographic membership list — membership/usage is politically and historically complex and may not match customer operating structures.

If customers use any of these internally, they can enter the term as a **custom region**, and PreM3 should preserve their business taxonomy without presenting it as a canonical geographic standard.

---

## 9.2 Regional importance

After markets are selected:

> **Do meaningful differences between these markets affect how you sell, price, advertise, or serve customers?**

- Yes
- No
- Sometimes
- Not sure

If yes:

> **What tends to differ by market?**

Multi-select:

- Marketing spend / channel mix
- Pricing
- Promotions
- Product mix
- Distribution / availability
- Customer behavior
- Competition
- Brand maturity
- Sales / revenue level
- Add your own: `[text]`
- Not sure

### Important boundary

Do **not** ask whether geo-level data is available here.

Business IQ answers:

> Does geography matter?

Data IQ later answers:

> Does usable geo-level evidence exist?

---

# 10. Customer journey

Keep the current broad journey classification.

## Suggested question

> **Which description best matches the path from marketing exposure to the business outcome?**

- Mostly immediate / same-session purchase
- Short consideration cycle
- Longer consideration cycle
- Lead → sales process
- Online marketing → offline purchase
- Subscription / recurring relationship
- Mixed journeys
- Add your own: `[text]`
- Not sure

## Conditional follow-up

If the journey is delayed, lead-based, offline, subscription-based, or mixed:

> **Roughly how long is it usually between meaningful marketing exposure and the business outcome?**

- Same day
- A few days
- 1–4 weeks
- 1–3 months
- More than 3 months
- Varies widely
- Add your own: `[text]`
- Not sure

### Why PreM3 asks

> The timing between marketing and the outcome can affect how PreM3 later interprets lagged media effects, attribution paths, experiments, and forecasts.

---

# 11. Acquisition vs retention

Keep this concept because it affects both the business interpretation and future measurement architecture.

## Example question

> **Do acquisition and retention marketing play meaningfully different roles in your business?**

- Yes
- No
- Somewhat
- Not sure

If yes:

> **How are they different?**

Allow concise free text or suggested chips:

- Different channels
- Different audiences
- Different KPIs
- Different budgets
- Different teams
- Different economics
- Add your own: `[text]`

---

# 12. Marketing portfolio — expand channel taxonomy

The current channel list should be expanded to better represent modern enterprise media mixes.

Business IQ captures **channel concepts**, not platform/provider names.

Provider names such as Google Ads, Meta, Spotify, The Trade Desk, etc. belong primarily in Data IQ.

---

## 12.1 Recommended channel choices

### Search

- Paid Search
- Shopping / Product Listing Ads
- Organic Search / SEO

### Social

- Paid Social
- Organic Social

### Video / television

- Online Video
- YouTube / Video
- **Connected TV / Streaming TV**
- Linear TV
- Addressable TV

### Audio

- **Streaming Audio / Digital Audio**
- Podcast Advertising
- Terrestrial / Traditional Radio

Examples such as Spotify may appear as helper text:

> Streaming Audio — e.g., Spotify, Pandora, digital radio

But **Spotify should be treated as a provider/platform in Data IQ**, not the canonical Business IQ channel.

### Display / programmatic

- Programmatic Display
- Direct Display / Publisher Media
- Native Advertising

### Retail / commerce media

- Retail Media
- Marketplace Advertising
- Affiliate / Partner Marketing

### CRM / owned

- Email
- SMS / Messaging
- Push Notifications / App Messaging
- Direct Mail
- Loyalty / CRM Marketing

### Offline / traditional

- Out-of-Home / OOH
- Digital Out-of-Home / DOOH
- Print
- Cinema
- Sponsorships
- Events / Experiential

### Partnerships / influence

- Influencer / Creator
- Partnerships
- Referral

### Custom

- **Add a custom channel: `[text]`**

### Unknown

- Not sure / needs review

---

## 12.2 Channel selection UX

The selector should support:

- search;
- grouped channel families;
- multi-select;
- custom text;
- large portfolios;
- editability later.

Do not design only for four channels.

Prototype with:

- 4 channels;
- 8 channels;
- 15 channels.

---

# 13. Channel roles

Expand the current role taxonomy.

## Recommended role choices

- Demand creation
- Demand capture
- Prospecting
- Retargeting
- **Retention / lifecycle**
- Conversion support
- **Brand building**
- Local activation
- Partner / retail support
- Multiple roles
- Add your own role: `[text]`
- Not sure

### Example question

> **What role does Paid Search primarily play in your marketing strategy?**

If multiple roles:

> **Which roles apply?**

### Why PreM3 asks

> Channels that capture existing demand can behave very differently from channels intended to create demand. That distinction can affect later causal interpretation.

---

# 14. Search-specific follow-up

If Paid Search is material, add conditional questions because Search has unusually important causal ambiguity.

## Question A

> **How much of Paid Search is branded vs non-branded?**

- Mostly branded
- Mostly non-branded
- Meaningful mix of both
- We separate them operationally
- We do not separate them
- Not sure

## Question B

> **Can stronger customer search demand cause Paid Search spend or delivery to increase?**

- Yes
- No
- Sometimes
- Not sure

## Question C

> **Do automated bidding or budget systems respond to recent demand, conversions, ROAS, or similar performance signals?**

- Yes
- No
- Some campaigns do
- Not sure

### Why PreM3 asks

> Search activity may rise because demand is already increasing. PreM3 needs to distinguish demand capture from incremental demand creation when reviewing later model assumptions.

---

# 15. Marketing decision-making / budget process

Keep this section and strengthen the conditional logic.

It is one of the highest-value Business IQ areas.

## Baseline question

> **What typically causes marketing spend or delivery to change?**

Multi-select:

- Annual / quarterly plan
- Seasonality
- Promotions
- Product launches
- Changes in customer demand
- Recent marketing performance
- Inventory / availability
- Competitor activity
- Agency recommendations
- Platform automation
- Executive / management discretion
- Contractual commitments
- Market expansion / contraction
- Add your own: `[text]`
- Not sure

---

## Conditional — performance-responsive spend

If `Recent marketing performance` is selected:

> **Can strong or weak results cause spend to change during the same planning period?**

- Yes
- No
- Sometimes
- Not sure

---

## Conditional — customer demand

If `Changes in customer demand` is selected:

> **Can stronger demand cause media spend or delivery to increase even before your team explicitly changes the budget?**

- Yes
- No
- Sometimes
- Not sure

Helper:

> Search volume, auction availability, and automated systems can increase delivered spend even when the planned budget has not changed.

---

## Conditional — platform automation

If `Platform automation` is selected:

> **What signals can automated bidding or budget systems respond to?**

Multi-select:

- Conversion volume
- Conversion value / revenue
- ROAS / efficiency targets
- Search / query demand
- Audience availability
- Cost / auction conditions
- Inventory / product availability
- Add your own: `[text]`
- Not sure

---

## New — decision cadence

> **How often are meaningful marketing allocation decisions typically made?**

- Daily
- Weekly
- Monthly
- Quarterly
- Annually
- Mostly fixed once planned
- Ad hoc / event-driven
- Varies by channel
- Add your own: `[text]`
- Not sure

### Why PreM3 asks

> If media changes in response to demand or recent business performance, that relationship can matter when estimating what marketing caused.

---

# 16. Commercial drivers

Keep the current driver matrix, but add targeted follow-ups where the answer is highly useful.

## Baseline

> **Which factors materially change business outcomes or marketing activity?**

Use a relevance control such as:

```text
Not material
Somewhat important
Important
Not sure
```

Drivers:

- Pricing
- Promotions
- Seasonality
- Inventory / availability
- Product launches / assortment
- Distribution / store footprint
- External / macro events
- Competitor activity
- Add your own driver: `[text]`

---

# 17. Seasonality — deeper follow-up

The current `Seasonality = Important` signal is too shallow for later temporal reasoning.

## Trigger

If seasonality is `Somewhat important` or `Important`:

> **What recurring periods tend to materially change demand or customer behavior?**

Multi-select:

- Holiday / Q4
- Back-to-school
- Summer
- Winter
- Tax season
- Weather-driven periods
- Weekly / day-of-week cycle
- Month-end / quarter-end
- Industry-specific season
- Add your own recurring period: `[text]`
- Not sure

## Follow-up

> **Is the seasonal pattern relatively stable from year to year?**

- Mostly stable
- Changes somewhat
- Changes materially
- Not sure

Optional free text:

> **Anything unusual about your seasonal pattern?**  
> `[text]`

### Why PreM3 asks

> Recurring demand patterns affect how later models separate normal business movement from marketing-driven movement.

---

# 18. Promotions

If promotions are important:

## Question A

> **Do promotions usually run independently of paid media, or are they intentionally coordinated with marketing?**

- Usually independent
- Usually coordinated
- Sometimes coordinated
- Varies by promotion
- Not sure

## Question B

> **Can strong or weak demand change when promotions are launched?**

- Yes
- No
- Sometimes
- Not sure

## Question C

> **Are the biggest promotions recurring or one-time?**

- Mostly recurring
- Mostly one-time
- Mix of both
- Not sure

### Why PreM3 asks

> Promotions can directly change demand and may also change media spend, which makes their role important to later causal interpretation.

---

# 19. Pricing

If pricing is important:

> **How are major price changes typically determined?**

- Planned independently in advance
- Coordinated with promotions
- Respond to demand
- Respond to inventory
- Respond to competitor pricing
- Product / assortment driven
- Mix of several factors
- Add your own: `[text]`
- Not sure

Optional:

> **Do major price changes often occur at the same time as major marketing changes?**

- Yes
- No
- Sometimes
- Not sure

---

# 20. Inventory / availability

Keep the current inventory follow-up and make the causal direction explicit.

## Question

> **Can inventory or product availability change how much marketing you run?**

- Yes
- No
- Sometimes
- Not sure

If yes:

> **What usually happens when inventory is constrained?**

- Reduce / pause media
- Shift spend to other products
- Shift spend to other markets
- Continue media unchanged
- Depends on channel
- Add your own: `[text]`
- Not sure

### Why PreM3 asks

> Inventory can affect both sales and media decisions. That makes it potentially important when interpreting marketing impact.

---

# 21. Competition

Keep progressive disclosure.

## Baseline

> **Does competitor activity materially affect customer demand, pricing, or your marketing decisions?**

- Yes
- No
- Sometimes
- Not sure

If yes:

> **What can competitor activity affect?**

- Customer demand
- Search demand
- Paid media costs
- Pricing
- Promotions
- Product positioning
- Marketing spend
- Market entry / exit decisions
- Add your own: `[text]`
- Not sure

Optional:

> **Are there specific competitors or categories PreM3 should know about?**

Free text; visibly optional.

### Why PreM3 asks

> Competitor activity can influence customer demand and your marketing decisions at the same time.

---

# 22. Business events

Keep the event timeline concept.

## Event types

- Promotion
- Pricing change
- Product launch
- Product retirement
- Market launch / exit
- Store / location opening or closure
- Media channel launch
- Media channel pause
- Major budget-policy change
- Marketing strategy change
- Inventory constraint
- Tracking / measurement change
- Competitor event
- Distribution change
- Organizational / sales-process change
- Add your own event type: `[text]`

## Add approximate dates

Users should not need exact dates for every historical event.

For start/end, support:

- exact date;
- month/year;
- quarter/year;
- approximate date.

Example:

```text
Started
○ Exact date
○ Approximate

Approximate:
[ Q2 2025 ]
```

## Distinguish events from recurring patterns

When entering an event:

> **Was this a one-time event or a recurring pattern?**

- One-time event
- Recurs regularly
- Not sure

If recurring, offer:

> **Add to recurring business patterns**

This prevents annual holiday promotions from becoming dozens of isolated events.

---

# 23. Existing evidence / priors

Keep the current framing:

> Users provide business evidence. They do **not** configure Bayesian distributions in onboarding.

## Baseline

> **Do you already have credible evidence about the impact of any marketing activity?**

Examples:

- geo / holdout experiment;
- platform lift study;
- previous MMM;
- internal benchmark;
- prior attribution study;
- expert / planning knowledge.

Answers:

- Yes
- No
- Not sure

## If yes — lightweight capture

> **Add evidence**

### Evidence type

- Geo experiment
- Holdout / randomized experiment
- Platform lift study
- Previous MMM
- Attribution study
- Internal benchmark
- Expert / planning knowledge
- Add your own evidence type: `[text]`

### Description

> **What did you learn?**  
> `[free text]`

### New optional structure

PreM3 can extract candidates from the description and ask the user to confirm:

```text
Applies to          Paid Search
Evidence period     Q2 2025
Market              United States
Outcome             Revenue
Evidence source     Geo experiment
```

User actions:

- Confirm
- Edit
- Leave unstructured for now

### Artifact

Do not force upload here.

Show:

> **Attach supporting file later in Data Foundation**

Data IQ / Google Drive integration should ultimately validate whether the artifact is accessible.

### Why PreM3 asks

> Previous experiments and MMM studies may contain credible evidence that is not visible in the current dataset and can inform later model recommendations.

---

# 24. Business Profile review

Preserve the existing synthesis-first review.

This should remain much more than “review your answers.”

## Recommended structure

```text
WHAT PREM3 UNDERSTANDS

Business & KPI             Confirmed
Markets                    Confirmed
Marketing portfolio        Confirmed
Decision process           Partial
Commercial drivers         Confirmed
Competition                Unknown acknowledged
Business events            3 recorded
Prior evidence             2 sources
Open questions             2
```

Each section should expand into structured facts.

---

# 25. Standardize user-facing provenance

Internal provenance may be richer, but the UI should consistently use a small vocabulary.

Recommended user-facing states:

| System meaning | User-facing label | Icon concept |
|---|---|---|
| user stated | Provided by you | user |
| extracted from free text | From your description | sparkle/document |
| deterministic data evidence | Detected in your data | database-search |
| user confirmed | Confirmed by you | check-circle |
| inferred candidate | Needs confirmation | help / sparkle |
| conflict | Needs review | alert triangle |
| stale | May need updating | clock |
| explicit unknown | Unknown | help-circle |

Do not visually mix **provenance** with **readiness**.

---

# 26. Business IQ update receipts

When Data IQ later produces evidence that changes Business IQ, show the proposed change before writing it.

Example:

```text
Business Profile update

Paid Social

Previously
Always-on

New evidence
No spend or impressions observed Apr 1–May 15, 2026.

You confirmed
The channel was intentionally paused because inventory was constrained.

Proposed profile update
Paid Social intentionally paused Apr 1–May 15, 2026 due to inventory constraints.

[ Update Business Profile ]
[ Keep current profile ]
```

After update:

```text
✓ Business Profile updated
Source: Data IQ evidence + confirmed by you
```

This should become a reusable in-product receipt pattern.

---

# 27. Conversational clarification

Keep the existing “Tell PreM3 in your own words” escape hatch.

Use it when:

- bounded options are inadequate;
- the user chooses custom text;
- the user is unsure how to classify a business process;
- causal nuance matters.

## Pattern

```text
Tell PreM3 in your own words

How does your Paid Search budget typically change during the year?

[ We set a quarterly budget, but Google can spend more during high-demand
  periods as long as ROAS stays above target. ]
```

PreM3 response:

```text
Here is what I understood:

✓ Budget is planned quarterly.
✓ Delivered spend can increase when demand increases.
✓ Automated efficiency targets constrain the increase.

Is that right?

[ Yes, save this ]
[ Edit ]
```

The structured interpretation must remain visibly distinguishable from the raw user statement.

---

# 28. “Why PreM3 asks” reusable pattern

Use an `info` icon plus a concise expandable explanation.

Never expose long modeling lectures during onboarding.

Examples:

### Budget behavior

> **Why PreM3 asks:** If spend increases because demand is already rising, PreM3 needs to consider that relationship when estimating incremental impact.

### Search

> **Why PreM3 asks:** Search can capture demand that already exists, so understanding how spend responds to query demand helps interpret Search correctly.

### Promotions

> **Why PreM3 asks:** Promotions can change demand directly and may also change how much media you run.

### Competition

> **Why PreM3 asks:** Competitor activity can affect customer demand and your own media decisions at the same time.

### Seasonality

> **Why PreM3 asks:** Recurring demand patterns help later models distinguish normal business movement from marketing effects.

### Prior evidence

> **Why PreM3 asks:** Previous experiments or MMM studies can provide credible information that is not visible in the current dataset.

---

# 29. Progress & navigation

Preserve conceptual progress rather than question counts.

Recommended left-side progress:

```text
Business             ✓
Objective            ✓
Markets              ✓
Marketing            ●
Business drivers     ○
Evidence             ○
Review               ○
```

Depending on design density, Competition and Events may be nested under Business Drivers / Context rather than each being a full left-nav item.

## Requirements

- Back/edit;
- auto-save;
- resume;
- no visible penalty for `Not sure`;
- optional enrichment visually differentiated;
- returning users should enter the existing Business Profile, not restart onboarding.

---

# 30. Answer-state requirements

Question components should support, where appropriate:

- Yes
- No
- Sometimes / Mixed
- Not sure
- Not applicable
- Answer later
- Custom text

Important:

```text
Not answered
≠
Not sure
```

Business IQ readiness should recognize explicit acknowledgement of unknown information.

---

# 31. Business IQ completion

Recommended completion screen:

```text
BUSINESS CONTEXT READY

PreM3 understands enough about how your business operates
to begin evaluating the evidence behind it.

✓ Business & KPI
✓ Markets
✓ Marketing portfolio
✓ Decision process
✓ Commercial drivers

2 known gaps
1 optional evidence item can be added later

Next
Data Foundation
Connect, discover and organize the evidence PreM3 will use.

[ Continue to Data Foundation ]

Secondary:
[ Review my Business Profile ]
```

Avoid:

> “Profile complete”

Business IQ is expected to evolve as Data IQ and future modeling produce new evidence.

---

# 32. Channel/platform change management — design for future reuse

The Business IQ Marketing Portfolio should become editable after onboarding.

Provide a persistent action such as:

> **Manage marketing mix**

Future actions:

- Add channel
- Change channel role
- Pause channel
- Retire channel
- Add market
- Change business event
- Add evidence

Example future workflow:

```text
+ Add channel

Channel
[ Connected TV / Streaming TV ]

Role
[ Demand creation ] [ Brand building ]

Started
[ July 2026 ]

Where is the data?
Handled next by Data IQ.
```

Adding a channel should update Business IQ immediately.

It should **not automatically modify an existing MMM**.

Instead:

```text
Business IQ change
       ↓
Data IQ source onboarding
       ↓
Evidence accumulation
       ↓
Pre-Modeling eligibility review
       ↓
Model Plan vNext
```

Design Business IQ components so they can later support this persistent management flow without creating a second channel-management UI.

---

# 33. Prototype scenarios for V2

The next design iteration should explicitly demonstrate:

## Scenario A — Standard single-market ecommerce

- US;
- ecommerce;
- Revenue;
- Paid Search / Paid Social / Streaming TV / Email;
- promotion + seasonality;
- clear budget process;
- no prior evidence.

## Scenario B — Multi-region enterprise

Markets:

- NA;
- EMEA;
- APAC;

Regional differences:

- pricing;
- product mix;
- channel allocation.

The UI must remain usable without one “primary market.”

## Scenario C — Large channel portfolio

At least 12 channels including:

- Paid Search;
- Paid Social;
- Streaming TV / CTV;
- Streaming Audio;
- Retail Media;
- Programmatic;
- Linear TV;
- OOH;
- Email;
- Affiliate;
- Influencer;
- Direct Mail.

Validate that channel selection and role assignment remain efficient.

## Scenario D — Search demand ambiguity

User says:

> “We set quarterly Search budgets, but Google spends more when query demand rises if ROAS stays in range.”

Show:

- own-words input;
- extracted structured meaning;
- confirmation;
- Why PreM3 asks.

## Scenario E — Seasonal business

Business marks seasonality important and identifies:

- Q4 holiday;
- back-to-school;
- stable annual pattern.

Show concise conditional follow-up.

## Scenario F — Delayed customer journey

Lead generation business:

- 1–3 month sales cycle;
- Paid Search + LinkedIn + events;
- pipeline KPI.

## Scenario G — Existing evidence

User describes a prior geo experiment.

PreM3 extracts:

- channel;
- period;
- market;
- KPI;
- evidence type.

## Scenario H — Custom answers

User chooses:

- custom business model;
- custom region;
- custom channel;
- custom commercial driver.

No “Other” values appear in the resulting profile.

## Scenario I — Business IQ → Data Foundation

One CTA:

> Continue to Data Foundation

No data-maturity fork.

## Scenario J — Returning user adds Streaming Audio

Business IQ already exists.

User:

- opens `Manage marketing mix`;
- adds `Streaming Audio`;
- selects `Demand creation / Brand building`;
- Data IQ becomes the next step for provider/source discovery.

---

# 34. Design acceptance criteria for the refinement pass

The Business IQ V2 mockups are ready when:

### Coverage

- [ ] Streaming TV / CTV exists as a defined channel.
- [ ] Streaming Audio / Digital Audio exists as a defined channel.
- [ ] Channel list covers major digital and offline marketing families.
- [ ] Retention / lifecycle exists as a channel role.
- [ ] Enterprise multi-market scope is supported.
- [ ] Regional selection supports predefined business regions + country search + custom groups.
- [ ] No generic `Other` answer is used where custom text is more useful.

### Causal / temporal intelligence

- [ ] Search has conditional demand / automation questions.
- [ ] Marketing decision cadence can be captured.
- [ ] Seasonality receives a conditional follow-up.
- [ ] Promotions can be classified as coordinated vs independent.
- [ ] Pricing decision behavior can be captured where relevant.
- [ ] Inventory can be linked to media decisions.
- [ ] Delayed customer journeys capture approximate lag.

### Evidence

- [ ] Existing evidence can optionally capture channel, market, period, and KPI.
- [ ] Artifact upload is deferred naturally to Data Foundation.
- [ ] Prior evidence is not described as guaranteed truth or a final model prior.

### UX

- [ ] Current standalone layout is reused as the basis for the in-product interaction shell.
- [ ] Icons improve stage / section / state clarity without becoming decorative.
- [ ] `Not sure` is visibly different from unanswered.
- [ ] Custom text is first-class.
- [ ] “Why PreM3 asks” remains concise and contextual.
- [ ] Conversational clarification extracts structured meaning and requests confirmation.
- [ ] Large channel portfolios remain usable.

### Lifecycle

- [ ] Business IQ completion leads directly to Data Foundation.
- [ ] Business IQ is presented as durable/editable, not one-time onboarding.
- [ ] A returning user can add a channel or market without redoing intake.
- [ ] Data IQ evidence can later propose Business IQ updates with provenance.

---

# 35. Design north star

The refined Business IQ experience should feel like:

> **PreM3 is learning how the business actually works, not asking the user to fill out a marketing questionnaire.**

Each question should pass this test:

> **Can this answer materially improve data planning, causal interpretation, model design, diagnostics, forecasting, experimentation, or investment decisions?**

If not, do not ask it.

The baseline experience should stay compact.

The sophistication should come from:

- branching;
- selective clarification;
- durable Business IQ;
- evidence-triggered follow-up;
- user-confirmed structured meaning;

not from displaying the full ontology.

---

# 36. Summary of required V2 changes

```text
CURRENT BUSINESS IQ
        ↓
Preserve core structure
        ↓
REMOVE GENERIC “OTHER”
Use custom text instead
        ↓
EXPAND MARKETS
Multi-region + defined region taxonomy
        ↓
EXPAND MEDIA MIX
CTV / Streaming TV + Digital Audio + modern channels
        ↓
DEEPEN ONLY HIGH-VALUE QUESTIONS
Search / automation / cadence / seasonality / promotions / pricing
        ↓
STRUCTURE PRIOR EVIDENCE LIGHTLY
Without asking for distributions
        ↓
STANDARDIZE PROVENANCE
And Business Profile update receipts
        ↓
ONE HANDOFF
Continue to Data Foundation
        ↓
REUSE THE SHELL
Across the broader PreM3 product
```

The goal is **not more onboarding**.

The goal is:

> **More decision-relevant Business IQ with less ambiguity and no unnecessary user burden.**
