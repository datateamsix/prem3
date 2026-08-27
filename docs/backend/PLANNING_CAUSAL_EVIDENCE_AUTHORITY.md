# Planning causal evidence authority

Accepted MMM is the only causal return engine for optimization readiness.

## Accepted model

`MMMModelVersion.accepted is True` and `state is MODEL_ACCEPTED`. `MODEL_READY` is evidence readiness, not model acceptance. Fit-complete, iteration-required, failed, and review-pending states are ineligible.

Planning compiles or caches a `ModelConsumptionContract` **projection** from that version plus ModelPlan, acceptance, and artifact **refs**. MMM remains canonical. A projection that diverges from the accepted version is `MODEL_CONSUMPTION_PROJECTION_STALE`. Incomplete contracts are `MODEL_CONSUMPTION_CONTRACT_INCOMPLETE`. Optimizer / response artifacts are refs only; bytes are not copied into Planning storage.

## MTA

MTA may appear on `OptimizationEvidenceCoverage` as tactical/recent journey context. It cannot satisfy `MODEL_ACCEPTED` or response-artifact checks. Coverage issue `MTA_NOT_CAUSAL_AUTHORITY` is informative when MTA is present without MMM response evidence.

## Portfolio evidence vs optimization coverage

P6-03 `PortfolioEvidenceCoverage` describes measurement scope on the portfolio view. P6-04 `OptimizationEvidenceCoverage` is the optimization-specific causal overlay: covered/uncovered channels and markets relative to the mapping and accepted model.

## Production actuals

`P6_03_PRODUCTION_ACTUALS_QUERY_PENDING` stays fail-closed. P6-03A may land independently and must not change P6-04 contracts. Actuals never become `APPROVED_PLAN` and never satisfy V1 fixed-budget baseline by themselves.
