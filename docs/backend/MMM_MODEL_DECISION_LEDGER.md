# MMM model decision ledger

Consequential modeling choices are durable `ModelDecision` rows, not chat.

## Record

`decision_id`, `model_version_id`, `decision_type`, `proposal`, `authority`,
`evidence_refs[]`, `knowledge_asset_refs[]`, `recommended_value`, `chosen_value`,
`reason?`, `requires_approval`, `status` (`PENDING` / `APPROVED` / `REJECTED` /
`SUPERSEDED`), `approved_by?`, `approved_at?`, `plan_fingerprint`, `created_at`.

Approvals are user-attributed, timestamped, and bound to the ModelPlan
fingerprint. A changed plan, ModelSpec, prior, fit config, model window, or
MODEL_READY fingerprint invalidates stale approvals.

## Initial decision types

`MODEL_WINDOW`, `MODEL_SCOPE`, `KPI_TYPE`, `CONTROL_SELECTION`,
`TREATMENT_CLASSIFICATION`, `MEDIA_PRIOR_TYPE`, `RF_PRIOR_TYPE`, `CUSTOM_PRIOR`,
`ROI_CALIBRATION_PERIOD`, `KNOT_STRATEGY`, `ENABLE_AKS`, `MAX_LAG`,
`ADSTOCK_DECAY_SPEC`, `SATURATION_SPEC`, `HILL_BEFORE_ADSTOCK`, `BASELINE_GEO`,
`POPULATION_SCALING`, `HOLDOUT`, `MCMC_CONFIGURATION`, `FIT_APPROVAL`,
`MODEL_ACCEPTANCE`.

Fit and acceptance also have dedicated immutable records (`FitApproval`,
`ModelAcceptanceApproval`) bound to plan/artifact fingerprints.

## Knowledge classes

- `MERIDIAN_NORMATIVE` — reviewed/compatible official Meridian guidance
- `PREM3_DETERMINISTIC_EVIDENCE` — ModelReady / compiler / receipts
- `BUSINESS_CONTEXT` — pinned Business IQ
- `HISTORICAL_EXPERIENCE` — MEL evidence, never silent authority
- `MMM_JUDGMENT` — agent recommendation; not auto-approved

A PreM3 recommendation is not automatically approved. Numeric priors never
silently migrate across customers. Experiments inform priors only with retained
evidence, timing/scope review, supported calibration period, and human approval.

## Design brief

`MMMModelDesignBrief` answers: given what the business says is true and what the
data can support, what Meridian model should we attempt to fit?

Inputs are versioned (BusinessProfile snapshot, MeasurementCycle, MMM track,
ModelReadyManifest, official EDA findings, coverage, unknowns). Raw chat is not
authority. Every consequential recommendation includes `proposal`, `reason`,
`evidence_refs[]`, `knowledge_asset_refs[]`, `authority`, `requires_approval`.
