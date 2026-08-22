# PreM3 Business IQ Capture Strategy

**Status:** Strategic handoff companion to `BUSINESS_PROFILE_V1_SPEC.md`  
**Version:** 1.0  
**Date:** 2026-08-20  

---

## 1. Purpose

This document defines **how PreM3 should progressively acquire Business IQ** without creating a long, intrusive onboarding experience.

It does not define frontend components, backend endpoints, or implementation prompts. Those belong to the frontend and backend workstreams.

The BusinessProfile contract is the destination. This document defines the capture philosophy.

---

# 2. Recommendation: Hybrid capture

Use a hybrid model:

```text
STRUCTURED BASELINE
       ↓
High-confidence Business IQ foundation
       ↓
CONVERSATIONAL / AGENTIC ENRICHMENT
       ↓
Nuance, causal mechanisms, clarification
       ↓
DATA INGESTION + DATA IQ
       ↓
EVIDENCE-TRIGGERED QUESTIONS
       ↓
BUSINESS PROFILE REFINEMENT
       ↓
MODELER REVIEW WHERE REQUIRED
```

The system should not choose “form or chat.” Each method is appropriate for different knowledge types.

---

# 3. What deterministic structured capture is best for

Prefer bounded structured capture for:

- business model
- industry/category
- KPI selection/type
- market selection
- channel selection
- provider selection
- broad channel roles
- broad targeting roles
- budget-setting categories
- yes/no/unknown relevance questions
- promotion/pricing relevance
- competitive relevance
- date/date-range business events
- evidence-type classification for priors

Benefits:

- consistent semantics
- easier validation
- lower ambiguity
- fast completion
- deterministic branching
- better analytics on question effectiveness

---

# 4. What conversational capture is best for

Prefer agentic/conversational capture for questions such as:

- “How does your team decide when to increase Search spend?”
- “What typically causes your strongest demand spikes?”
- “How do promotions and paid media interact?”
- “What changed when that market launched?”
- “How does competitor behavior influence your pricing or media decisions?”
- “What do you believe Video does in the customer journey?”
- “What prior experiment or MMM evidence do you trust?”

The conversational layer should extract candidate structured facts, relationships, hypotheses, and events into BusinessProfile rather than storing important meaning only in a transcript.

---

# 5. Recommended capture stages

## Stage A — Business Baseline

Goal: reach `BUSINESS_CONTEXT_READY` with minimum fatigue.

Target: roughly 8–14 concise interactions after branching.

Capture:

- business model / offering
- industry/category
- measurement objective
- primary KPI meaning
- market scope
- material channels
- broad channel roles
- broad budget-setting process
- promotion relevance
- pricing relevance
- seasonality
- customer journey type
- competitive relevance
- major historical interventions

Optional high-value prompt:

- prior experiments/MMMs/benchmarks available?

### Rule

Do not block because a user genuinely does not know an answer. Record `UNKNOWN`.

---

## Stage B — Conditional Model Context

Trigger questions based on Stage A.

Examples:

### Paid Search selected

Ask about:

- brand/non-brand role
- demand capture
- query-volume influence
- automated bidding
- performance-responsive budgets

### Remarketing selected

Ask about:

- audience source
- prior behavior selection
- existing-customer exposure

### Promotions material

Ask about:

- promotion frequency
- media coordination
- market/product scope

### Pricing material

Ask about:

- pricing cadence
- media coordination
- market/product variation

### Competitive activity material

Ask which mechanisms matter:

- demand
- pricing
- promotion
- media budgets
- media costs

### Non-revenue KPI

Ask whether business has a credible economic translation/value per KPI or prefers outcome-unit interpretation.

---

## Stage C — Evidence-triggered refinement

After data inspection, ask only questions whose answers can resolve a material ambiguity.

Example triggers:

```text
Observed:
Search spend rises during demand spikes.

Question:
“Does your team automatically or manually increase Search budgets when demand/query volume rises?”
```

```text
Observed:
Paid Social is absent for six weeks.

Question:
“Was Paid Social intentionally paused during this period, or is the data missing?”
```

```text
Observed:
Revenue and media both change during a promotion window.

Question:
“Was media intentionally increased because of the promotion?”
```

```text
Observed:
Media costs rise during periods of competitor activity.

Question:
“Do competitor campaigns meaningfully affect your auction/media costs or your own spend decisions?”
```

Data should trigger semantic questions, not causal conclusions.

---

## Stage D — Prior Knowledge & Calibration Evidence

This stage is optional/high-value and should appear when:

- the organization has experiments;
- previous MMMs exist;
- internal/external benchmarks exist;
- domain experts possess meaningful beliefs;
- applied modeling identifies weakly identified effects or asks for calibration context.

### User-facing approach

Do not ask ordinary business users to specify probability distributions.

Ask:

- “Do you have previous evidence about how effective this channel is?”
- “What kind of evidence is it?”
- “What result did you consider credible?”
- “What range would you consider plausible?”
- “How confident are you in that evidence today?”

Then structure the answer into `PriorKnowledge`.

### Guardrail

Captured knowledge may support a **candidate prior recommendation**. Final Meridian prior configuration requires modeler governance.

---

# 6. Question information-value model

Each question should be classified as:

- `BASELINE_REQUIRED`
- `HIGH_VALUE_CONDITIONAL`
- `EVIDENCE_TRIGGERED`
- `OPTIONAL_ENRICHMENT`

A question should only be asked if one or more of these can materially change:

