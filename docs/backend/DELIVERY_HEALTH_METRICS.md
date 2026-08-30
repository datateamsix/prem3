# Delivery health metrics (P6-08)

Metrics stay definition-specific. Comparability is deterministic.

## Catalog

Pinned ids include served / rendered / measurable / viewable / human impressions as distinct counts; `VIEWABILITY_RATE`, `IVT_RATE`, `IN_TARGET_RATE`, `UNIQUE_REACH`, `INCREMENTAL_REACH`, `AVERAGE_FREQUENCY`, `OVER_FREQUENCY_SHARE`, `UNDER_FREQUENCY_SHARE`, `VIDEO_COMPLETION_RATE`, `ATTENTION_RATE`, `INVENTORY_QUALITY_RATE`, and `COST_PER_QUALIFIED_EXPOSURE`.

`EXPOSURE_QUALITY_SCORE` and `DELIVERY_CONFIDENCE` are forbidden.

## Comparability

`assert_comparable()` requires matching comparability class, numerator, denominator, population, grain, and provider when a provider is pinned.

Examples that fail closed:

- viewability rate ≠ in-target rate
- average frequency ≠ over-frequency share
- Google Ads viewability ≠ Meta viewability without an explicit mapping
- human-valid impressions × viewable impressions × in-target rate is not a silent product

The only named combination proxy is `human_viewable_in_target_impressions/v1`, and only when components are comparable. Otherwise `EXPOSURE_METRIC_NOT_COMPARABLE`.

## Observations

`ExposureMetricObservation` values are `CUSTOMER_AMOUNT_TRANSIENT`. Canonical `market_id` / `channel_id` are required. `campaign_id` is optional context and must be an Identity Graph campaign when present. Grain remains fiscal year × quarter × market × channel.

## Flags

`DeliveryHealthEvidence` flags (`LOW_VIEWABILITY`, `HIGH_IVT`, `LOW_IN_TARGET_RATE`, `LOW_UNIQUE_REACH`, `OVER_FREQUENCY`, `UNDER_FREQUENCY`, `EXPOSURE_DATA_STALE`, `EXPOSURE_DATA_INCOMPLETE`, `HIGH_SPEND_LOW_QUALITY`, …) are compiled from `ExposureRiskPolicy`. `HIGH_SPEND_LOW_QUALITY` is descriptive and does not rewrite actuals or create LINE_MIN/MAX constraints.
