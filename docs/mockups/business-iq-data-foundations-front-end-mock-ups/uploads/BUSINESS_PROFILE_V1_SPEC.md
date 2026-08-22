# PreM3 BusinessProfile v1 — Strategic Contract Specification

**Status:** Proposed canonical product/architecture contract  
**Owner:** Business IQ strategy / product architecture  
**Primary consumers:** Frontend, backend, planning, dataset intake, M3 Agent, applied modeling, MEL  
**Version:** `business-profile/1.0`  
**Date:** 2026-08-20  

---

## 1. Purpose

`BusinessProfile` is the first-class, persistent representation of what PreM3 knows about a customer's business, marketing system, commercial environment, measurement objectives, causal context, and prior knowledge relevant to media mix modeling.

It sits **above both planning and dataset ingestion**.

```text
Customer / Organization
        │
        ▼
BUSINESS INTELLIGENCE FOUNDATION
        │
        ▼
BusinessProfile / Business IQ
        │
        ├─────────────────────┐
        ▼                     ▼
Data Acquisition          Existing Data
Planning                  Ingestion
        │                     │
        └──────────┬──────────┘
                   ▼
                Data IQ
                   │
                   ▼
       Modeling Context Assembly
                   │
                   ▼
          Meridian / Modeling
```

The profile is **not** an onboarding form, chat transcript, flat customer record, or model configuration. It is a governed knowledge contract that may be populated progressively from structured input, conversation, documents, registry knowledge, deterministic data evidence, human confirmation, and later modeling outcomes.

### Core statement

> **Business context becomes typed, versioned, temporal, provenance-aware system state. It must not disappear into chat history or prompts.**

---

## 2. Why BusinessProfile exists

A dataset can show that spend and revenue changed together. It usually cannot establish **why** spend changed, what business intervention occurred, whether a channel was prospecting or remarketing, whether demand influenced budget, whether pricing changed, whether a competitor forced a response, or what prior experimental evidence the organization already possesses.

Current Meridian guidance makes this distinction important. Meridian recommends focusing control-variable collection on factors that affect both KPI and media execution, and notes that it can be practical to ask marketing planners what information affected budget and planning decisions. Meridian also identifies market competition and Google Query Volume as examples of potential controls. Pricing, promotions, and other non-media interventions can instead be modeled as treatments when they are intervenable.

PreM3 therefore needs two complementary knowledge systems:

- **Business IQ:** what the business means, how it operates, why decisions were made, and what prior knowledge exists.
- **Data IQ:** what evidence exists, where it resides, how complete/valid it is, and whether it satisfies modeling contracts.

Neither is sufficient alone.

---

## 3. Design principles

### BP-01 — Business first

A minimum Business Profile must exist before dataset evaluation begins. Users may upload only after the baseline business context has been acknowledged.

### BP-02 — Large ontology, small initial burden

The contract may eventually represent deep business knowledge without forcing users to answer every possible question at onboarding.

### BP-03 — Unknown is a valid answer

`UNKNOWN` is materially different from `NO`. PreM3 must never convert missing business knowledge into a silent assumption.

### BP-04 — Facts are temporal

Business truths can change. Price strategy, channel role, market presence, competitive pressure, KPI definitions, promotions, budget rules, and distribution conditions must support temporal validity.

### BP-05 — Provenance is mandatory for material facts

PreM3 must know where important knowledge came from and whether the user or modeler has confirmed it.

### BP-06 — Causal-first

BusinessProfile does not assign causal roles from correlation. It records business knowledge, hypotheses, relationships, and candidate causal relevance for later review.

### BP-07 — Prior knowledge is evidence, not final prior configuration

BusinessProfile may capture experiments, historical MMMs, benchmarks, and expert beliefs that can inform priors. It must not silently impose a final Meridian prior distribution.

### BP-08 — Customer-local by default

Proprietary Business IQ remains customer-local by default. It must not become global domain knowledge or cross-customer learning unless separately authorized and appropriately sanitized.

### BP-09 — Reproducible modeling context

Every modeling run should be able to identify the exact BusinessProfile version/fingerprint it consumed.

### BP-10 — Ask only when the answer can matter

Questions should be prioritized by whether an answer can materially change planning, readiness, causal interpretation, model specification, diagnostics, or decision interpretation.

---

## 4. Business IQ vs Data IQ boundary

| Topic | BusinessProfile / Business IQ | Data IQ |
|---|---|---|
| What does the company sell? | Yes | No |
| What KPI matters and why? | Yes | No |
| Which markets are strategically meaningful? | Yes | No |
| Which channels are prospecting vs remarketing? | Yes | No |
| Why does Search spend increase? | Yes | No |
| Are promotions coordinated with media? | Yes | No |
| Does competitor behavior alter pricing or spend? | Yes | No |
| Did a planned media pause occur? | Yes | Data later verifies evidence |
| Does a BigQuery table contain Search spend? | No | Yes |
| Are 6 weeks missing? | No | Yes |
| Is the KPI summable at the modeled grain? | No | Yes |
| Is historical coverage sufficient? | No | Yes |
| Are geo values aligned and complete? | No | Yes |
| Does prior experiment evidence exist? | Yes | Data IQ may validate artifact availability |
| Is the experiment artifact accessible/usable? | No | Yes |

### Cross-system example

```text
Business IQ:
Meta Prospecting was intentionally paused from 2026-04-01 to 2026-05-15
because inventory was constrained.

Data IQ:
Meta exposure/spend is absent for six modeled periods.

Combined interpretation:
The absence may represent confirmed inactivity rather than unknown missing data.
```

