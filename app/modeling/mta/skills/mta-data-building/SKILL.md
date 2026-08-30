# mta-data-building

Workflow for preparing MTA inputs.

1. Discover GA4 `analytics_<property_id>` dataset
2. Select conversion / key event
3. Select settled conversion period (`DAILY_SETTLED`)
4. Review identity strategy
5. Review session traffic-source policy
6. Review lookback window
7. Review journey boundary
8. Review Direct treatment
9. Review / approve channel grouping version
10. Compile BQ asset plan
11. Validate `MTA_INPUT_READY` via deterministic receipt

## Critical checkpoints

- Gemini cannot mark MTA ready.
- Intraday shards are PREVIEW only.
- Channel grouping versions are immutable after use.
