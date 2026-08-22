# Business IQ — Engineering Scope & Migration Addendum

**Status:** Addendum to `BUSINESS_PROFILE_V1_SPEC.md` and `BUSINESS_IQ_UX_DESIGN_BRIEF.md`
**Purpose:** the concrete, sequenced, buildable layer those two strategy documents deliberately left out of scope
**Grounded against:** `origin/main` @ `dce8a20`, `origin/feature/prem3-frontend-mission-2` (real, shipped `PlannerIntake`)

---

## 1. What exists today (verified, not assumed)

`frontend/src/components/prem3/planner/planner-experience.tsx` (529 lines) is a real, tested, shipped wizard:

- 4 sections: `About your business`, `Channels & platforms`, `Data readiness`, `Your goal`
- State is `useState<PlannerIntake>` — **no backend persistence at all**
- 14 flat fields (confirmed exact match to `BUSINESS_PROFILE_V1_SPEC.md` §17's migration table)
- Own analytics (`planner/analytics.ts`) with an explicit security-boundary test (`security/planner-boundary.test.ts`) guarding against free-text business content reaching analytics
- Own client-side decision engine (`planner/decision-engine.ts`) and browser storage (`planner/storage.ts`)
- A real, dated, generated provider snapshot (`provider-snapshot.generated.json`) — 52 providers, `sourceRetrievedAt: 2026-08-15`

This is not a stub. It's a working feature with its own test suite. The migration described in the strategy doc's §17 is a **replacement of shipped functionality**, and should be planned as one.

---

## 2. Sequencing — this is not one PR

| Phase | Work | Blocks |
|---|---|---|
| 0 | **Register decision** (§3 below) — confirm before any screen design starts | Claude Design work |
| 1 | `BusinessProfile` persistence contract + `BUSINESS_CONTEXT_READY` gate computation, backend-owned | everything below |
| 2 | `BusinessQuestionCatalog` engine — self-describing schema, trigger conditions, criticality classes | frontend rendering |
| 3 | Frontend: Screens 01–04 (Welcome, Your Business, Measurement, Markets) against the new contract, **anonymous-compatible** | conversion-risk decision (§4) |
| 4 | Frontend: Screens 05–09 (Portfolio, Decisions, Drivers, Competitive, Events) | Phase 3 |
| 5 | Screen 11 (What PreM3 Understands) + edit/confirm workflow | Phases 1–4 |
| 6 | Screen 10 (Prior Knowledge) — explicitly optional, can ship after Phase 5 | none — decoupled by design |
| 7 | Embedded agent pattern + free-text extraction-to-candidate-fact flow | Phase 2 |
| 8 | Evidence-triggered questions (Data IQ → Business IQ feedback) | dataset ingestion work, separately scoped |
| 9 | **Retire `PlannerIntake`** — only after Phase 5 ships and reaches parity, not before | Phases 1–5 |

Phase 9 belongs at the end deliberately. The existing planner keeps working for anonymous users until its replacement is proven, not the moment the new contract exists.

---

## 3. Register decision — confirm this before screen design starts

**Business IQ is a product surface, not a marketing surface.** It uses the calm, restrained register established for the console and Taskmaster (light background, navy/indigo, cyan reserved for confirmed/complete states, minimal motion) — **not** the dark/grid/tilt register built for the landing page.

Reasoning: a user filling in real business detail across 8–14 interactions is doing sustained work, not being converted in thirty seconds. Drama earns a landing page a click; it costs a working tool legibility and trust. This is the same split already codified for the frontend team (product vs. marketing tracks) — Business IQ sits firmly on the product side of that line regardless of whether it's reached before or after sign-up.

Concretely: `StatusBadge`, `AuthorityBadge`-style chips, and the existing light card system extend directly to Screen 11's understanding panel. Do not reach for the marketing hero's dark card, grain, or tilt for any Business IQ screen.

---

## 4. Open decision: does this gate the anonymous funnel?

The strategy doc is explicit that Business IQ should precede *both* planning and dataset ingestion (§18–19), and that "a user should not have to choose 'I do not have data' before PreM3 starts learning about the business." Taken literally, that means `BUSINESS_CONTEXT_READY` sits in front of the anonymous `/start` funnel — before the three-card stage chooser, not after it.

That's a materially different funnel than the one already built and tested (Prompt 05 in the frontend prompt pack): 4 fast sections today, versus 12 conceptual screens (even at "8–14 concise interactions," more screens than the current wizard). This needs an explicit answer, not an inherited assumption:

- **Option A:** Business IQ baseline precedes `/start` entirely, replacing the current anonymous planner. Highest strategic coherence, highest conversion risk — untested against real funnel data.
- **Option B:** A lightweight baseline (Screens 01–03 only, roughly matching the current 4-section scope) gates `/start`; the remaining depth (04–10) is captured post-sign-up, inside the authenticated product. Lower conversion risk, defers "business-first" purity.
- **Option C:** Keep the current anonymous planner as-is for the free funnel; Business IQ v1 ships only inside the authenticated product as a richer post-signup capture, with the anonymous planner's 14 fields becoming the seed data for a user's first `BusinessProfile` via the migration table.

Recommendation: **Option C for the first ship**, revisited once there's funnel data to weigh against the strategic ideal. It's the only option that doesn't require re-validating the anonymous conversion funnel before the backend contract in Phase 1 even exists. Record whichever is chosen in `08_DECISION_LOG.md` — this is exactly the kind of call that gets silently relitigated mid-build otherwise.

---

## 5. Backend contract requirements

Numbered to slot into the existing `docs/contracts/BACKEND_REQUESTS.md` queue alongside REQ-001–011.

**REQ-012 — `BusinessProfile` persistence contract.** Durable, tenant/workspace-scoped, versioned. Minimum: the primitives in `BUSINESS_PROFILE_V1_SPEC.md` §6 (`BusinessFact`, `BusinessEvent`, `BusinessRelationship`, `BusinessHypothesis`, `KnowledgeGap`) plus the 12-domain ontology (§7) as the field surface. Snapshot/fingerprint on every modeling run per BP-09.

**REQ-013 — `BUSINESS_CONTEXT_READY` gate, computed server-side.** Concept-aware per §10.4 — never a percentage the frontend computes. Frontend renders the gate's output; it does not derive readiness from field counts, mirroring the existing rule that the Taskmaster never derives `MODEL_READY` client-side.

**REQ-014 — `BusinessQuestionCatalog` engine.** Self-describing schema per §12's `BusinessQuestion` shape: `answer_type`, `field_targets`, `trigger_conditions`, `information_value_class` (`BASELINE_REQUIRED` / `HIGH_VALUE_CONDITIONAL` / `EVIDENCE_TRIGGERED` / `OPTIONAL_ENRICHMENT`), `why_prem3_asks`. This is the same rule already established for planning intake (Prompt 06 / REQ-004): the frontend renders a schema, it does not own question text, options, or branching.

**REQ-015 — Per-field provenance and confirmation.** `knowledge_state` × `confirmation_state` as two independent axes (§6.1) — not collapsed into one status. This is what makes Screen 11 honest rather than a summary the user has to fact-check from memory, same principle as the planning intake's provenance requirement (REQ-005).

**REQ-016 — Free-text extraction to candidate facts.** The embedded agent pattern (design brief §9) requires an endpoint that takes free text and a `question_id`, returns structured candidate facts with `confirmation_state: UNCONFIRMED`, never writes directly to confirmed state. Mirrors the existing planning-intake extraction endpoint's confirm-before-commit pattern.

**REQ-017 — Understanding read model.** A single endpoint backing Screen 11 — per-domain status (`Confirmed` / `Partial` / count-based / unknown-acknowledged), not assembled client-side from raw facts. Same rule as the Taskmaster read model (REQ-007): whichever side computes status becomes the second definition of it.

**REQ-018 — Migration endpoint for existing `PlannerIntake` records.** Anyone who completed the current anonymous planner before the cutover needs their 14 fields mapped into a seed `BusinessProfile` per the exact table in `BUSINESS_PROFILE_V1_SPEC.md` §17 — not discarded, not silently re-asked.

---

## 6. Response-contract and style-guide impact

Consistent with how `COLLECTION_CODE` required its own `RESPONSE_STYLE_GUIDE.md` section (see the collection-code-generation spec): **the "What PreM3 understands" panel is a new presentation pattern and needs the same treatment.**

- A `BUSINESS_PROFILE_SUMMARY` (or similar) addition to `ResponseType`, carrying per-domain status, provenance, and the optional natural-language synthesis line (design brief §8, Screen 11) — which must be generated *from* structured state, never authored independently of it, or it becomes exactly the kind of ungrounded prose the rest of this product's authority model exists to prevent.
- A style-guide rule, mirroring the `COLLECTION_CODE` confidence-banner precedent: an "unknown/partial" domain must never render with the same visual weight as an error or blocker. The design brief already states this (§8, Screen 11, "do not visually imply that every partial/unknown area is a problem") — it needs to be a testable rendering rule, not just design guidance that erodes over time.

---

## 7. What this addendum does not decide

Consistent with both source documents' own scoping discipline, this addendum does not prescribe: exact Firestore/BigQuery schema, exact REST shapes, final question wording, or the extraction model's prompt. Those belong to whoever implements REQ-012–018. This document exists so that work has a sequenced, buildable target — the same purpose the two strategy docs state for themselves, one layer down.
