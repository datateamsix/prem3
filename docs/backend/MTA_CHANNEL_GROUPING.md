# MTA Channel Grouping (M5-00)

Channel grouping is a governed analytical asset.

## Versioning

`MTAChannelGrouping` pins:

- version (`v1`, `v2`, …)
- BusinessProfile snapshot
- rules + fingerprint
- routine name `channel_grouping_<version>`
- SQL fingerprint

## Immutability

Never `CREATE OR REPLACE channel_grouping_v1` after it has powered a recorded run.

Create `channel_grouping_v2` instead. Optional alias `channel_grouping_current`
may advance; historical runs pin the versioned routine.

## Compilation

PreM3 compiles deterministic BigQuery SQL CASE logic from approved rules.
Stacktonic examples are reference-only templates, not universal truth.
