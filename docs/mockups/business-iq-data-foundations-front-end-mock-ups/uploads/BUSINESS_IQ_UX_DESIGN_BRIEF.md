# PreM3 Business IQ — UX / Product Design Brief

**Status:** Canonical strategic design handoff  
**Owner:** Business IQ strategy / product architecture  
**Primary consumers:** Product design, UX, frontend planning, backend planning  
**Companion specifications:** `BUSINESS_PROFILE_V1_SPEC.md`, `BUSINESS_IQ_CAPTURE_STRATEGY.md`  
**Version:** 1.0  
**Date:** 2026-08-20  

---

# 1. Purpose

This brief defines the target **Business IQ capture experience** for PreM3.

The design objective is to help PreM3 establish a robust, trusted understanding of a customer's business **before dataset evaluation begins**, while minimizing user fatigue, anxiety, and unnecessary disclosure.

The experience must convert business knowledge into durable `BusinessProfile` state. It is not simply an onboarding questionnaire and should not be designed as a generic chatbot.

### Core product statement

> **PreM3 should learn enough about the business to interpret marketing data responsibly, without forcing the user to become an MMM expert or complete an exhaustive questionnaire.**

The resulting experience should make the user feel that PreM3 is **understanding the business**, not merely collecting fields.

---

# 2. Product context

Business IQ is one of two foundational intelligence systems within PreM3:

```text
BUSINESS IQ
What the business means,
how decisions are made,
and what context matters
        │
        ├──────────────┐
        │              │
        ▼              ▼
  Planning path    Existing-data path
        │              │
        └──────┬───────┘
               ▼
            DATA IQ
What evidence exists,
how complete it is,
and whether it is model-ready
               │
               ▼
       MODELING CONTEXT
               │
               ▼
            Meridian
```

The Business IQ experience must therefore occur **before the product routes the user into data acquisition planning or dataset ingestion**.

The design should visually reinforce this progression:

```text
BUSINESS IQ  →  DATA IQ  →  MODELING
```

---

# 3. Fixed strategic decisions

The following are product decisions, not open design questions.

## 3.1 Capture model: structured-first hybrid

The primary capture surface is a **guided, structured workflow**.

Conversation is an embedded enrichment and clarification mechanism.

```text
STRUCTURED BUSINESS BASELINE
            ↓
BUSINESS_CONTEXT_READY
            ↓
BUSINESS PROFILE REVIEW
            ↓
DATA IQ / DATA INGESTION
            ↓
EVIDENCE-TRIGGERED CONVERSATION
            ↓
BUSINESS PROFILE IMPROVES
```

### Structured capture is preferred for

- business model
- industry/category
- markets
- primary KPI
- measurement objective
- material marketing channels
- broad channel roles
- broad budget-setting methods
- customer journey classifications
- pricing/promotion relevance
- competitive relevance
- seasonality relevance
- known business events
- prior-evidence availability

### Conversational capture is preferred for

- nuanced budget-setting behavior
- channel strategy and role clarification
- demand-generation vs demand-capture mechanics
- promotion/media coordination
- competitor response mechanisms
- unusual historical changes
- causal hypotheses
- prior experiments or previous MMM evidence
- explanations that do not fit bounded options

The product should not force users to choose between “form mode” and “chat mode.” Both methods populate the same BusinessProfile.

---

## 3.2 The ontology may be large; the initial experience must be small

The BusinessProfile can represent deep business intelligence over time.

The initial Business Baseline should require only approximately **8–14 concise interactions**, depending on branching.

Do not expose the full ontology as a giant form.

---

## 3.3 `UNKNOWN` is a valid answer

Users must be able to say:

- I don't know
- I'm not sure
- This does not apply
- I can answer this later

Unknown information should become explicit profile state rather than a silent default.

The UX must never punish a user for honestly not knowing something.

---

## 3.4 Readiness is conceptual, not percentage-complete

PreM3 uses `BUSINESS_CONTEXT_READY` to indicate that enough business context has been acknowledged to proceed.

