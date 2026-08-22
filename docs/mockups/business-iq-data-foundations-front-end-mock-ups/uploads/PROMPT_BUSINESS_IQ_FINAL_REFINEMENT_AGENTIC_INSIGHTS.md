# PROMPT — Business IQ Final Refinement Pass
## Evidence Guidance, Modeling Intelligence, Customer Learning & Business Profile “Wow” Layer

**Status:** Design refinement prompt  
**Audience:** Product design / UX  
**Applies to:** Current Business IQ standalone mockups and eventual in-product Business Profile  
**Priority:** Final Business IQ refinement before moving to Data IQ  
**Version:** `business-iq/final-refinement/1.0`  
**Date:** 2026-08-20

---

# 1. Objective

The current Business IQ flow is in a strong place.

This refinement pass should **not redesign the onboarding structure**.

Instead, improve four areas:

1. make the **Existing Evidence** step more useful and educational;
2. make the **Business Drivers** table easier to scan with restrained visual semantics;
3. turn the completed **Business Profile** into a high-value agentic insight surface;
4. subtly bring the customer along in the modeling/forecasting learning process without making the product feel academic or instructional.

The desired feeling after Business IQ is:

> **“PreM3 did not just collect my answers. It understood how my business works, identified what matters for measurement, and is already translating that context into useful modeling guidance.”**

This screen should create one of the first meaningful **wow moments** in the product.

---

# 2. Core design philosophy

## The learning layer should be useful, subtle and clear

PreM3 should help users learn *while they work*.

Avoid:

- tutorials before the user can proceed;
- long educational sidebars;
- mathematical explanations unless requested;
- technical jargon as primary copy;
- “AI teacher” language;
- large blocks of static documentation.

Prefer:

```text
Observation
    ↓
Why it matters
    ↓
PreM3 recommendation
    ↓
Optional deeper explanation
```

The product should teach through **applied context**.

Example:

> **What PreM3 noticed**  
> Paid Search can increase when customer demand increases.
>
> **Why this matters**  
> Search may capture demand that already exists, which can make causal impact harder to isolate.
>
> **What PreM3 will do**  
> Review Search alongside demand signals and recommend whether additional controls or sensitivity checks are warranted.
>
> `Learn why →`

The user receives value even if they never click `Learn why`.

---

# 3. Existing Evidence — improve guidance

The current screen asks:

> **Do you already have credible evidence about the impact of any marketing activity?**

Keep this.

The missing piece is helping users understand **what a useful answer looks like**.

---

# 4. Add a concrete example

Under the question or inside an expandable example component, show a short example.

## Recommended treatment

**Example of useful evidence**

> *“We ran a geo holdout for Paid Search in Q2 2025. The test suggested Search drove approximately 8–12% incremental revenue lift in the tested markets. The experiment covered six weeks and the US only.”*

Then show what PreM3 can extract:

```text
Evidence type       Geo experiment
Channel             Paid Search
Market              United States
Period              Q2 2025
Outcome              Revenue
Finding              Positive incremental effect
Supporting range     8–12% lift
```

This visually demonstrates the level of detail that is useful without requiring the user to know a schema.

---

# 5. Add several compact evidence examples

A small `See examples` affordance could open a short list such as:

### Geo / holdout experiment

> “We held out Paid Social in 12 DMAs for four weeks and observed a measurable decline in new-customer orders.”

### Platform lift study

> “Meta ran a conversion-lift study last year and reported positive incremental purchases.”

### Previous MMM

> “Our previous MMM estimated TV was efficient at current spend but showed Search becoming saturated.”

### Internal benchmark

> “Historically, when we launch in a new market, branded search grows after upper-funnel campaigns begin.”

### Expert / planning knowledge

> “Our team believes most branded search captures existing demand rather than creating new demand.”

The examples should make clear:

> **Evidence does not need to be perfect or formatted. PreM3 will structure what the user provides and preserve its uncertainty.**

---

# 6. Explain priors simply

Add a restrained `What are priors?` explanation.

Recommended copy:

> **What are priors?**  
> Meridian uses Bayesian modeling. A prior represents what we reasonably believe about a parameter *before* the current model sees the data.
>
> Existing experiments, previous MMMs, domain knowledge, and credible historical evidence can sometimes help inform those assumptions.
>
> You do **not** need to choose a probability distribution here.