Business IQ supplies meaning. Data IQ supplies evidence.

---

## 5. BusinessProfile conceptual contract

```text
BusinessProfile
├── profile_id
├── schema_version
├── tenant_scope
├── workspace_scope
├── project_scope
├── status
├── business_identity
├── measurement_objectives[]
├── kpi_framework
├── economics
├── markets[]
├── marketing_portfolio
├── budget_decision_process
├── customer_journey
├── commercial_drivers
├── competitive_landscape
├── external_drivers
├── causal_context
├── prior_knowledge
├── business_events[]
├── facts[]
├── relationships[]
├── hypotheses[]
├── knowledge_gaps[]
├── readiness
├── version
├── fingerprint
├── created_at
└── updated_at
```

This is a **strategic semantic contract**, not a required storage layout. Backend engineering may normalize or denormalize persistence provided the observable contract and semantics remain intact.

---

# 6. Core knowledge primitives

BusinessProfile should not store all intelligence as flat scalar fields. At minimum it needs the following primitives.

## 6.1 BusinessFact

Represents a reported, extracted, observed, or inferred business truth.

```text
BusinessFact
├── fact_id
├── concept
├── value
├── value_type
├── unit
├── scope
├── knowledge_state
├── source_type
├── source_ref
├── question_id
├── confidence
├── confirmation_state
├── effective_from
├── effective_to
├── sensitivity_class
├── model_relevance[]
├── causal_role_candidate[]
├── modeler_review_required
├── created_at
└── updated_at
```

### Knowledge states

Recommended initial enum:

- `UNKNOWN`
- `USER_REPORTED`
- `EXTRACTED`
- `SYSTEM_OBSERVED`
- `INFERRED`
- `CONFLICTING`
- `STALE`

### Confirmation states

Keep confirmation distinct from knowledge state:

- `UNCONFIRMED`
- `USER_CONFIRMED`
- `MODELER_CONFIRMED`
- `REJECTED`

### Source types

Recommended initial enum:

- `USER`
- `DOCUMENT`
- `REGISTRY`
- `SYSTEM`
- `DATA_DERIVED`
- `MODEL_OUTPUT`
- `EXTERNAL_EVIDENCE`
- `INFERRED`

### Causal-role candidates

These are candidates, not autonomous assignments:

- `TREATMENT`
- `OUTCOME`
- `CONFOUNDER_CANDIDATE`
- `MEDIATOR_CANDIDATE`
- `EFFECT_MODIFIER_CANDIDATE`
- `COLLIDER_RISK`
- `CONTEXT_ONLY`
- `UNDETERMINED`

---

## 6.2 BusinessEvent

Represents a time-bounded intervention or business change.

```text
BusinessEvent
├── event_id
├── event_type
├── name
├── description
├── start_date
├── end_date
├── markets[]
├── products[]
├── channels[]
├── expected_business_effect
├── expected_media_effect
├── source_type
├── source_ref
├── confidence
├── confirmation_state
└── sensitivity_class
```

Candidate event types:

- `PROMOTION`
- `PRICE_CHANGE`
- `PRODUCT_LAUNCH`
- `PRODUCT_DISCONTINUATION`
- `MARKET_ENTRY`
- `MARKET_EXIT`
- `MEDIA_LAUNCH`
- `MEDIA_PAUSE`
- `BUDGET_POLICY_CHANGE`
- `CAMPAIGN_STRATEGY_CHANGE`
- `BRAND_REFRESH`
- `TRACKING_CHANGE`
- `DISTRIBUTION_CHANGE`
- `STORE_OPENING`
- `STORE_CLOSURE`
- `INVENTORY_CONSTRAINT`
- `CAPACITY_CONSTRAINT`
- `COMPETITOR_EVENT`
- `REGULATORY_EVENT`
- `MACRO_EVENT`
- `OTHER`

---

## 6.3 BusinessRelationship

Represents typed relationships between entities.

```text
BusinessRelationship
├── relationship_id
├── subject_ref
├── predicate
├── object_ref
├── effective_from
├── effective_to
├── source_type
├── confidence
└── confirmation_state
```

Candidate predicates:

- `SELLS_IN`
- `TARGETS`
- `PROMOTES`
- `CAPTURES_DEMAND_FROM`
- `CREATES_DEMAND_FOR`
- `BUDGET_DEPENDS_ON`
- `COORDINATED_WITH`
- `COMPETES_WITH`
- `AFFECTS_AVAILABILITY`
- `SHARES_AUDIENCE_WITH`
- `PRECEDES`
- `INFLUENCES`

---

## 6.4 BusinessHypothesis / CausalClaim

A hypothesis is not the same as a fact.

```text
BusinessHypothesis
├── hypothesis_id
├── statement
├── entities[]
├── causal_role_candidate
├── evidence_refs[]
├── confidence
├── confirmation_state
├── status
└── modeler_review_required
```

Recommended statuses:

- `OPEN`
- `SUPPORTED`
- `CONTRADICTED`
- `RESOLVED`
- `NOT_MODEL_RELEVANT`

Example:

> “Promotions increase branded search demand, and Search spend rises automatically with that demand.”

This should be represented as a hypothesis/relationship requiring evidence and review, not silently encoded as a model rule.

---

## 6.5 KnowledgeGap

Represents a known unknown or unresolved contradiction.

```text
KnowledgeGap
├── gap_id
├── concept
├── reason
├── priority
├── blocks_business_context_ready
├── affects[]
├── resolution_actor
├── suggested_question_id
├── status
└── created_at
```

Statuses:

- `OPEN`
- `ANSWERED`
- `WAIVED`
- `NOT_APPLICABLE`

The system should prefer an explicit `KnowledgeGap` over inventing a value.

---

# 7. BusinessProfile ontology

The v1 ontology contains **12 business domains plus one modeling-knowledge overlay**.

## Domain 1 — Business Identity & Operating Model

Purpose: understand the company and the commercial system in which marketing operates.

### Candidate fields

- `business_model`
- `industry`
- `industry_subcategory`
- `customer_type` — B2C, B2B, mixed
- `revenue_model` — transactional, subscription, marketplace, lead-gen, services, mixed
- `primary_products_or_services[]`
- `business_units[]`
- `brand_portfolio[]`
- `online_offline_mix`
- `business_maturity`
- `operating_history_class`

### Baseline priority

`BASELINE_REQUIRED` for business model, industry/category, and primary offering.

---

## Domain 2 — Measurement Objectives & Decision Context

Purpose: define what the MMM is intended to help decide.

### Candidate fields

- `objective_id`
- `decision_question`
- `objective_type`
- `decision_owner_role`
- `planning_horizon`
- `optimization_horizon`
- `decision_frequency`
- `primary_business_constraint`
- `preserve_or_protect_constraints[]`
- `success_definition`

### Recommended objective types

- `MEASURE_INCREMENTAL_CONTRIBUTION`
- `UNDERSTAND_CHANNEL_EFFECTIVENESS`
- `REALLOCATE_BUDGET`
- `PLAN_TOTAL_BUDGET`
- `UNDERSTAND_GROWTH_DRIVERS`
- `MEASURE_BRAND_AND_PERFORMANCE_MIX`
- `TEST_SCENARIOS`
- `OTHER`

### Example

> Determine quarterly allocation across six paid-media channels while preserving a minimum level of brand-video investment.

This is materially stronger than a generic free-text “optimize marketing.”

---

## Domain 3 — KPI Framework & Outcome Semantics

Purpose: establish what is being modeled and how the business interprets it.

### Candidate fields

- `primary_kpi.name`
- `primary_kpi.business_definition`
- `primary_kpi.kpi_type`
- `primary_kpi.revenue_or_non_revenue`
- `primary_kpi.value_unit`
- `primary_kpi.conversion_definition`
- `primary_kpi.online_offline_scope`
- `primary_kpi.definition_effective_from`
- `secondary_kpis[]`
- `revenue_translation_relevant`
- `kpi_hierarchy[]`

### Strategic rule

Business IQ records KPI meaning. Data IQ validates whether the supplied KPI series satisfies Meridian data requirements.

---

## Domain 4 — Business Economics

Purpose: capture economically relevant context without making sensitive financial disclosure mandatory.

### Candidate fields

- `economics_relevance`
- `average_order_or_contract_value_class`
- `gross_margin_relevance`
- `margin_variability`
- `ltv_relevance`
- `repeat_purchase_relevance`
- `customer_acquisition_economics_relevance`
- `profitability_varies_by_product`
- `profitability_varies_by_market`

### Sensitivity rule

Exact margin, LTV, revenue, or contract values should normally be `OPTIONAL_ENRICHMENT` unless required for a specific modeling decision. Prefer categorical relevance questions before requesting precise confidential values.

---

## Domain 5 — Markets & Geography

Purpose: understand commercial geography before deciding whether geo modeling is useful or feasible.

### Candidate fields

- `primary_market`
- `operating_markets[]`
- `market_hierarchy`
- `meaningful_regional_differences`
- `marketing_varies_by_geo`
- `pricing_varies_by_geo`
- `distribution_varies_by_geo`
- `product_mix_varies_by_geo`
- `market_maturity_varies_by_geo`
- `geo_modeling_strategically_relevant`

### Strategic rule

Business IQ answers whether geography matters. Data IQ answers whether usable geo-level data exists.

---

## Domain 6 — Marketing Portfolio & Channel Roles

Purpose: understand not merely which channels exist, but what role each plays.

### `MarketingChannelProfile`

```text
MarketingChannelProfile
├── channel_id
├── canonical_channel_type
├── business_label
├── providers[]
├── role[]
├── funnel_role[]
├── targeting_role[]
├── paid_or_organic
├── always_on
├── flighting_pattern
├── active_markets[]
├── promoted_products[]
├── budget_owner_role
├── budget_setting_methods[]
├── automation_level
├── materiality
├── active_from
├── active_to
└── notes
```

### Channel roles

- `DEMAND_CREATION`
- `DEMAND_CAPTURE`
- `BRAND_BUILDING`
- `PROSPECTING`
- `RETARGETING`
- `RETENTION`
- `CONVERSION`
- `LOCAL_ACTIVATION`
- `PARTNER_OR_RETAIL_SUPPORT`
- `MIXED`
- `UNKNOWN`

### Targeting roles

- `BROAD`
- `PROSPECTING`
- `REMARKETING`
- `EXISTING_CUSTOMER`
- `CRM_AUDIENCE`
- `LOOKALIKE`
- `HIGH_INTENT`
- `CONTEXTUAL`
- `MIXED`
- `UNKNOWN`

### Search-specific extension

If Paid Search is material, conditionally capture:

- brand vs non-brand mix
- demand capture vs demand generation belief
- whether budgets react to query volume
- automated bidding usage
- performance-threshold rules
- seasonality/demand effects

### Remarketing-specific extension

If remarketing is material, capture audience selection logic and whether prior customer behavior determines exposure.

---

## Domain 7 — Budget Decision Process