A user does **not** need to fill every field.

A percentage may be used as secondary visual feedback, but it must not be the primary readiness mechanism.

Preferred language:

> **Business context ready**

rather than:

> **87% complete**

---

## 3.5 BusinessProfile is persistent and editable

Business IQ is not disposable onboarding state.

Users must eventually be able to:

- review what PreM3 understands
- correct facts
- confirm extracted knowledge
- mark information unknown
- revise information when the business changes
- see time-bounded events and changes
- understand the source of material facts

---

## 3.6 Business IQ precedes dataset evaluation

The user should not enter dataset evaluation without first establishing the minimum Business Baseline.

This is a fundamental change from the current Planner/data-routing experience.

---

## 3.7 Priors are expressed in business language

Users should not be required to understand Bayesian probability distributions.

The user-facing concept is **Prior knowledge** or **Existing evidence**.

Example explanation:

> **Prior knowledge** tells PreM3 what your organization already knows or reasonably believes about a marketing activity before a new model analyzes the current data. This can come from experiments, previous MMM studies, benchmarks, or expert knowledge.

PreM3 may later turn that knowledge into a **candidate prior recommendation**, but final model priors remain modeler-governed.

---

# 4. Primary UX objective

Optimize for:

> **Maximum decision-relevant Business IQ per unit of user effort and trust.**

The experience should feel:

- intelligent
- calm
- transparent
- progressive
- useful before modeling begins
- non-technical where possible
- professional enough for analysts/modelers
- approachable enough for marketers and business stakeholders

It should **not** feel like:

- tax software
- a compliance questionnaire
- an AI chatbot interrogation
- an enterprise CRM setup wizard
- an academic causal-inference exam
- a hidden attempt to collect confidential business information

---

# 5. Target users

The design must work for multiple likely participants.

## Primary

### Marketing / Growth leader

Knows:

- channel strategy
- business objectives
- budget process
- promotions
- competition

May not know:

- Bayesian terminology
- model specification concepts
- data engineering details

### Analyst / Measurement lead

Knows:

- KPI definitions
- historical media structure
- prior MMMs/experiments
- measurement objectives

May not know:

- every operational budget decision
- executive competitive strategy

## Secondary

### Data / analytics engineer

May begin setup but may need other business stakeholders to complete Business IQ.

### Agency / consultant

May know the marketing system deeply but should be able to mark client-specific facts as unknown or request confirmation.

### Modeler

Needs deeper causal context and prior evidence later, but should not be forced to re-enter baseline business information.

---

# 6. UX architecture

The recommended experience has five layers.

```text
1. ORIENTATION
   Why PreM3 needs business context
              ↓
2. BUSINESS BASELINE
   Fast structured workflow
              ↓
3. CONDITIONAL CONTEXT
   Only high-value follow-ups
              ↓
4. PROFILE REVIEW
   "What PreM3 understands"
              ↓
5. CONTINUOUS ENRICHMENT
   Agentic + evidence-triggered questions later
```

The initial design effort should focus on Layers 1–4 while establishing the interaction pattern for Layer 5.

---

# 7. Recommended screen / flow map

The designer should explore a concise wizard built around **conceptual sections**, not dozens of numbered questions.

Recommended flow:

```text
01  Welcome / Why Business IQ
02  Your Business
03  What Are We Trying to Measure?
04  Markets & Customer Journey
05  Marketing Portfolio
06  How Marketing Decisions Are Made
07  Business & Commercial Drivers
08  Competitive Landscape
09  Important Business Changes / Events
10  Existing Evidence / Prior Knowledge
11  What PreM3 Understands
12  Business Context Ready → Next Path
```

Not every user sees every follow-up inside every section.

---

# 8. Screen requirements

## Screen 01 — Welcome / Why Business IQ

### Goal

Establish trust and explain why PreM3 asks business questions before requesting data.

### Core message

Suggested direction:

> **Before we look at your data, tell PreM3 how your business works.**
>
> Marketing data shows what happened. Business context helps PreM3 understand why it may have happened and what matters for your model.

