# MTA Track Architecture (M5-00)

PreM3 MTA is the second first-class `MeasurementTrack`, parallel to MMM, on the
same Project Foundation (Business IQ + Data Foundation).

## Epistemic boundary

MTA measures **observable journey attribution evidence**.

It does **not** measure causal / incremental outcomes.

Preferred language: attributed credit, journey contribution, observable
conversion role, removal sensitivity, marginal coalition contribution.

## Package

`app/modeling/mta/`

Domain stages (`MTATrackStage`) are projected into Project Home; envelope
`MeasurementTrackStatus` remains shared.

## Invariant

`DATA_FOUNDATION_READY` ≠ `MTA_INPUT_READY`

Only the deterministic `MTAReadinessReceipt` may mark input ready.

## M5-00 vs later

| Mission | Owns |
|---|---|
| M5-00 | Contracts, discovery, policies, grouping, provisioning plan, Overview, skills |
| M5-01 | Journey compiler, DP6 worker, live attribution |
| M5-02 | Results, visuals, channel-role intelligence |
| M5-03 | MMM ↔ MTA reconciliation |