Purpose: understand what causes marketing execution to change.

This is one of the highest-value Business IQ domains for causal modeling.

### Candidate fields

- `total_budget_setting_method[]`
- `channel_allocation_method[]`
- `in_period_reallocation_allowed`
- `reallocation_frequency`
- `budget_owner_roles[]`
- `decision_inputs[]`
- `performance_feedback_used`
- `demand_signals_used`
- `inventory_signals_used`
- `promotion_calendar_used`
- `competitor_signals_used`
- `platform_automation_used`
- `known_budget_policy_changes[]`

### Budget-setting methods

- `FIXED_PLAN`
- `SEASONAL_PLAN`
- `PERFORMANCE_BASED`
- `DEMAND_RESPONSIVE`
- `INVENTORY_RESPONSIVE`
- `PROMOTION_COORDINATED`
- `COMPETITOR_RESPONSIVE`
- `AGENCY_DISCRETION`
- `PLATFORM_AUTOMATION`
- `EXECUTIVE_DISCRETION`
- `MIXED`
- `UNKNOWN`

### Why it matters

A channel can appear highly correlated with the KPI because the business increases spend when demand is already rising. The budget decision process is therefore potential confounding context, not merely operational trivia.

---

## Domain 8 — Customer Journey & Demand Mechanics

Purpose: understand how customers move from demand creation to conversion and how media reaches them.

### Candidate fields

- `journey_type`
- `typical_sales_cycle`
- `immediate_vs_delayed_conversion`
- `new_vs_repeat_importance`
- `online_vs_offline_conversion`
- `lead_gen_vs_direct_commerce`
- `crm_lifecycle_relevance`
- `brand_demand_relevance`
- `search_capture_relevance`
- `remarketing_relevance`
- `sales_assisted_conversion`
- `cross_device_or_offline_complexity`

### Strategic rule

`hasFirstPartyCrm` is insufficient as Business IQ. The business meaning of CRM/lifecycle belongs here; source availability belongs in Data IQ.

---

## Domain 9 — Commercial Drivers

Purpose: capture intervenable and operational factors that may affect KPI, media, or both.

### Subdomains

#### Pricing

- pricing changes materially
- pricing cadence
- price decisions coordinated with media
- price varies by product/market
- major historical price changes

#### Promotions

- promotion frequency
- promotion types
- promotion calendar relevance
- media coordinated with promotions
- promotion targeting
- major historical promotions

#### Availability / Inventory / Capacity

- inventory constrains demand
- inventory constrains media
- stockouts materially occur
- capacity constraints
- lead-time constraints

#### Product / Assortment

- launches
- discontinuations
- assortment shifts
- packaging/design changes

#### Distribution

- store openings/closures
- retailer expansion/contraction
- distribution footprint changes

### Strategic rule

The current combined `hasPromoPricingSeasonality` field must be retired. Pricing, promotion, and seasonality have different meanings and modeling implications.

---

## Domain 10 — Competitive Landscape

Purpose: explicitly represent competitive dynamics because competition can affect demand, pricing, promotions, channel costs, media execution, and budget decisions.

### `CompetitiveLandscape`

```text
CompetitiveLandscape
├── relevance
├── market_structure
├── key_competitors[]
├── competitor_groups[]
├── relative_brand_position
├── competitor_pricing_intensity
├── competitor_promotion_intensity
├── competitor_media_intensity
├── competitor_search_pressure
├── competitor_activity_affects_demand
├── competitor_activity_affects_pricing
├── competitor_activity_affects_promotions
├── competitor_activity_affects_media_budget
├── competitor_activity_affects_media_cost
├── known_competitor_events[]
├── competitive_data_known_to_exist
└── notes
```

### Market-structure values

- `FRAGMENTED`
- `SEVERAL_MAJOR_PLAYERS`
- `HIGHLY_CONCENTRATED`
- `CATEGORY_LEADER`
- `CHALLENGER`
- `UNKNOWN`

### Strategic rule

Competitive context is Business IQ. Whether competitor price, sales, share-of-search, media spend, market share, or other proxy data actually exists is Data IQ.

---

## Domain 11 — External Drivers & Seasonality

Purpose: identify non-company factors that may affect business demand or planning.

### Candidate factors

- seasonality pattern
- holidays/events
- weather sensitivity
- macroeconomic sensitivity
- interest-rate sensitivity
- housing-market sensitivity
- tourism/travel sensitivity
- regulatory sensitivity
- sports/event sensitivity
- category demand shocks
- other material external factors

### Strategic rule

A factor being relevant to the business does not automatically make it a control variable. It becomes a candidate for modeling review.

---

## Domain 12 — Causal Context & Known Decision Mechanisms

Purpose: record the semantic facts the dataset cannot establish on its own.

### Candidate fields / relationships

- `known_confounder_candidates[]`
- `known_mediator_candidates[]`
- `known_effect_modifiers[]`
- `selection_mechanisms[]`
- `targeting_mechanisms[]`
- `budget_response_mechanisms[]`
- `promotion_media_coordination[]`
- `search_demand_relationships[]`
- `organic_media_relationships[]`
- `inventory_media_relationships[]`
- `competitive_response_relationships[]`
- `known_reverse_causality_risks[]`
- `open_causal_questions[]`

### Strategic rule

PreM3 may rank or surface causal candidates, but causal role must not be assigned solely from correlation or agent inference.

---

# 8. Modeling Knowledge Overlay — Prior Knowledge & Calibration Evidence

Priors are modeled as a governed **knowledge overlay** associated with BusinessProfile rather than an ordinary business attribute.