### Supporting reassurance

Communicate that:

- the process is short
- “I'm not sure” is always acceptable
- the profile can be updated later
- PreM3 asks deeper questions only when they matter
- business context is used to improve modeling and interpretation

### Optional visual

A simple three-stage architecture:

```text
Business IQ  →  Data IQ  →  Model
```

### Primary CTA

`Build my Business Profile`

Avoid technical language such as “configure semantic readiness.”

---

## Screen 02 — Your Business

### Goal

Establish basic operating context.

### Candidate captures

- business model
- industry/category
- primary products/services
- B2C / B2B / mixed
- revenue model where useful

### Interaction direction

Prefer:

- cards
- searchable select
- multiselect
- concise optional free text

Avoid asking for sensitive financial values here.

### Example prompt

> **Which best describes how your business makes money?**

Potential options could include:

- Ecommerce / direct-to-consumer
- Retail
- Subscription / SaaS
- Marketplace
- Lead generation
- Services
- Mixed model
- Other

The exact taxonomy belongs to the product contract/question catalog, not to hard-coded design.

---

## Screen 03 — What Are We Trying to Measure?

### Goal

Capture measurement objective and primary KPI in language the business understands.

### Design principle

Lead with the **decision**, not the model.

### Example lead question

> **What decision are you hoping this model will help you make?**

Potential objective cards:

- Understand channel effectiveness
- Reallocate marketing budget
- Plan total marketing investment
- Understand growth drivers
- Measure brand + performance together
- Compare scenarios
- Something else

### KPI capture

Ask:

> **What business outcome matters most for this analysis?**

Examples:

- Revenue
- Orders / purchases
- Leads
- Sign-ups
- Qualified opportunities
- Store visits
- Other

Allow a short business definition.

### Helpful microcopy

> Tell us what this metric means to your business. PreM3 will evaluate the actual data later.

This visually reinforces the Business IQ vs Data IQ boundary.

---

## Screen 04 — Markets & Customer Journey

### Goal

Understand commercial scope and how customers reach the outcome.

### Market capture

Potential structure:

- primary country/market
- other material markets
- whether regional differences matter
- whether marketing differs by region

### Journey capture

Prefer a small set of business-language cards:

- Immediate online purchase
- Longer consideration / delayed purchase
- Lead → sales process
- Store / offline conversion
- Subscription / recurring relationship
- Mixed journey

### Optional follow-up

> **Are new customers and existing customers marketed to differently?**

`Yes / No / Not sure`

Do not attempt to model the entire customer journey during baseline onboarding.

---

## Screen 05 — Marketing Portfolio

### Goal

Establish the material channel set and broad role of each channel.

### Primary interaction

Use a visual multiselect channel matrix or card set.

Example categories:

```text
Paid Search
Paid Social
Video / CTV
Programmatic
Audio
Retail Media
Organic / SEO
Email / CRM
Affiliate / Partner
Offline Media
Other
```

### Progressive follow-up

For each selected material channel, collect only the highest-value role information.

Example:

> **What role does Paid Search primarily play?**

- Capture existing demand
- Create/acquire new demand
- Retarget high-intent users
- Brand support
- Multiple roles
- Not sure

### User-effort guardrail

Do not show a separate long form for every channel.

Explore compact interaction patterns such as:

- inline role chips
- expandable channel cards
- matrix selection
- batch assignment + optional detail

### Agent escape hatch

Include an option such as:

`Describe how you use Paid Search`

This opens a focused conversational interaction rather than a separate general chatbot.

---

## Screen 06 — How Marketing Decisions Are Made

### Goal

Capture one of the highest-value Business IQ concepts: **why spend changes**.

### Lead question

> **What usually causes your team to increase, decrease, or shift marketing spend?**

Suggested multi-select concepts:

- Annual / quarterly plan
- Seasonality
- Recent performance
- Changes in customer demand
- Promotions
- Inventory / availability
- Competitor activity
- Agency recommendation
- Platform automation
- Executive discretion
- Other
- Not sure

