# MMM Decision Intelligence Contract (M4-00)

Decision Intelligence is a **separate** contract from verified
`MMMResultsSnapshot`. Compiling a brief never mutates the snapshot.

## Brief

`MMMDecisionIntelligenceBrief` contains:

- `executive_summary`
- `verified_findings[]` — must cite typed evidence refs
- `interpretations[]` — labeled `INTERPRETATION` / `BUSINESS_IQ_CONTEXT`
- `recommendations[]` — authority `RECOMMENDATION`
- `counter_evidence[]`
- `uncertainties[]`
- `decision_requirements[]`

## Recommendation gate

Default production policy:

> Investment recommendations require `MODEL_ACCEPTED` /
> `result_status=ACCEPTED`.

Pre-acceptance briefs may include verified findings, interpretations, and
review observations, but must not issue investment actions that could be
mistaken for approved advice.

## Recommendation shape

Do not recommend solely because one channel has the highest mROI.
Recommendations must include:

- evidence refs
- counter-evidence refs when present
- uncertainty refs when present
- `decision_required=true` for consequential actions

## Explicit non-goals

No `BudgetOptimizer`. No Scenario Planner. No automatic media buying.