## 8.1 User-facing definition

> **Prior knowledge** is information your organization already has about the likely impact of a marketing activity before the new model analyzes the current dataset. It can come from experiments, previous MMM studies, internal benchmarks, external research, or informed expert judgment.

The user should not be required to understand probability distributions to provide useful prior knowledge.

## 8.2 `PriorKnowledgeProfile`

```text
PriorKnowledgeProfile
├── availability
├── evidence_sources[]
├── treatment_knowledge[]
├── experiment_evidence[]
├── historical_mmm_evidence[]
├── benchmark_evidence[]
├── expert_beliefs[]
├── candidate_prior_recommendations[]
└── unresolved_prior_questions[]
```

## 8.3 `PriorKnowledge`

```text
PriorKnowledge
├── prior_knowledge_id
├── treatment_ref
├── treatment_type
├── prior_type_candidate
├── belief
├── evidence_type
├── evidence_ref
├── evidence_quality
├── confidence
├── valid_from
├── valid_to
├── confirmation_state
├── modeler_review_required
└── notes
```

### Treatment types

- `PAID_MEDIA`
- `ORGANIC_MEDIA`
- `NON_MEDIA_TREATMENT`

### Meridian-aligned prior-type candidates

- `ROI`
- `MROI`
- `CONTRIBUTION`
- `COEFFICIENT`

Current Meridian guidance supports ROI, mROI, Contribution, and Coefficient treatment-prior types. ROI and mROI apply to paid media; Contribution and Coefficient can also apply to organic media and non-media treatments. Meridian describes ROI as the usual intuitive paid-media prior, Contribution as useful where spend is absent, and Coefficient as less naturally interpretable for business users.

### Evidence types

- `RANDOMIZED_EXPERIMENT`
- `GEO_EXPERIMENT`
- `LIFT_TEST`
- `HISTORICAL_MMM`
- `INTERNAL_BENCHMARK`
- `EXTERNAL_BENCHMARK`
- `PLATFORM_STUDY`
- `EXPERT_JUDGMENT`
- `OTHER`
- `UNKNOWN`

### Evidence-quality classes

- `STRONG_EMPIRICAL`
- `EMPIRICAL`
- `INTERNAL_BENCHMARK`
- `EXTERNAL_BENCHMARK`
- `EXPERT_BELIEF`
- `UNASSESSED`

## 8.4 Belief representation

BusinessProfile should store beliefs in business language where possible:

```text
PriorBelief
├── metric
├── expected_value
├── plausible_low
├── plausible_high
├── direction
├── unit
└── free_text_rationale
```

Examples:

- “Our last Search incrementality study suggested ROI near 1.5.”
- “We believe Video contributes roughly 5–10% of total revenue.”
- “We expect promotions to increase units sold.”

## 8.5 Guardrail

```text
BusinessProfile prior evidence
        ↓
PreM3 candidate prior recommendation
        ↓
Modeler review / approval
        ↓
Final Meridian ModelSpec / PriorDistribution
```

The BusinessProfile **must not** silently turn a user's business answer into final model configuration.

---

# 9. Field criticality classes

Every field/question should carry one of four information-value classes.

## `BASELINE_REQUIRED`

Needed to establish a minimum usable business context before dataset evaluation.

## `HIGH_VALUE_CONDITIONAL`

Important when triggered by business type, channel mix, measurement objective, or other prior answers.

## `EVIDENCE_TRIGGERED`

Ask only when observed data or model evidence makes the answer valuable.

## `OPTIONAL_ENRICHMENT`

Useful but not necessary for the current decision or model.

This classification belongs in the question/catalog metadata, not hard-coded in frontend behavior.

---

# 10. BUSINESS_CONTEXT_READY gate

`BusinessProfile` can be incomplete while still being ready to proceed.

The gate should mean:

> **PreM3 has enough acknowledged business context to begin interpreting the customer's data responsibly.**

It does **not** mean every Business IQ field is known.

## 10.1 Proposed status model

- `NOT_STARTED`
- `IN_PROGRESS`
- `BUSINESS_CONTEXT_READY`
- `REVIEW_REQUIRED`
- `STALE`

## 10.2 Baseline requirements

Before dataset evaluation, PreM3 should know or explicitly acknowledge `UNKNOWN` for:

1. business model / primary offering
2. industry/category
3. primary measurement objective
4. primary KPI concept and business definition
5. markets / scope
6. material marketing channels
7. broad role of each material channel
8. broad budget-setting process
9. pricing behavior relevance
10. promotion behavior relevance
11. seasonality / major recurring demand patterns
12. customer journey type
13. competitive-landscape relevance
14. major known historical business interventions/events

### Conditional baseline requirements

Examples:

- Paid Search material → ask broad Search role and whether spend reacts to demand/query volume.
- Remarketing material → ask whether prior customer behavior determines exposure.
- Offline sales material → acknowledge online/offline outcome relationship.
- Promotions material → ask whether media is coordinated with promotions.
- Competitive relevance = yes → ask whether competitor activity changes demand, pricing, promotion, or media decisions.

## 10.3 Unknown vs missing

A user may satisfy a baseline element by explicitly stating `UNKNOWN` where they genuinely do not know.

What should block readiness is an **unacknowledged required concept**, not an honest unknown.

Example:

```text
budget_setting_process = UNKNOWN
knowledge_state = USER_REPORTED
```

is valid business context.

No answer at all is not.

## 10.4 Readiness must not be a superficial percentage

A UI may display coverage, but the backend gate should be concept-aware. A profile with 90 optional enrichment fields complete but no KPI definition is not ready.