### Follow-up behavior

Branch only when strategically useful.

For example, if `Recent performance` is selected:

> **Can stronger recent performance cause the team to increase spend within the same campaign period?**

`Yes / No / Sometimes / Not sure`

### “Why PreM3 asks” pattern

This screen should demonstrate the system's transparency model.

Example:

> **Why PreM3 asks**  
> If spend increases because demand or performance is already rising, that relationship can matter when estimating incremental impact.

The design team should create a reusable “Why PreM3 asks” interaction pattern.

---

## Screen 07 — Business & Commercial Drivers

### Goal

Identify which non-media business forces materially affect outcomes or marketing decisions.

### Do not use one combined question

Pricing, promotions, inventory, distribution, product changes, and seasonality must not be collapsed into a single `Yes/No` field.

### Recommended progressive cards

```text
Pricing changes
Promotions / discounts
Seasonality
Inventory / capacity
Product launches / assortment
Distribution / store footprint
External events
```

Each card can support:

- Important
- Not important
- Not sure

Only expand selected material categories.

### Example expansion — Promotions

> **Are media campaigns intentionally increased or coordinated around promotions?**

`Yes / No / Sometimes / Not sure`

### Example expansion — Inventory

> **Can inventory or capacity limits cause your team to reduce marketing?**

This is much more valuable than asking whether an inventory table exists. Data availability belongs to Data IQ.

---

## Screen 08 — Competitive Landscape

### Goal

Establish whether competitive activity materially affects the business or marketing system.

### Baseline question

> **Does competitor activity materially affect your demand, pricing, promotions, media costs, or marketing decisions?**

- Yes
- No
- Not sure

### If Yes

Progressively ask which mechanisms matter:

- Customer demand
- Pricing
- Promotions
- Media budgets
- Media costs / auction pressure
- Product positioning
- Search demand
- Other

### Optional competitor identification

Allow users to add:

- key competitors
- competitor groups
- market structure

Do not require users to disclose confidential competitive strategy during baseline.

### “Why PreM3 asks” example

> **Why PreM3 asks**  
> Competitor activity can affect both customer demand and your own marketing decisions, which may matter when PreM3 interprets historical relationships.

---

## Screen 09 — Important Business Changes / Events

### Goal

Capture major time-bounded changes that may explain historical behavior.

### Prompt direction

> **Were there any major business or marketing changes during the period you expect to analyze?**

Examples presented as selectable event types:

- Major promotion
- Price change
- Product launch
- New market
- Media launch or pause
- Budget policy change
- Brand / campaign strategy change
- Inventory constraint
- Store / distribution change
- Tracking change
- Competitor event
- Other
- None / Not sure

### Interaction

For selected events:

- name
- approximate date or date range
- affected markets/channels/products if known
- brief explanation

Users should be allowed to provide approximate timing.

The event timeline should eventually be visible in BusinessProfile review.

---

## Screen 10 — Existing Evidence / Prior Knowledge

### Goal

Discover credible existing evidence without forcing Bayesian terminology.

### This section is optional/high-value

It must be skippable.

### Lead question

> **Do you already have evidence about how effective any of your marketing activities are?**

Examples:

- Experiment / lift test
- Geo experiment
- Previous MMM
- Internal benchmark
- External benchmark / research
- Platform study
- Expert business knowledge
- No prior evidence
- Not sure

### If evidence exists

Allow the user to describe it in business language.

Examples:

> “Our last Search incrementality study suggested ROI around 1.5.”

> “Previous MMM work typically attributed 5–10% of revenue to Video.”

### Do not ask ordinary users for

- distribution families
- standard deviations
- hyperparameters
- Bayesian notation

### UX guardrail

Clearly communicate:

> Existing evidence may help PreM3 recommend model assumptions later. It does not automatically override what the new data shows.

Final prior configuration remains outside baseline onboarding.

---

## Screen 11 — What PreM3 Understands

