# EDA → Model Design handoff

EDA should not end with “here is a report.” It should end with a better-informed
model design.

## Flow

```text
EDA finding
  → modeling implication
  → Model Design proposal (MMMModelDesignBrief)
  → ModelDecision
  → human approval where required
```

Do not recreate EDA reasoning during Model Design. Consume
`EDAModelDesignHandoff`.

## Contract

`EDAModelDesignHandoff` carries:

- `report_id`
- `modeling_implications[]` (`EDAModelingImplication`)
- `open_modeling_decisions[]` (`EDAOpenModelingDecision`)
- `known_limitations[]`
- `relevant_finding_refs[]`
- `recommended_starting_actions[]`

An implication is not an approved model change. `approved_model_change` is
always false. Open decisions remain `PENDING`. They are inputs to Model
Design, not approved `ModelDecision` records.

`MMMModelDesignBrief` consumes the handoff as:

- extra `evidence_refs` (`eda_report:<id>`, finding ids, implication ids)
- extra `known_limitations`
- extra `decisions_requiring_human_input` (for example `KNOT_STRATEGY`)

`build_design_brief(..., eda_handoff=...)` and
`MMMModelingService.start_design(..., eda_handoff=...)` wire this. Creating
a model design from `POST /v1/projects/{project_id}/cycles/{cycle_id}/mmm/model-design`
attaches the latest cycle handoff when an extended report exists.

## Implication types

`CONTROL_SELECTION`, `TREATMENT_CLASSIFICATION`, `PRIOR_REVIEW`,
`KNOT_STRATEGY`, `TIME_EFFECT_REVIEW`, `MODEL_WINDOW_REVIEW`,
`GEO_SCOPE_REVIEW`, `RF_SPECIFICATION`, `ADSTOCK_REVIEW`,
`SATURATION_REVIEW`, `COLLINEARITY_REVIEW`, `DATA_ADEQUACY`,
`HOLDOUT_REVIEW`, `MCMC_PREPARATION`, `OTHER`.

## EDA-only knot fallback

EDA ModelSpec remains `PRE_MODELING_EDA_ONLY`. If official EDA used
`EDA_ONLY_OFFICIAL_GEO_TIME_CONTROL_INVARIANT` (`n_time - 1` knots), the
handoff always includes:

> This enabled official EDA only. It does not establish the final knot strategy.

That is a `KNOT_STRATEGY` implication plus a pending human decision. The
proposed fitted `ModelPlan.spec.knots` stays `None`. AKS stays off. EDA knots
are never promoted into the final ModelSpec automatically.

## ERROR vs ATTENTION vs INFO

| Official severity | Handoff behavior |
|---|---|
| ERROR | Route to `RESOLVE_EDA_ERROR` / Data Foundation / rerun. Not fitting. `EDA_BLOCKED` unchanged. |
| ATTENTION | Model Design review. Severity stays ATTENTION. ModelSpec is not auto-changed. |
| INFO | Concise unless material to design, a known limitation, or monitoring. |

## MEL

Structured evidence is emitted (`EDA_INTERPRETATION_PATTERN`) with
`can_promote=false`. Generating an interpretation does not promote it. The
long-term question is which interpretations lead to better accepted models
under which business and data conditions.
