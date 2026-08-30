# MMM identifiability decision workflow

Official Meridian owns compatibility. PreM3 explains the tradeoff. A human
selects the model change. A model that runs is not automatically a model that
should be trusted.

## When this workflow starts

A FitRun reaches `FAILED_PRE_FIT` with
`failure_class=MODEL_SPEC_IDENTIFIABILITY_ERROR` and
`retry_semantics=NEW_MODEL_DESIGN_REQUIRED`. ModelVersion becomes
`ITERATION_REQUIRED`. Exact retry of the same FitPlan is forbidden.

Music Center v1 failed because `music_center_promo` does not vary across geos
while the approved spec used `n_knots = n_time`.

## Decision family

The failed model routes to `KNOT_STRATEGY`. The package links existing
`TREATMENT_CLASSIFICATION` and EDA `GEO_SCOPE_REVIEW` open decisions. It does
not duplicate M3-02A decisions.

## Package

`MMMIdentifiabilityDecisionPackage` is grounded in:

- official Meridian failure
- pinned Business IQ snapshot
- Data Foundation / source inventory (not only the current ModelReady artifact)
- ModelReady fingerprint and promotion provenance
- `MeridianEDAReceipt`, extended EDA, and `EDAModelDesignHandoff`
- failed ModelPlan, FitPlan, FitApproval, and FitRun

Tenant identity is resolved server-side. No customer tenant ID is
model-supplied.

## Alternatives

| Id | Change | Meaning |
|---|---|---|
| A | Keep `music_center_promo`, set `n_knots < n_time` | Explicit promotion, less time flexibility |
| B | Remove `music_center_promo`, keep `n_knots = n_time` | Full time flexibility; promotion is not explicitly modeled |
| C | Genuine geo-varying promotion evidence | Requires a new Data Foundation / ModelReady version |

C is eligible only when governed geo-varying evidence exists.
`GEO_PROMOTION_EVIDENCE_NOT_FOUND` disables C. Absence in the current
ModelReady CSV is not sufficient to declare C impossible; source inventory is
inspected. Fabricated geo variation is prohibited.

B is not harmless variable cleanup. If B is chosen, record
`PROMOTION_NOT_EXPLICITLY_MODELED`.

## Recommendation

PreM3 may emit `PREM3_RECOMMENDATION`. It may not emit `APPROVED_MODEL_CHANGE`.
Counter-evidence is mandatory. The coding agent stops before selecting A/B/C.

## Human gate

Required payload:

- `decision_type=KNOT_STRATEGY`
- `selected_alternative=A|B|C`
- `selected_configuration` (A requires human-approved `n_knots`)
- `rationale`, `evidence_refs`, `approved_by`, `approved_at`
- `decision_fingerprint`

Service-account approval is prohibited. No successor ModelVersion exists until
this decision is recorded.

## Knots

EDA used `n_knots = n_time - 1` for official EDA only. That does not establish
the final knot strategy. Alternative A produces a `KnotStrategyProposal`. The
human approves the exact knot value. PreM3 does not claim one candidate is
statistically superior until fit evidence exists.

## Frontend read model

`IDENTIFIABILITY REVIEW` renders official constraint, PreM3 interpretation,
business context, data evidence, EDA evidence, alternatives, advisory
recommendation, counter-evidence, and `decision_required`. The frontend must
not manufacture A/B/C.
