# Future scenario assumptions (P6-07)

Future cost, flighting, and unit-value inputs are governed assumptions, not optimizer authority and not tenant identity.

## Pinning

`FutureScenarioAssumptions` is amount-bearing. It is persisted to a GCS JSON artifact. Firestore stores only `ScenarioAssumptionSetRef` (ids, bucket/object, generation, fingerprint).

Every cost pin includes unit, currency, period, market (optional), channel, source, and freshness. Flighting pins channel, period, weight, source, and authority. `pin_assumptions` fingerprints the set and records `cost_per_media_unit_refs` / `flighting_refs`.

Invalid pins fail closed:

- non-positive media-unit cost → `FUTURE_COST_ASSUMPTION_INVALID`
- missing unit/currency/period/channel/source/freshness → `FUTURE_COST_ASSUMPTION_INVALID`
- negative flighting weight or missing channel/period/source → `FLIGHTING_ASSUMPTION_INVALID`

## Financial value

`TARGET_ROI_FLEXIBLE_BUDGET`, `TARGET_MROI_FLEXIBLE_BUDGET`, and `MAX_INCREMENTAL_CONTRIBUTION_VALUE` require a governed `UnitValueAssumption` (`revenue_per_kpi` or `contribution_margin`) with source, currency, and freshness.

Missing or ungoverned unit value → `FINANCIAL_VALUE_ASSUMPTION_REQUIRED`. PreM3 does not fabricate ROI or ROMI. When financial value is unavailable, optimize the original KPI and report cost per incremental KPI.

A bare Decimal `revenue_per_kpi` is not a governed source.

## Native encoding

Inspected Meridian 1.8.0 `DataTensors` fields that can carry future data: media / reach / frequency, media_spend / rf_spend, revenue_per_kpi, time. P6-07 records `new_data_kind` on the compiled spec fingerprint. It does not invent tensor payloads when inspection cannot prove the field. Unencodable future cost/flighting remains a validation failure rather than a custom media simulator.

## Staleness

Changing a pinned assumption fingerprint stales `AdvancedOptimizationReadinessReceipt`. Advanced runs include the assumption fingerprint in `optimizer_defaults_fingerprint` / `execution_key`.
