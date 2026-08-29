# MTA Results Architecture

M5-02 compiles a verified `MTARun` into an immutable `MTAResultsSnapshot`.
It does not recompile GA4 journeys, rewrite DP6 execution, or mutate run status
when result serving fails.

```
Verified MTARun + normalized BQ/in-memory outputs
        → MTAResultsCompiler
        → MTAResultsSnapshot (immutable)
        → channel results, model comparison, Markov/Shapley,
          journeys, sensitivity, roles, visualizations
        → MTADecisionIntelligenceCompiler
        → MTADecisionIntelligenceBrief
```

## Pointers

- `latest_result_snapshot_id` always tracks the newest compiled snapshot.
- `current_result_snapshot_id` defaults to the first `VERIFIED` snapshot.
- A later `PARTIAL` or `REVIEW_REQUIRED` snapshot never auto-replaces `current`.
- Operators may select current explicitly.

## Missing is not zero

`MetricAvailability` distinguishes `AVAILABLE`, `NOT_RUN`, `NOT_APPLICABLE`,
`BLOCKED_BY_PREFLIGHT`, `UNAVAILABLE_SOURCE`, and `INVALID`. Shapley not run is
never stored as credit `0`.

## Compile failure

If snapshot compilation fails, `MTARun` remains `SUCCEEDED`. Result status is
`NOT_AVAILABLE` until a snapshot is verified.