Then:

> **Have evidence but not the file yet?**  
> Add the description now. Supporting reports, prior models, experiment files, or structured prior inputs can be attached during Data Foundation or later during model design.

This should reduce anxiety about the word “prior” while introducing a useful modeling concept.

---

# 7. Evidence should remain optional

Preserve the current framing:

> **High value if you have it, entirely skippable if you don’t.**

Do not make users feel they are disadvantaged if they have never run an experiment or MMM.

Avoid language that implies:

> “Good modelers should already have priors.”

Instead:

> **No prior evidence is a valid state. PreM3 will distinguish external evidence from assumptions inferred later from the current data.**

---

# 8. Evidence input UX

If the user selects `Yes`, expand an evidence capture component.

Recommended fields:

```text
Evidence type
[ dropdown / chips ]

What did you learn?
[ free text ]

Applies to
[ optional channel / business concept ]

Market
[ optional ]

Period
[ optional ]

Outcome
[ optional ]
```

Do not require every field.

PreM3 may extract structured candidates from the free text and present:

> **Here is what PreM3 understood**

with:

- Confirm
- Edit
- Keep unstructured

Supporting artifact CTA:

> `Attach supporting file later in Data Foundation`

---

# 9. Business Drivers — improve visual hierarchy

The current matrix is clear but visually flat.

Introduce subtle state color to help scanning.

## Recommended semantics

### Important

Use a **subtle green selected treatment**.

Example:

- very light green background;
- dark green text / border;
- restrained checkmark or selected state if useful.

Meaning:

> **The user says this is materially important to the business.**

### Somewhat important

Use the existing indigo / neutral selected treatment.

### Not material

Neutral gray.

### Not sure

Dashed / low-confidence neutral treatment.

---

# 10. Do not confuse “important” with “verified”

This distinction must remain clear.

Green in this table means:

> **Business importance declared by the user**

It does **not** mean:

- deterministic proof;
- data verified;
- model ready;
- issue resolved.

If the broader product uses cyan for verified/completed states, preserve that distinction.

Suggested design-system semantics:

```text
GREEN       User-declared materiality / importance
CYAN        Deterministically verified / completed
INDIGO      Active interaction / product structure
GRAY        Neutral / unknown / inactive
AMBER       Review / caution
RED         Blocked / error
```

Use these semantics consistently.

---

# 11. Business Drivers follow-ups should feel earned

When the user selects `Important`, the UI may reveal a concise follow-up immediately or after the table.

Example:

```text
Seasonality              IMPORTANT
Promotions               IMPORTANT
```

Then:

> **Two of these factors need a little more context**

instead of making the user feel like they triggered another questionnaire.

Use targeted follow-ups only for selected factors.

---

# 12. Elevate the completed Business Profile

The current review screen should become one of the most valuable Business IQ surfaces.

It should not merely say:

> “Here is what PreM3 understands.”

It should answer four questions:

1. **What does PreM3 know about my business?**
2. **What appears most important for measurement?**
3. **What does that imply for modeling and forecasting?**
4. **What should we pay attention to next?**

---

# 13. Add customer identity to the Business Profile

The profile should feel like a durable business asset, not an onboarding summary.

## Header concept

```text
[ Customer logo ]

ACME OUTDOORS
Business Intelligence Profile

Updated Aug 20, 2026 at 10:18 PM
Business Profile v3
```

Optional metadata:

```text
Scope        United States
Owner        Marketing Analytics
Status       Business Context Ready
```

---

# 14. Customer logo

Include the customer's brand/logo in the Business Profile.

Potential sources later:

- uploaded by customer;
- organization settings;
- company website / approved brand source;
- Clerk organization image if appropriate.

Fallback:

- customer initials / organization monogram.

Do not make logo acquisition a blocker.

The goal is to make the profile feel:

> **“This is Acme Outdoors’ measurement intelligence profile.”**

rather than:

> “This is a PreM3 form completion screen.”

---

# 15. Last edited / freshness

Add a clear timestamp near the profile title.

Example:

> **Last updated:** Aug 20, 2026 · 10:18 PM

Optional:

> **Updated by:** Alex Ortiz

Where possible, later distinguish:

```text
Business Profile last edited
Data evidence last refreshed
Model configuration last updated
```

These are different freshness concepts.

For Business IQ, the main requirement is visible profile freshness.

---

# 16. Create a “PreM3 understands your business” hero section

This should be more prominent than the current plain-language paragraph.

Recommended treatment:

```text
WHAT PREM3 UNDERSTANDS

Acme Outdoors is a US ecommerce business focused on transaction growth.
Paid Search is primarily a demand-capture channel, while Paid Social and
Linear TV play broader demand-creation roles.

Demand and marketing activity are materially influenced by promotions
and recurring seasonality. Search spend can also respond to customer
demand, which is important when estimating incremental Search impact.

Competitive effects are currently unknown.
```

Below:

```text
Based on:
✓ 27 confirmed business facts
✓ 6 acknowledged unknowns
✓ 4 material marketing channels
✓ 3 important business drivers
```

Do not overuse counts if they become arbitrary. Their purpose is to show the synthesis is grounded.

---

# 17. Add a “What matters most” section

This should identify the **highest-value business facts** for future measurement.

Suggested card:

## What matters most for measurement

### 1. Search may respond to existing demand

**Business evidence**  
Paid Search delivery can increase when customer demand rises.

**Why it matters**  
Search may capture demand already in-market, increasing confounding risk.

---

### 2. Promotions materially change demand

**Business evidence**  
Promotions are an important commercial driver and are coordinated with marketing.

**Why it matters**  
Promotion effects may need to be represented separately so media is not credited for demand created by the promotion itself.

---

### 3. Strong recurring seasonality

**Business evidence**  
Q4 and holiday periods materially increase demand.

**Why it matters**  
The model will need enough temporal flexibility to represent recurring demand patterns.

---

The user should immediately see:

> **PreM3 understands which facts matter, not just which answers were entered.**

---

# 18. Add a “Modeling considerations” section

This is the agentic wow layer.

Recommended heading:

> ## Modeling considerations

Supporting copy:

> Based on the business context you provided, PreM3 will carry these considerations into Data Foundation and Pre-Modeling.

Example cards:

---

### Search demand capture

**Consideration**  
Paid Search may partially respond to existing demand.

**PreM3 recommendation**  
Evaluate branded vs non-branded Search, demand controls, and Search sensitivity before final model specification.

**Authority**  
PreM3 modeling recommendation

`Why this matters →`

---

### Promotion effects

**Consideration**  
Promotions materially change revenue and may coincide with media changes.

**PreM3 recommendation**  
Locate promotion history during Data Foundation and evaluate it as a candidate non-media treatment/control.

`Learn how promotions affect MMM →`

---

### Seasonal demand

**Consideration**  
Demand rises materially during recurring Q4/holiday periods.

**PreM3 recommendation**  
Verify sufficient historical coverage and preserve enough temporal flexibility to represent recurring seasonality.

`Learn about time effects →`

---

# 19. Separate observations from recommendations

This is important for trust.

Each modeling insight should visibly separate:

```text
WHAT PREM3 KNOWS
User-confirmed business fact

WHY IT MATTERS
Interpretation

WHAT PREM3 RECOMMENDS
Advisory action
```

Do not present the recommendation as though it were another business fact.

Suggested visual hierarchy:

```text
Fact
↓
Implication
↓
Recommendation
```

This aligns the UX with the long-term authority model.

---

# 20. Add forecasting considerations

The Business Profile should not feel exclusively MMM-oriented.

Include a small section when relevant:

> ## Forecasting considerations

Examples:

### Recurring seasonality

> Q4 demand is materially different from baseline periods. Forecasting should preserve seasonal structure rather than treating recent Q4 growth as a permanent trend.

### Promotions

> Promotional periods may need separate features because they materially change demand.

### Inventory constraints

> Historical demand may understate unconstrained demand during stockouts.

This subtly reinforces that Business IQ supports the broader Marketing Investment Intelligence roadmap.

---

# 21. Potential “PreM3 Intelligence Brief” component

Consider naming the synthesis section:

> **PreM3 Intelligence Brief**

or:

> **Business Intelligence Brief**

Potential layout:

```text
PREM3 INTELLIGENCE BRIEF
─────────────────────────────────────────

What PreM3 understands
[ concise synthesis ]

What matters most
[ 3–5 ranked business considerations ]

Modeling considerations
[ 2–5 recommendations ]

Forecasting considerations
[ 0–3 recommendations ]

Open questions
[ unresolved business concepts ]

Next evidence PreM3 will look for
[ Data Foundation handoff ]
```

This is potentially much stronger than a conventional profile review.

---

# 22. Add “Next evidence PreM3 will look for”

This creates a natural bridge to Data IQ.

Example:

> ## Next, PreM3 will look for

Based on your Business IQ, Data Foundation will try to locate:

```text
✓ Revenue / transaction history
✓ Paid Search spend and execution
✓ Paid Social spend and execution
✓ Linear TV history
✓ Promotion calendar
✓ Seasonal history
? Competitive-demand evidence
```

Then:

> **You will not need to re-enter this information. PreM3 will use the Business Profile to guide discovery.**

CTA:

> **Continue to Data Foundation**

This is both useful and educational.

The user sees *why* Data IQ is searching for specific evidence.

---

# 23. Rank insights by consequence

Do not dump every inference onto the Business Profile.

Use a consequence-based hierarchy.

Recommended:

```text
HIGH CONSEQUENCE
Likely to materially affect model specification or interpretation.

MODELING CONSIDERATION
Important enough to review during Pre-Modeling.

CONTEXT
Useful business context, but not currently expected to drive a major decision.
```

In the UI, avoid alarming labels such as “HIGH RISK” unless warranted.

Potential simpler presentation:

- **Key consideration**
- **Worth reviewing**
- **Context**

---

# 24. Keep insights bounded

The agent should not produce ten paragraphs because the user supplied twenty answers.

Recommended target:

```text
3–5 most important considerations
2–4 recommendations
0–3 forecasting considerations
3–6 open questions
```

Additional insights can live behind:

> `View all considerations`

The goal is curation.

---

# 25. Ground every insight

Each insight should have structured support.

Example:

```text
Insight
Search may respond to existing demand

Based on
• User said Paid Search is primarily demand capture
• User said platform automation responds to query demand
• User said spend can change within the planning period

Knowledge source
Business IQ / user-confirmed
```

The user-facing view can keep this compact:

> **Based on 3 Business IQ facts** `View evidence`

This creates trust without clutter.

---

# 26. Deterministic + agentic split

The “wow” factor should not come from a generic LLM summary.

Use the system architecture intentionally.

## Deterministic layer

Provides structured facts such as:

- selected channels;
- channel roles;
- market scope;
- important commercial drivers;
- budget decision process;
- customer journey;
- prior-evidence availability;
- explicit unknowns;
- confirmed events.

## Agent layer

Uses those facts to generate:

- plain-language synthesis;
- causal/modeling considerations;
- recommended evidence to find;
- forecasting considerations;
- open-question prioritization.

## Governance

Every recommendation must remain labeled as:

> **PreM3 recommendation**

not:

> Official Meridian requirement

unless it is actually derived from an official requirement later in Pre-Modeling.

---

# 27. Add lightweight learning moments

Use short applied explanations throughout the Intelligence Brief.

Examples:

### Confounding

> **Quick concept — Confounding**  
> A confounder can influence both marketing activity and the business outcome. If promotions raise revenue *and* change media spend, the model needs enough evidence to separate those effects.

### Mediator

> **Quick concept — Mediator**  
> Sometimes marketing changes another behavior that then affects the outcome. PreM3 distinguishes these pathways before recommending whether a variable should be treated as a control.

### Prior

> **Quick concept — Prior**  
> A Bayesian prior expresses a reasonable belief before the current model sees the data. Credible experiments can sometimes help inform it.

### Seasonality

> **Quick concept — Seasonality**  
> Recurring demand patterns need to be represented so the model does not mistakenly assign normal seasonal growth to advertising.

These should be:

- one or two sentences;
- contextual;
- expandable;
- never required reading.

---

# 28. Learning receipt concept

A subtle future pattern worth mocking:

> **What you learned from Business IQ**

Example:

```text
3 modeling concepts surfaced

✓ Why Search demand can create confounding
✓ Why promotions may need separate treatment
✓ How prior evidence can inform Bayesian models
```

Do not turn this into gamification.

Potential location:

- small footer;
- profile activity panel;
- optional “Concepts surfaced” link.

The goal is to reinforce comprehension, not completion points.

---

# 29. Open questions should be prioritized

The current screen shows a large numeric open-question count.

A raw count such as `31` can feel noisy or discouraging.

Instead, prioritize.

Recommended:

```text
OPEN QUESTIONS

3 worth resolving before modeling
8 can be resolved from data
20 optional / lower priority
```

Or even:

```text
3 questions PreM3 may ask later
```

Then show examples:

```text
• Whether branded and non-branded Search are separately available
• Whether promotion history exists
• Whether inventory constraints are recorded historically
```

The number should help the user understand consequence, not reveal ontology completeness.

---

# 30. Replace “Partial” where possible

Several review sections currently display `Partial`.

That is technically understandable but vague.

Consider more meaningful states:

- Confirmed
- Known with gaps
- Unknown acknowledged
- Optional
- Needs review
- Not provided
- No events reported

For example:

```text
Measurement objective      Known with gaps
Markets & journey          Confirmed
Marketing portfolio        Confirmed
Decision process           Known with gaps
Commercial drivers         Confirmed
Competition                Unknown acknowledged
Business events            None reported
Prior evidence             Not provided
```

This is clearer than repeated `Partial`.

---

# 31. Business Profile hero layout concept

Potential composition:

```text
┌───────────────────────────────────────────────────────────────┐
│ [Acme logo]  ACME OUTDOORS                                   │
│              Business Intelligence Profile                    │
│              Updated Aug 20, 2026 · 10:18 PM                 │
│                                                               │
│ BUSINESS CONTEXT READY                                        │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ PREM3 INTELLIGENCE BRIEF                                      │
│                                                               │
│ Acme Outdoors is a US ecommerce business...                   │
│                                                               │
│ [27 confirmed facts] [6 unknowns] [4 channels]                │
└───────────────────────────────────────────────────────────────┘

┌────────────────────────────┬──────────────────────────────────┐
│ WHAT MATTERS MOST          │ MODELING CONSIDERATIONS          │
│                            │                                  │
│ Search demand              │ Review Search demand capture     │
│ Promotions                 │ Locate promotion history         │
│ Seasonality                │ Preserve temporal flexibility    │
└────────────────────────────┴──────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ FORECASTING CONSIDERATIONS                                    │
│ Seasonal demand · Promotions · Inventory                      │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ NEXT, PREM3 WILL LOOK FOR                                     │
│ Revenue · Search · Social · Promotions · TV · Competition     │
│                                                               │
│                           [Continue to Data Foundation]        │
└───────────────────────────────────────────────────────────────┘
```

---

# 32. Editing should remain first class

From the Intelligence Brief, users must still be able to reach the underlying facts.

Examples:

```text
Search may respond to demand
[ View supporting facts ]
```

opens:

```text
Paid Search role
Demand capture                 [Edit]

Platform automation
Responds to query demand       [Edit]

Allocation cadence
Quarterly                      [Edit]
```

Do not let AI synthesis hide the source profile.

---

# 33. Agent voice

The agent should sound analytical and useful.

Prefer:

> “Because Search spend can rise when demand rises, PreM3 will treat Search as a potential confounding review area.”

Avoid:

> “Great insight! This is super important!”

Prefer:

> “Promotion timing will be useful to locate in Data Foundation.”

Avoid:

> “You should definitely upload your promotion calendar.”

Prefer:

> “Based on the facts provided, PreM3 recommends…”

Avoid:

> “The correct model should…”

unless deterministic/modeling evidence later supports that certainty.

---

# 34. Explain what happens next

The Business Profile should end with a clear contract:

> **Business IQ provides the meaning. Data Foundation will now look for the evidence.**
>
> PreM3 will use your profile to discover likely data sources, identify missing evidence, and establish the governed BigQuery foundation used by Pre-Modeling.