---

# 11. Progressive Business IQ levels

The contract should support progressive enrichment.

## Level 1 — Business Baseline

Universal prerequisite. Target: approximately 8–14 concise interactions depending on branching.

## Level 2 — Model Context

Conditional questions based on the business model, channel portfolio, KPI, customer journey, commercial drivers, and competitive landscape.

## Level 3 — Deep Causal Context

Questions triggered by observed data, EDA, model design, prior evidence, or unresolved causal mechanisms.

This allows the ontology to be broad without creating onboarding fatigue.

---

# 12. Question-catalog relationship

`BusinessProfile` and `BusinessQuestionCatalog` are separate contracts.

```text
Structured Wizard ─┐
                   │
Agent Conversation ├────► BusinessQuestionCatalog ─────► BusinessProfile
                   │
Document Extraction┤
                   │
Data Evidence ─────┘
```

One profile field may be populated by multiple capture mechanisms.

A question record should eventually support:

```text
BusinessQuestion
├── question_id
├── catalog_version
├── topic
├── prompt
├── help_text
├── why_preM3_asks
├── answer_type
├── requiredness
├── field_targets[]
├── trigger_conditions[]
├── options[]
├── sensitivity_class
├── information_value_class
├── follow_up_rules[]
└── retirement_state
```

The frontend should render the backend question schema rather than owning question text, options, sequencing, or branching logic.

---

# 13. Scope and inheritance

Business knowledge exists at different scopes.

Recommended conceptual scopes:

- `TENANT`
- `WORKSPACE`
- `PROJECT`
- `BRAND`
- `MARKET`
- `PRODUCT`
- `CHANNEL`
- `TREATMENT`
- `RUN`

Examples:

```text
TENANT:
“We are a B2C ecommerce retailer.”

PROJECT:
“This MMM evaluates US ecommerce revenue.”

CHANNEL:
“Paid Search is primarily demand capture.”

MARKET:
“California pricing differs from national pricing.”

RUN / EVENT:
“Meta Prospecting was paused during weeks 14–18.”
```

Backend engineering should support reuse/inheritance without forcing users to re-answer durable facts for every project. Project-specific overrides must remain explicit and provenance-aware.

---

# 14. Temporal semantics

Every material fact should support one of:

- `PERSISTENT`
- `INTERVAL`
- `EVENT`

Examples:

```text
PERSISTENT:
Business model = B2C ecommerce

INTERVAL:
Paid Search budget policy = performance-based
2025-01-01 through 2026-03-31

EVENT:
National price increase = 8%
2026-07-15
```

Facts without temporal semantics should not be assumed eternal.

---

# 15. Sensitivity and privacy classes

Recommended initial classes:

- `LOW`
- `BUSINESS_CONFIDENTIAL`
- `HIGHLY_CONFIDENTIAL`

Examples:

- industry/category → `LOW`
- budget decision rules → `BUSINESS_CONFIDENTIAL`
- exact margin/LTV → `HIGHLY_CONFIDENTIAL`
- competitive strategy → `BUSINESS_CONFIDENTIAL`

The product should explain why sensitive questions are useful and allow optional enrichment where exact values are not essential.

### Learning boundary

Customer BusinessProfile content is `LOCAL_ONLY` by default. Customer-specific facts, causal context, KPI hierarchy, confidential market strategy, margin assumptions, and prior evidence must not enter global DOMAIN_VIEW merely because the system learned them during a customer engagement.

---

# 16. Modeling relevance tags

Each material BusinessFact may carry one or more relevance tags:

- `DATA_ACQUISITION`
- `DATA_INTERPRETATION`
- `KPI_SELECTION`
- `GEO_STRATEGY`
- `CHANNEL_AGGREGATION`
- `CONTROL_CANDIDATE`
- `NON_MEDIA_TREATMENT_CANDIDATE`
- `CONFOUNDER_REVIEW`
- `MEDIATOR_REVIEW`
- `SEARCH_GQV_REVIEW`
- `TARGETING_SELECTION_REVIEW`
- `TIME_EFFECT_REVIEW`
- `MODEL_COMPLEXITY_REVIEW`
- `PRIOR_RECOMMENDATION`
- `EDA_INTERPRETATION`
- `MODEL_DIAGNOSTICS`
- `SCENARIO_PLANNING`
- `OPTIMIZATION_CONSTRAINT`
- `DECISION_INTERPRETATION`

This makes the profile operational rather than decorative.

---

# 17. Migration from current `PlannerIntake`

Current frontend Planner intake on `feature/prem3-frontend-mission-2` contains 14 fields:

```text
businessModel
industryLabel
primaryOutcome
markets
historyLengthMonths
channelCategoryIds
providerIds
hasOnlineOutcomeSource
hasOfflineOutcomeSource
warehouseLocation
exportStatus
hasPromoPricingSeasonality
hasFirstPartyCrm
desiredUseCase
```

Recommended migration:

| Current field | Decision | Future destination |
|---|---|---|
| `businessModel` | Keep + expand | `business_identity.business_model` |
| `industryLabel` | Keep + normalize | `business_identity.industry` |
| `primaryOutcome` | Replace | `kpi_framework.primary_kpi` |
| `markets` | Replace | structured `markets[]` |
| `historyLengthMonths` | Move | Data IQ; separate business operating history if useful |
| `channelCategoryIds` | Keep + expand | `marketing_portfolio.channels[]` |
| `providerIds` | Keep, subordinate | `MarketingChannelProfile.providers[]`; provider/source availability also Data IQ |
| `hasOnlineOutcomeSource` | Move | Data IQ/source availability |
| `hasOfflineOutcomeSource` | Move | Data IQ/source availability |
| `warehouseLocation` | Move | Data IQ/infrastructure profile |
| `exportStatus` | Move | Data IQ/source readiness |
| `hasPromoPricingSeasonality` | Retire | split pricing, promotions, seasonality |
| `hasFirstPartyCrm` | Split | customer-journey relevance + Data IQ CRM availability |
| `desiredUseCase` | Replace | structured `measurement_objectives[]` |

