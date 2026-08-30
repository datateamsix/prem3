# Exposure risk scenarios (P6-08)

`ExposureRiskScenario` pins bounded assumption deltas plus metric-definition fingerprints. It is not a causal edit of Meridian response curves.

## Bounds

Assumptions store `metric_id`, `delta_kind`, a metadata `delta_ref` (for example `cpm_plus_10`, `viewability_minus_8`), and rationale. Numeric rates/spend do not persist on the scenario document.

Labeled examples:

- CPM +10%
- viewability −8%
- incremental reach −15%
- IVT +3 percentage points
- audience match −10%

## Authority

Scenarios are review/assumption artifacts for Role C. They may attach proposal limitations. They must not rewrite an approved Investment Plan, optimizer result, or fitted ModelSpec.

## P6-09

`ExposureRiskHandoff` carries scenario ids with evidence refs and qualified guardrail ids. Pricing/CVaR remains P6-09.