### Goal

Turn data collection into visible intelligence and give the user agency.

This is a critical product screen.

### Suggested header

> **What PreM3 understands about your business**

### Recommended section summary

```text
Business & operating model       Confirmed
Measurement objective            Confirmed
Markets & customer journey       Confirmed
Marketing portfolio              Confirmed
Budget decision process          Confirmed
Commercial drivers               Partial
Competitive landscape            Confirmed
Business events                  2 recorded
Prior knowledge                  1 evidence source
Open questions                   3 can be resolved later
```

### Interaction requirements

Users should be able to:

- open a section
- edit a fact
- mark a fact incorrect
- mark a fact unknown
- confirm an extracted fact
- see relevant effective dates
- see whether information came from their answer vs later system evidence

### Important design principle

Do **not** visually imply that every partial/unknown area is a problem.

Some areas are legitimately irrelevant or unknown.

### Optional understanding card

A concise natural-language synthesis could appear above the structured sections:

> PreM3 understands that you are a U.S.-focused ecommerce business optimizing revenue across Search, Social, and Video. Search is primarily demand capture, budgets can respond to recent performance, and promotions materially affect both demand and media planning.

This summary must be grounded in structured BusinessProfile state.

---

## Screen 12 — Business Context Ready / Route Forward

### Goal

Create a clear completion moment and transition into the next workflow.

### State

When the minimum baseline has been acknowledged:

> **Business context ready**
>
> PreM3 now understands enough about how your business operates to begin planning or evaluating your data.

### Route options

Depending on product context:

- `I need a data acquisition plan`
- `I already have data`
- `Review my Business Profile`

### Architecture reinforcement

Visually show:

```text
Business IQ   ✓
     ↓
Data IQ       Next
     ↓
Modeling
```

---

# 9. Embedded agent interaction pattern

The conversational agent should be **contextual and embedded**, not a floating generic chatbot that takes over onboarding.

Recommended pattern:

```text
┌───────────────────────────────────────────────┐
│ What usually changes your Search budget?     │
│                                               │
│ □ Recent performance                         │
│ □ Customer demand                            │
│ □ Promotions                                 │
│ □ Fixed planning                             │
│ □ Other                                      │
│ □ Not sure                                   │
│                                               │
│ [ Tell PreM3 in your own words ]              │
└───────────────────────────────────────────────┘

Why PreM3 asks →
Budget-setting behavior can affect how historical
media relationships should be interpreted.
```

Selecting `Tell PreM3 in your own words` can open an inline or side-panel conversation focused on the current concept.

### Agent behavior after free-text answer

Example user answer:

> “We have a quarterly Search budget but the agency can push spend up if branded queries and ROAS are strong.”

PreM3 may respond:

> **I understood:**
> - Search has a quarterly planned budget.
> - In-period spending can increase based on performance.
> - Branded query demand can influence spending.
>
> Is that right?

Actions:

`Confirm` · `Edit` · `Try again`

Material agent extraction should not disappear directly into hidden profile state.

---

# 10. Conversation design rules

1. **One purpose per conversation.** Do not turn every field into open-ended chat.
2. **Use profile context.** Never ask something the user already confirmed unless the system detects a conflict or the fact is stale.
3. **Summarize extracted meaning.** Show users what PreM3 believes it learned.
4. **Allow correction before commitment.** Especially for causal/mechanism interpretations.
5. **Ask follow-ups only when information value is high.**
6. **Do not invent business facts.** Unknown remains unknown.
7. **Do not assign causal roles from user wording alone.** The profile may store hypotheses or candidate relationships.
8. **Do not expose unnecessary MMM jargon.** Explain jargon when necessary.
9. **Keep answers bounded when possible.** Conversation is for nuance, not for replacing structured capture.
10. **Never imply that prior beliefs guarantee model results.**

---

# 11. “Why PreM3 asks” design system

The design team should create a reusable trust pattern for non-obvious questions.

It may render as:

- inline helper text
- tooltip
- expandable explanation
- info icon + short panel

