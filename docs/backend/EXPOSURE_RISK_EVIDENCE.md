# Exposure risk evidence (P6-08)

P6-08 is an architectural evidence adapter. It interprets delivery/exposure as portfolio risk evidence. It does not price downside risk (P6-09), mutate approved plans, or invent a composite quality score.

## Production path

```text
DF + provider evidence (TEST_ONLY adapter in unit tests)
  → IG market_id / channel_id / optional campaign_id / provider binding
  → ExposureMetricObservation (transient values)
  → DeliveryHealthEvidence
  → PortfolioExposureRiskProfile
  → role A MODEL_INPUT | B CONSTRAINT_OR_FEASIBILITY | C SCENARIO_OR_REVIEW_GUARDRAIL
```

Flags come from versioned `ExposureRiskPolicy` (`exposure_risk_policy/v1`), not hardcoded thresholds in call sites.

## What P6-08 is not

- Not `EXPOSURE_QUALITY_SCORE` / `delivery_confidence = 73`
- Not a second control plane
- Not warehouse discovery (Data Foundation owns source existence)
- Not person identity
- Not raw provider-row HTTP
- Not P6-07 constraint-family mutation
- Not proposal approve/reject

## Coverage

`PortfolioExposureCoverage` reports portfolio spend, channel, market, campaign-provider, and freshness. Missing evidence is not zero risk or quality. Stale evidence is review-required.

## Actuals

P6-03A actual spend joins as context only. Amounts are never rewritten. See [DELIVERY_HEALTH_METRICS.md](DELIVERY_HEALTH_METRICS.md) and [EXPOSURE_GUARDRAIL_QUALIFICATION.md](EXPOSURE_GUARDRAIL_QUALIFICATION.md).

## Handoff

Role A attaches to `FutureScenarioAssumptions.source_refs`. Role B attaches qualified IDs to `OptimizationConstraintSet.exposure_guardrails`. Role C may attach `EXPOSURE_RISK_FLAGS_PRESENT` on the proposal change summary. P6-09 receives `ExposureRiskHandoff` refs (evidence, qualified guardrails, scenarios, coverage fingerprint, flags). P6-08 does not compute CVaR.
