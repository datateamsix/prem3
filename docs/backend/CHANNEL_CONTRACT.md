# PreM3 Canonical Channel Contract V1

## Purpose

Canonical channel identity is shared across:
`Business IQ → Data Foundation → MMM → MTA → Planning → Decision Intelligence`.

## Levels

```text
channel_family_id
  ↓
channel_id
  ↓
provider / platform / campaign
```

A provider is not a channel.

## Stable identity

`channel_id` is an immutable semantic identifier once used in production. Display names can evolve; IDs do not silently change.

## Cross-method rule

- Business IQ records canonical `channel_id`.
- Data Foundation maps provider/source evidence to canonical `channel_id`.
- MMM model inputs bind media variables to canonical `channel_id`.
- MTA UDF returns canonical `channel_id`.
- Portfolio/Decision Intelligence joins methods on canonical `channel_id`, plus period/market/KPI context.

## Customer customization

Customers can customize **mapping rules** from raw traffic values to existing canonical channels.

If a genuinely new channel is needed, create a governed Channel Registry version so it becomes available simultaneously to Business IQ, MMM, MTA, and Planning.

Do not create MTA-only custom channel IDs.

## Version pinning

Every MTA run records:
- `channel_registry_version`
- `channel_grouping_ruleset_version`
- `channel_grouping_udf_version`
- `channel_grouping_udf_fingerprint`

Historical runs never use a mutable `current` alias during replay.