### Characteristics

- one or two sentences
- plain language
- explain the modeling relevance
- never sound accusatory
- never imply the user must know the answer

### Examples

#### Budget behavior

> If spending increases because demand is already rising, PreM3 needs to consider that relationship when interpreting media impact.

#### Competitive landscape

> Competitor activity can affect customer demand and your marketing decisions at the same time.

#### Promotions

> Promotions can change demand directly and can also change how much media you run.

#### Prior knowledge

> Previous experiments or MMM studies can provide credible information that may not be visible in the current dataset.

---

# 12. Trust, privacy, and sensitivity UX

BusinessProfile can contain commercially sensitive information. Trust should be designed into the experience rather than buried in legal copy.

## Principles

### Ask for relevance before precision

Prefer:

> Does profitability vary materially by product?

before:

> Enter gross margin by product.

### Explain why sensitive information is useful

When asking higher-sensitivity questions, show explicit value.

### Make optionality visible

Use language such as:

- Optional
- Helpful if known
- You can add this later
- Not required to continue

### Avoid unnecessary specificity

Exact revenue, margin, LTV, budget, and competitive strategy should not be baseline requirements unless the current modeling decision needs them.

### Local context positioning

The experience should support the product principle that proprietary Business IQ is customer-specific context, not generic cross-customer knowledge.

Product/legal teams can supply final policy wording; design should reserve clear space for concise trust messaging.

---

# 13. Progress and navigation

## Do

- show progress by conceptual section
- allow back/edit
- auto-save
- allow resume later
- branch without visibly “skipping 30 questions”
- tell the user when enough context exists to proceed

## Avoid

- `Question 17 of 46`
- a giant left-nav with every ontology field
- making optional enrichment look mandatory
- red-error styling for `UNKNOWN`
- forcing completion of irrelevant sections

### Suggested progress pattern

```text
Business       ✓
Objective      ✓
Marketing      ●
Context        ○
Review         ○
```

The design team may explore better alternatives, but progress should communicate **conceptual completion**, not raw question count.

---

# 14. Required answer states

Design components should support these user-intent states where relevant:

- Yes
- No
- Sometimes / Mixed
- Not sure
- Not applicable
- Answer later

Not every question needs every option.

The design must visibly distinguish:

- user intentionally answered `Not sure`
- user has not answered the question

That distinction is fundamental to `BUSINESS_CONTEXT_READY`.

---

# 15. BusinessProfile review states

The review UI should be able to represent at least:

- Confirmed
- Reported
- Inferred / needs confirmation
- Unknown acknowledged
- Conflicting
- Stale / needs review
- Not applicable

Do not overexpose internal ontology language if it harms usability. Human-readable labels are preferred.

Example mapping:

```text
USER_CONFIRMED   → Confirmed
USER_REPORTED    → Provided by you
INFERRED         → Needs confirmation
UNKNOWN          → Unknown
CONFLICTING      → Needs review
STALE            → May need updating
```

---

# 16. Evidence-triggered question pattern

The initial design should establish a reusable pattern for future Data IQ → Business IQ questions.

Example:

```text
PreM3 found something worth clarifying

Paid Social has no spend for six weeks in the dataset.

Was the channel intentionally paused during this period?

○ Yes, it was intentionally inactive
○ No, it should have data
○ I'm not sure

Why this matters →
This helps PreM3 distinguish true inactivity from missing data.
```

Another example:

```text
PreM3 found something worth clarifying

Search spend rises during the same periods when demand is already increasing.

Does your team increase Search spend when query volume or demand rises?

○ Yes
○ No
○ Sometimes
○ Not sure
```

This should feel like PreM3 is asking **fewer, smarter questions because it has seen evidence**.

---

# 17. Prior-knowledge UX requirements

The design must support the possibility that prior evidence is:

- absent
- known but not accessible yet
- described in natural language
- linked to a specific channel/treatment
- based on an experiment
- based on previous MMM work
- based on benchmark evidence
- based on expert judgment

