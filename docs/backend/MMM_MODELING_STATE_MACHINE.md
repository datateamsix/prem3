# MMM modeling state machine

`MODEL_READY` remains the terminal milestone of **pre-modeling**. Modeling
consumes the immutable `ModelReadyManifest` and does not recompute it.

The EDA ModelSpec stays `PRE_MODELING_EDA_ONLY` /
`approved_for_final_modeling = false`. It is never silently promoted into the
fitted model.

## Domain stages (`MMMModelingStage`)

```text
MODEL_READY
        ↓
DESIGNING_MODEL
        ↓
AWAITING_ASSUMPTION_DECISIONS
        ↓
CONFIGURING_MODEL
        ↓
PRIOR_VALIDATION
        ↓
READY_TO_FIT
        ↓
AWAITING_FIT_APPROVAL
        ↓
FITTING_MODEL
        ↓
EVALUATING_MODEL
        ↓
AWAITING_MODEL_REVIEW
        ↓
ITERATING_MODEL  ↺  DESIGNING_MODEL / CONFIGURING_MODEL
        ↓
MODEL_ACCEPTED
        ↓
INTERPRETING_MODEL
        ↓
HANDOFF_READY
        ↓
COMPLETE
```

Plus `FAILED` from any non-terminal stage.

READY_TO_FIT is emitted only when MODEL_READY input is still valid, required
decisions are resolved, the ModelPlan is fingerprinted, compiled ModelSpec is
valid, final `sample_prior` passed, compatibility passed, and the FitPlan is
compiled. Agent prose does not set it.

## Coarse global projection

Existing run-level consumers may continue to see `MODEL_READY`,
`WAITING_FOR_MODEL_APPROVAL`, `MODELING`, `COMPLETE`. Modeling detail lives on
the MMM domain machine.

## MeasurementTrack projection

Frontend renders backend state. No inference. Projected values:

- `MODEL_READY`
- `DESIGNING_MODEL`
- `AWAITING_ASSUMPTION_DECISIONS`
- `READY_TO_FIT` (also projects `CONFIGURING_MODEL`, `PRIOR_VALIDATION`, `AWAITING_FIT_APPROVAL`)
- `FITTING_MODEL`
- `AWAITING_MODEL_REVIEW` (also projects `EVALUATING_MODEL`)
- `MODEL_ACCEPTED`

Iteration projects `DESIGNING_MODEL` for the successor version.

## Authority

```text
Agent recommends
Deterministic compiler prepares
Human approves consequential assumptions + exact fit
Cloud worker executes the approved plan
```

No autonomous background fitting. Posterior sampling executes only after an
immutable human `FitApproval` bound to the exact FitPlan fingerprint.

## Acceptance

- Convergence `FAIL` blocks `MODEL_ACCEPTED`
- Any official `FAIL` blocks `MODEL_ACCEPTED`
- Official `REVIEW` may proceed only after explicit human acknowledgment
- Health score is not the sole criterion
- Accepted versions cannot mutate; iteration creates a new `MMMModelVersion`