### Migration principle

Do **not** extend `PlannerIntake` until it becomes BusinessProfile. The current Planner is a planning workflow. BusinessProfile is a platform foundation consumed by planning and ingestion.

---

# 18. Relationship to planning

Planning becomes a consumer of BusinessProfile.

```text
BusinessProfile
      │
      ├──► Data Acquisition Planner
      │        ├── required sources
      │        ├── collection priorities
      │        ├── potential controls/treatments
      │        └── unresolved business questions
      │
      └──► Existing-Data Intake
               ├── expected sources
               ├── semantic expectations
               └── interpretation context
```

A user should not have to choose “I do not have data” before PreM3 starts learning about the business.

---

# 19. Relationship to dataset ingestion and Data IQ

BusinessProfile should precede ingestion but continue to evolve after data is inspected.

```text
BusinessProfile baseline
        ↓
BUSINESS_CONTEXT_READY
        ↓
Dataset upload/import
        ↓
Data IQ
        ↓
Evidence-triggered Business IQ questions
        ↓
BusinessProfile refinement
        ↓
Modeling Context Assembly
```

Example evidence-triggered question:

> “Paid Search spend rises sharply in the same periods as promotions. Does your team intentionally increase Search budgets during promotion windows?”

The data triggers the question. The user supplies the causal business meaning.

---

# 20. Relationship to Meridian modeling

BusinessProfile should influence **recommendations and review context**, not silently bypass modeling authority.

Potential consumers include:

- KPI interpretation
- geo-strategy recommendations
- channel aggregation review
- control-variable candidate review
- non-media-treatment candidate review
- branded-search/GQV review
- targeting/remarketing selection review
- time-effect and intervention review
- model complexity discussion
- prior recommendations
- EDA interpretation
- scenario and optimization constraints

### Authority rule

```text
Business IQ + Data IQ + Meridian guidance
                ↓
        PreM3 recommendation
                ↓
     deterministic validation / review
                ↓
        modeler-governed decision
```

Final model fit, final knots, final treatment selection, and final prior specification remain modeler-governed unless a later product decision explicitly changes that authority model.

---

# 21. Relationship to MEL and local learning

The BusinessProfile creates a durable customer-specific intelligence substrate.

```text
BusinessProfile
     +
Data IQ
     +
Model Decisions
     +
Human Corrections
     +
Outcomes
     ↓
Customer-local MEL
     ↓
Customer-local operational knowledge
```

Examples of useful local learning:

- accepted channel taxonomy
- validated business relationships
- recurring business-event patterns
- organization-specific causal context
- approved prior evidence
- KPI hierarchy
- business constraints
- past modeling decisions and their outcomes

Customer-local knowledge must remain distinct from global domain knowledge.

---

# 22. Versioning and reproducibility

Every material BusinessProfile update creates a new immutable logical version or equivalent auditable revision.

Required run references should eventually include:

```text
business_profile_id
business_profile_version
business_profile_schema_version
business_profile_fingerprint
question_catalog_version
business_context_ready_at
business_context_snapshot_at
```

A model/run should be reproducible against the Business IQ snapshot that informed it.

Example run receipt:

```text
BusinessProfile: bp_123
Version: 1.4
Schema: business-profile/1.0
Fingerprint: sha256:...

Context consumed:
- 38 user-confirmed facts
- 7 system-observed facts
- 3 inferred candidates
- 4 open knowledge gaps
- 2 prior-evidence records
```

---

# 23. Profile quality / coverage

A profile may expose user-friendly coverage but should not use one opaque score as the readiness authority.

Recommended coverage dimensions:

- `baseline_context`
- `measurement_context`
- `marketing_context`
- `commercial_context`
- `competitive_context`
- `causal_context`
- `prior_knowledge_context`

Example:

```text
Business IQ coverage

Baseline context           COMPLETE
Measurement context        COMPLETE
Marketing context          COMPLETE
Commercial context         PARTIAL
Competitive context        ACKNOWLEDGED_UNKNOWN
Causal context             4 OPEN QUESTIONS
Prior knowledge            NOT PROVIDED
```

`NOT PROVIDED` for optional prior knowledge is not a failure.

---

# 24. User-trust principles

BusinessProfile capture must minimize fatigue and concern.

1. Explain **why** sensitive or unusual questions are asked.
2. Prefer categorical relevance before exact financial values.
3. Allow `UNKNOWN` without penalty.
4. Reuse previously confirmed durable facts.
5. Ask follow-ups only when triggered by information value.
6. Show users what PreM3 currently understands.
7. Make assumptions visibly different from confirmed facts.
8. Permit correction at any time.
9. Explain customer-local privacy posture for proprietary business intelligence.
10. Never describe a user-entered belief as proven causal truth.

---

# 25. Initial Business Baseline — proposed question concepts

This is **not final UX copy**. It defines the minimum knowledge targets.