The baseline experience should ask only whether relevant evidence exists.

Deep prior specification belongs later in applied modeling.

### Example user-facing card

```text
Existing evidence

Do you already have credible evidence about the impact of any
marketing activity?

Examples: lift tests, experiments, previous MMM studies, internal
benchmarks, or expert knowledge.

[ Yes ]  [ No ]  [ Not sure ]
```

If yes:

`Add evidence` should allow a lightweight description without requiring model parameters.

---

# 18. Accessibility and responsive requirements

Design should anticipate:

- desktop-first analytical use
- responsive tablet/mobile completion where practical
- keyboard navigation
- accessible focus states
- WCAG-compatible contrast
- screen-reader-friendly labels
- no meaning conveyed only through color
- long text wrapping without layout breakage
- multi-select patterns that remain usable with many channels/markets

The initial design review should include desktop and narrow viewport states for the main flow.

---

# 19. Design exploration areas

The following are intentionally open for the design team to explore.

## 19.1 Wizard structure

Explore:

- single-question cards
- compact section pages
- progressive cards
- hybrid section + question flow

The requirement is low fatigue and clear conceptual progress, not a specific layout.

## 19.2 Embedded agent location

Explore:

- inline expansion
- right-side contextual panel
- bottom sheet
- modal conversation

Avoid a generic floating chat bubble as the primary capture pattern.

## 19.3 “What PreM3 understands” visualization

Explore:

- structured profile cards
- knowledge map
- status sections
- natural-language summary + structured facts
- event timeline

Clarity and editability matter more than visual novelty.

## 19.4 Channel portfolio interaction

Explore efficient ways to capture channel + role without repetitive forms.

## 19.5 Business event timeline

Explore a lightweight timeline that can grow over time without becoming a project-management interface.

---

# 20. Explicitly out of scope for this design phase

Do not design full experiences for:

- dataset upload / BigQuery configuration
- Data IQ evaluation results
- Meridian model fitting
- posterior diagnostics
- final prior-distribution configuration
- budget optimization
- billing / subscription
- organization administration
- complete profile history/version diffing
- backend persistence architecture
- API design

The design may show the **handoff point** into Data IQ, but not the full Data IQ product.

---

# 21. Prototype scenarios required

The design team should prototype at least the following end-to-end scenarios.

## Scenario A — Standard happy path

User knows:

- business model
- KPI
- markets
- channels
- channel roles
- budget process
- promotion/seasonality context

No major unknowns.

Outcome: `BUSINESS_CONTEXT_READY`.

## Scenario B — User is unsure

User selects `Not sure` for:

- channel role
- competitor relevance
- budget-setting mechanism

The experience still allows readiness once the required concepts have been explicitly acknowledged.

## Scenario C — Competitive context matters

User says competitor activity affects demand and paid-search costs.

Show progressive follow-up without turning it into a long competitive-analysis exercise.

## Scenario D — Conversational clarification

User cannot describe Search budget behavior using the bounded options and uses `Tell PreM3 in your own words`.

PreM3 extracts structured meaning and requests confirmation.

## Scenario E — Existing prior evidence

User has a prior geo experiment or previous MMM.

Show a lightweight evidence capture and explain that it can inform later model recommendations.

## Scenario F — Business event history

User adds a product launch and six-week media pause.

Show how events appear in profile review.

## Scenario G — Resume / edit

Returning user re-enters the BusinessProfile and updates a previously confirmed fact.

The experience should make the profile feel persistent, not like redoing onboarding.

## Scenario H — Business IQ → Data IQ transition

User reaches `BUSINESS_CONTEXT_READY` and chooses either:

- I need a data acquisition plan
- I already have data

This should clearly demonstrate that Business IQ sits above both pathways.

---

# 22. Design deliverables requested

Recommended design package:

1. **End-to-end Business IQ user flow**
2. **Low-fidelity wireframes** for all primary screens
3. **High-fidelity desktop mockups** for the core baseline journey
4. **Responsive/narrow mockups** for representative screens
5. **Interactive prototype** covering Scenarios A, B, D, and H at minimum
6. **BusinessProfile review / “What PreM3 understands” concept**
7. **Embedded agent interaction pattern**
8. **“Why PreM3 asks” reusable pattern**
9. **Unknown / not-applicable / answer-later states**
10. **Competitive Landscape progressive-disclosure state**
11. **Prior Knowledge optional-enrichment state**
12. **Evidence-triggered question concept** for future Data IQ integration
13. **Business Context Ready completion state**
14. **Interaction annotations** sufficient for frontend planning

Design annotations should capture behavior and state transitions, but should not prescribe API/storage implementation.

---

# 23. Handoff expectations for frontend planning

The eventual frontend planning team should be able to infer from the approved designs:

- screen hierarchy
- reusable question patterns
- section progress behavior
- branching UX
- unknown/not-applicable states
- contextual agent behavior
- profile review/edit behavior
- transition into Data IQ
- trust/privacy messaging surfaces

Question text, options, branching, and requiredness should ultimately be driven by the product/question contract rather than permanently hard-coded into presentation components.

---

# 24. Handoff expectations for backend planning

The approved UX will imply backend capabilities such as:

- durable BusinessProfile
- question catalog / self-describing question schema
- branching metadata
- explicit unknown states
- per-field provenance
- profile review read model
- readiness evaluation
- agent-extracted candidate facts
- confirmation workflow
- business events
- prior evidence
- evidence-triggered questions
- profile snapshots/versioning

This brief does not prescribe endpoint or storage design.

---

# 25. Design acceptance criteria

A design direction is ready for frontend planning when all of the following are true.

### User burden

- A normal user can reach Business Context Ready without facing the full ontology.
- Optional/sensitive areas are visibly optional.
- Repetitive per-channel capture is minimized.

### Business IQ quality

- Core business, KPI, market, channel, budget, commercial, competitive, and event context can be represented.
- Unknown is explicit.
- Nuance can be captured without abandoning structure.

### Trust

- The experience explains why non-obvious questions matter.
- The user can inspect what PreM3 believes it knows.
- Agent-extracted meaning can be corrected.
- Sensitive questions are contextualized and progressively disclosed.

### Product architecture

- Business IQ visibly precedes both planning and data ingestion.
- `BUSINESS_CONTEXT_READY` is distinct from “profile complete.”
- The BusinessProfile feels persistent and reusable.
- The design can later accommodate evidence-triggered questions.

### Modeling discipline

- The UI does not imply that Business IQ automatically proves causality.
- Prior evidence is not presented as guaranteed model truth.
- The user is not asked to configure Bayesian distributions during baseline onboarding.

---

# 26. North-star experience

The final experience should communicate this idea:

> **PreM3 learns how your business actually works first. Then it looks at your data through that lens. As it finds evidence, it asks fewer and better questions.**

The product should progressively evolve from:

```text
Tell us about your business
```

into:

```text
Here is what PreM3 understands.
Here is what the data confirms.
Here are the few questions that still matter.
```

That progression is the core UX expression of Business IQ.

---

# 27. Companion specifications

Design decisions in this brief should remain aligned with:

- `BUSINESS_PROFILE_V1_SPEC.md` — canonical BusinessProfile ontology, knowledge primitives, readiness semantics, provenance, temporal behavior, prior-knowledge overlay, and Business IQ/Data IQ boundary.
- `BUSINESS_IQ_CAPTURE_STRATEGY.md` — capture-method philosophy, information-value classes, structured vs agentic capture, progressive questioning, sensitivity rules, and evidence-triggered enrichment.

If a proposed UI requires changing the underlying BusinessProfile semantics, treat that as a product/architecture decision and return it to the Business IQ strategy workstream rather than silently changing the contract in design.

---

**Strategic owner note:** This document defines the intended product experience and architectural guardrails. Frontend and backend workstreams should use the approved design plus the companion BusinessProfile specifications to create their implementation plans and engineering prompts.