This reinforces the product architecture without making the customer learn internal terminology.

---

# 35. Required design changes

## Evidence screen

- [ ] Add one high-quality full example of useful evidence.
- [ ] Add several compact example evidence types.
- [ ] Add simple Bayesian prior explanation.
- [ ] State explicitly that distributions are not chosen here.
- [ ] Explain that evidence/artifacts can be added during Data Foundation or later.
- [ ] Preserve optional/skippable framing.
- [ ] Show structured extraction after free-text evidence.

## Business Drivers

- [ ] Important selection receives subtle green treatment.
- [ ] Somewhat important remains indigo/neutral.
- [ ] Not material remains neutral.
- [ ] Not sure remains visually distinct.
- [ ] Color semantics do not collide with verified/completed state.
- [ ] Follow-ups appear only for materially relevant drivers.

## Business Profile

- [ ] Add customer logo / fallback identity.
- [ ] Add last-updated timestamp.
- [ ] Optionally show profile version.
- [ ] Expand plain-language synthesis into a prominent Intelligence Brief.
- [ ] Add `What matters most`.
- [ ] Add `Modeling considerations`.
- [ ] Add `Forecasting considerations` when relevant.
- [ ] Separate fact / implication / recommendation.
- [ ] Ground every insight in Business IQ facts.
- [ ] Make underlying facts editable.
- [ ] Replace generic `Partial` status where possible.
- [ ] Prioritize open questions instead of emphasizing raw completeness count.
- [ ] Add `Next, PreM3 will look for`.
- [ ] Primary CTA remains `Continue to Data Foundation`.

## Learning philosophy

- [ ] Add contextual `Why this matters` explanations.
- [ ] Add optional 1–2 sentence modeling concepts.
- [ ] No required educational reading.
- [ ] No gamification.
- [ ] No jargon without plain-language explanation.
- [ ] Learning is tied to the customer's actual facts.
- [ ] User can go deeper only when desired.

---

# 36. Prototype cases for this refinement

Design should mock at least these cases.

## Case A — Rich Business IQ

Acme Outdoors:

- ecommerce;
- US;
- Revenue / Orders;
- Paid Search;
- Paid Social;
- CTV;
- Streaming Audio;
- Search demand capture;
- promotions important;
- seasonality important;
- inventory somewhat important;
- prior geo experiment available.

The Intelligence Brief should produce a rich but concise result.

---

## Case B — Sparse / uncertain Business IQ

User selected many `Not sure` answers.

The profile should still feel valuable:

> “PreM3 understands the business model, objective, channel portfolio and markets. Several causal details are intentionally unresolved and can be clarified later from data.”

Do not punish uncertainty.

---

## Case C — No prior evidence

Evidence screen:

> No

Profile:

```text
Prior evidence
Not provided

PreM3 note
No external prior evidence was supplied. This is a valid starting point.
```

No warning styling.

---

## Case D — Prior evidence present

User supplies:

> “Paid Search geo experiment in Q2 2025 showed 8–12% revenue lift in the US.”

Profile should surface:

```text
Existing evidence
Paid Search geo experiment
US · Q2 2025 · Revenue
```

Modeling consideration:

> Evaluate whether this evidence is compatible with the eventual model scope before using it to inform a prior or calibration decision.

---

## Case E — Search confounding insight

Business IQ:

- Search = demand capture;
- platform automation responds to query demand;
- spend changes in-period.

Intelligence Brief should identify Search as a top modeling consideration.

---

# 37. Design north star

The finished Business Profile should communicate:

> **PreM3 understands the business well enough to know what evidence matters next and what modeling questions deserve attention.**

The first agentic “wow” moment is not:

> “AI summarized my form.”

It is:

> **“PreM3 connected several facts I provided, explained why those facts matter for measurement, and already has a sensible plan for what to investigate next.”**

And the learning philosophy is:

> **Teach through consequence, not curriculum.**

The customer should gradually understand:

- why demand capture matters;
- why confounders matter;
- why seasonality matters;
- why promotions matter;
- what priors are;
- why evidence quality matters;

because those concepts become relevant to **their own business**.

That is the tone and interaction pattern to carry into Data IQ, Pre-Modeling, and Modeling.