| # | Knowledge target | Criticality |
|---|---|---|
| 1 | Business model and primary offering | Baseline |
| 2 | Industry/category | Baseline |
| 3 | Primary measurement/decision objective | Baseline |
| 4 | Primary KPI and what it means | Baseline |
| 5 | Market/geographic scope | Baseline |
| 6 | Material marketing channels | Baseline |
| 7 | Broad role of material channels | Baseline/conditional |
| 8 | Broad budget-setting process | Baseline |
| 9 | Promotions materially affect business? | Baseline |
| 10 | Pricing changes materially affect business? | Baseline |
| 11 | Major recurring seasonality/demand periods | Baseline |
| 12 | Customer journey type | Baseline |
| 13 | Competitive activity materially affects business/marketing decisions? | Baseline |
| 14 | Major known historical interventions/events | Baseline |
| 15 | Prior experiments/MMMs/benchmarks available? | Optional high-value |

Branching should reduce actual question count where concepts are not relevant.

---

# 26. Backend handoff requirements

This document intentionally does not prescribe endpoints, storage technology, or implementation prompts. Backend planning should preserve these strategic requirements:

1. first-class `BusinessProfile` resource or equivalent durable aggregate
2. tenant/workspace/project-safe scope resolution
3. versioning and fingerprinting
4. per-field provenance and confirmation
5. temporal validity
6. explicit knowledge gaps
7. separate facts, events, hypotheses/causal claims, and prior evidence
8. `BUSINESS_CONTEXT_READY` concept-aware gate
9. question-catalog version compatibility
10. customer-local privacy classification
11. read model suitable for frontend “What PreM3 understands” surfaces
12. modeling/run snapshot references
13. clear Business IQ / Data IQ separation
14. migration path from existing planner responses where appropriate

---

# 27. Frontend handoff requirements

This document intentionally does not prescribe React components or implementation prompts. Frontend planning should preserve these strategic requirements:

1. Business IQ begins before the planner/data split
2. compact baseline experience, not a giant form
3. backend-driven question schema/branching
4. explicit `UNKNOWN` affordance
5. “Why PreM3 asks” explanation for high-value/sensitive questions
6. profile-understanding review/edit surface
7. visible provenance/assumption distinction where appropriate
8. progressive enrichment after initial onboarding
9. prior knowledge explained in business language
10. no demand that ordinary business users specify probability distributions
11. profile reuse so returning users are not repeatedly interrogated
12. clear transition from `BUSINESS_CONTEXT_READY` to planning or ingestion

---

# 28. Out of scope for BusinessProfile v1 strategy

The following should be decided by the corresponding implementation or applied-modeling workstreams:

- exact persistence schema / Firestore collections
- REST endpoint shapes
- Clerk/tenant resolution mechanics
- specific frontend wizard components
- agent prompts
- final question wording
- exact confidence-calibration algorithm
- automated document extraction implementation
- final Meridian `ModelSpec`
- final knot selection
- final prior distributions
- posterior/model-fit policy

The contract exists to give those teams a stable target.

---

# 29. Acceptance criteria for the strategic contract

BusinessProfile v1 is successful if:

- the system can represent the important business context that affects MMM interpretation;
- current Planner fields have an unambiguous migration destination;
- Business IQ and Data IQ do not collapse into one intake object;
- users can explicitly say “I do not know”;
- material facts have provenance and temporal semantics;
- competitive landscape is first-class;
- prior knowledge can be captured without forcing users to be Bayesian statisticians;
- final priors remain modeler-governed;
- the baseline is compact enough to precede every data path;
- future question ordering and agentic capture can evolve without changing the knowledge ontology;
- model runs can reproduce the Business IQ snapshot they consumed;
- proprietary Business IQ remains customer-local by default.

---

# 30. Strategic decision summary

The product should move from:

```text
Planner form if user has no data
        ↓
14 temporary browser fields
```

To:

```text
EVERY CUSTOMER / MMM PROJECT
            ↓
      BusinessProfile
            ↓
     BUSINESS_CONTEXT_READY
            ↓
   ┌────────┴─────────┐
   ▼                  ▼
Planning          Dataset Intake
   │                  │
   └────────┬─────────┘
            ▼
          Data IQ
            ▼
  Business IQ refinement
            ▼
 Modeling Context Assembly
            ▼
          Meridian
```

The durable product asset is not the questionnaire. It is the **Business IQ state** created by that questionnaire, conversation, evidence, and subsequent learning.

---

# 31. Primary references

## PreM3 repository / project sources

- `frontend/src/lib/planner/types.ts` — current `PlannerIntake` contract, `feature/prem3-frontend-mission-2`
- `docs/context/PREM3_MMM_BOOT_CONTEXT.md` — causal-first principles, semantic readiness, authority boundaries
- `docs/context/domain-view/DOMAIN_VIEW.md` — knowledge precedence and customer-context boundary
- `docs/context/04_MERIDIAN_READINESS_SPEC.md` — KPI semantics, controls, readiness concepts
- `docs/contracts/BACKEND_REQUESTS.md` — self-describing question schema and per-field provenance requirements
- `PREM3_SHORT_TERM_LONG_TERM_PRODUCT_BUSINESS_CONTEXT_V2` — Business IQ + Data IQ learning architecture, `LOCAL_ONLY` default, customer-local knowledge

## Official Meridian sources verified 2026-08-20

- Collect and organize your data:  
  https://developers.google.com/meridian/docs/pre-modeling/collect-data

- Introduction to Applied Modeling / Priors:  
  https://developers.google.com/meridian/docs/advanced-modeling/intro

- Choose and configure treatment prior types:  
  https://developers.google.com/meridian/docs/advanced-modeling/how-to-choose-treatment-prior-types

---

**End of specification.**
