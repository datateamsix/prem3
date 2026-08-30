# Exposure guardrail qualification (P6-08)

Qualification is a receipt. It does not mutate P6-07 feasibility, flexible-budget compile, or `ConstraintFamily` values.

## Role mapping

Existing `ExposureGuardrailRole` values are retained:

| Guardrail role | Optimization role |
|---|---|
| `MODEL_INPUT` | A `MODEL_INPUT` |
| `CONSTRAINT` | B `CONSTRAINT_OR_FEASIBILITY` |
| `SCENARIO_GUARDRAIL` | C `SCENARIO_OR_REVIEW_GUARDRAIL` |
| `APPROVAL_GUARDRAIL` | C `SCENARIO_OR_REVIEW_GUARDRAIL` |

## Role A — model input

Allowed only when the accepted MMM/optimizer consumption contract explicitly lists the metric (reach/frequency variables on `ModelConsumptionContract`). Otherwise `EXPOSURE_MODEL_INPUT_UNSUPPORTED`.

## Role B — constraint or feasibility

Allowed only when `ExposureRiskPolicy` records a defensible spend→delivery relationship or bounded provider/capacity rule. Otherwise P6-08 does **not** emit Role B: the receipt assigns Role C and records `SPEND_QUALITY_RELATIONSHIP_REQUIRED` plus `EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED`.

`pin_constraint_set` (client `POST .../constraint-sets`) still rejects caller-supplied `exposure_guardrails`. After qualification, P6-08 `attach_qualified_exposure_guardrails()` may write Role B IDs onto the existing placeholder field. Observations are not compiled into LINE_MIN/MAX spend constraints or native `spend_constraint_*`. Role A attaches qualification refs to `FutureScenarioAssumptions.source_refs`. Role C may append `EXPOSURE_RISK_FLAGS_PRESENT` on `build_change_summary`.

## Role C — scenario or review

Default. May reduce recommendation confidence and attach proposal limitations. Must not mutate Meridian response curves.

## Errors

`EXPOSURE_SOURCE_NOT_READY`, `EXPOSURE_METRIC_NOT_COMPARABLE`, `EXPOSURE_DATA_STALE`, `EXPOSURE_COVERAGE_INSUFFICIENT`, `EXPOSURE_ENTITY_MAPPING_REQUIRED`, `EXPOSURE_MODEL_INPUT_UNSUPPORTED`, `EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED`, `SPEND_QUALITY_RELATIONSHIP_REQUIRED`, `EXPOSURE_GUARDRAIL_REVIEW_REQUIRED`.
