# Portfolio evidence coverage

`PortfolioEvidenceCoverage` describes which evidence exists at an explicit scope. It is not causal certainty and it is not `OPTIMIZATION_READY`.

## Scope

`PROJECT` · `MARKET` · `CHANNEL` · `MARKET_CHANNEL_PERIOD`

P6-03 emits project-scoped items when a real ref exists. It does not pretend evidence is finer than the ref.

## Status

`COVERED` · `PARTIAL` · `MISSING` · `REVIEW_REQUIRED` · `NOT_APPLICABLE` · `UNKNOWN`

## Categories with repository-backed refs

`DATA_FOUNDATION` · `MMM` · `MTA` · `EXPERIMENT` · `BRAND` · `EXPOSURE_INTEGRITY`

Campaign/audience grain is not a coverage category. `CAMPAIGN_IDENTITY` is not emitted.

## Causal boundary

Accepted MMM items are labeled `causal=True`. MTA items are `causal=False` (tactical attribution, not incremental response). Coverage metadata never emits `OPTIMIZATION_READY`.