- data acquisition plan
- Business IQ readiness
- KPI interpretation
- geo strategy
- channel structure
- causal-role review
- confounder/control review
- non-media treatment review
- prior recommendation
- EDA interpretation
- model diagnostics
- optimization constraints
- decision interpretation

If the answer cannot change anything meaningful, do not ask it.

---

# 7. “Why PreM3 asks” pattern

For non-obvious or sensitive questions, provide a concise rationale.

Example:

> **Why PreM3 asks:** If spend increases because demand is already rising, the model needs to consider that relationship when estimating incrementality.

Competitive example:

> **Why PreM3 asks:** Competitor activity can affect both customer demand and your own media decisions, which can influence causal interpretation.

Prior example:

> **Why PreM3 asks:** Prior experiments or MMM studies can help the model incorporate credible knowledge that is not visible in the current dataset.

This supports trust and reduces the feeling of arbitrary interrogation.

---

# 8. Sensitivity-aware capture

Use a progression from low concern to higher precision.

Bad first question:

> “What is your exact gross margin by product?”

Better first question:

> “Does profitability vary materially by product or customer type?”

Only request exact values when the current modeling objective actually requires them.

The same principle applies to:

- revenue
- margin
- LTV
- confidential budget rules
- competitor strategy
- internal experiment results

---

# 9. Capture sources beyond forms/chat

The BusinessProfile contract should support progressive population from:

- structured onboarding
- conversational intake
- approved business documents
- media plans
- prior MMM reports
- experiment reports
- planning calendars
- channel taxonomy documents
- human corrections
- deterministic data evidence
- modeler decisions
- customer-local MEL outcomes

Extracted or inferred facts must remain visibly distinct from user-confirmed facts.

---

# 10. What the user should see

PreM3 should eventually expose a user-facing understanding surface such as:

```text
What PreM3 understands

Business & KPI             Confirmed
Markets                    Confirmed
Marketing portfolio        Confirmed
Budget process             Partial
Commercial drivers         Confirmed
Competitive landscape      Unknown acknowledged
Causal context             3 open questions
Prior knowledge            2 evidence sources
```

Users should be able to:

- inspect
- correct
- confirm
- mark unknown
- update effective dates
- understand where a fact came from

---

# 11. Avoid questionnaire fatigue

The system should follow these rules:

1. Do not ask everything up front.
2. Reuse confirmed durable facts.
3. Branch aggressively.
4. Ask one question to populate multiple related fields where safe.
5. Prefer bounded options for common concepts.
6. Use free text only when nuance is the value.
7. Allow “I don't know.”
8. Defer optional economics and prior details until useful.
9. Ask evidence-triggered questions only after a real ambiguity exists.
10. Show visible progress by conceptual area, not arbitrary question count.

---

# 12. Initial capture recommendation by domain

| Domain | Baseline wizard | Conditional wizard | Agentic | Evidence-triggered |
|---|---:|---:|---:|---:|
| Business identity | Yes | Maybe | Maybe | No |
| Measurement objective | Yes | Yes | Yes | Maybe |
| KPI framework | Yes | Yes | Yes | Yes |
| Economics | Minimal | Yes | Yes | Yes |
| Markets/geography | Yes | Yes | Maybe | Yes |
| Marketing portfolio | Yes | Yes | Yes | Yes |
| Budget decision process | Broad | Yes | **Yes** | **Yes** |
| Customer journey | Broad | Yes | **Yes** | Yes |
| Commercial drivers | Relevance | Yes | **Yes** | **Yes** |
| Competitive landscape | Relevance | Yes | **Yes** | **Yes** |
| External drivers | Relevance | Yes | Yes | **Yes** |
| Causal context | Minimal | Some | **Primary** | **Primary** |
| Prior knowledge | Optional relevance | Yes | **Primary** | **Primary** |

---

# 13. Handoff to frontend planning

Frontend should design an experience that:

- begins Business IQ before planner vs dataset routing;
- renders a compact structured baseline;
- uses backend-driven questions and branching;
- supports tri-state/unknown explicitly;
- transitions naturally into conversational clarification where valuable;
- exposes “Why PreM3 asks” explanations;
- allows BusinessProfile review/edit;
- treats prior knowledge in plain business language;
- does not require probability-distribution knowledge;
- supports progressive return visits without restarting onboarding.

This strategy does not prescribe component architecture.

---

# 14. Handoff to backend planning

Backend should design services that:

- make BusinessProfile first-class and durable;
- support self-describing/versioned question catalogs;
- record per-field provenance and confirmation;
- support structured and agentic capture into the same profile;
- record facts, events, hypotheses, relationships, knowledge gaps, and prior evidence;
- support temporal validity;
- calculate concept-aware `BUSINESS_CONTEXT_READY`;
- surface the current “understanding” read model;
- allow data evidence to create targeted semantic questions;
- snapshot BusinessProfile for model/run reproducibility.

This strategy does not prescribe endpoint or persistence implementation.

---

# 15. Strategic recommendation

The target product experience is:

```text
Tell PreM3 enough to understand the business
              ↓
Business baseline established
              ↓
Choose / infer next workflow
      ┌───────┴────────┐
      ▼                ▼
Need data plan      Have data
      │                │
      └───────┬────────┘
              ▼
           Data IQ
              ▼
PreM3 asks only the business questions
that the evidence makes valuable
              ▼
      Business IQ improves
              ▼
      Better modeling context
```

The objective is not maximum data collection.

> **The objective is maximum decision-relevant Business IQ per unit of user effort and trust.**

---

**Companion:** `BUSINESS_PROFILE_V1_SPEC.md`
