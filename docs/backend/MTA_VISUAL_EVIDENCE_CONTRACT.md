# MTA Visual Evidence Contract

Backend owns chart-ready typed data. Frontend rendering is out of scope.
No Vega-Lite specs are emitted.

Every `MTAVisualization` binds `source_result_snapshot_id` and `source_run_id`.

P0 kinds:

- `ATTRIBUTION_BY_CHANNEL_MODEL`
- `MODEL_COMPARISON_HEATMAP` (share only; never mixed with credit)
- `CHANNEL_ROLE_POSITION`
- `MARKOV_TRANSITION_MATRIX`
- `MARKOV_REMOVAL_EFFECT`
- `SHAPLEY_CONTRIBUTION` (`available=false` + reason when not run)
- `TOP_CONVERSION_PATHS` (ranked table, not Sankey)
- `PATH_LENGTH_DISTRIBUTION`
- `TIME_TO_CONVERSION_DISTRIBUTION`
- `MODEL_SENSITIVITY_RANGE` (not a confidence interval)

Frontend may sort, filter, select channels/models, and format numbers.
It may not calculate attribution share, dispersion, roles, or Markov/Shapley values.
