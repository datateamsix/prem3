# MTA Channel Grouping Governance

UI edits priority / source / medium / campaign / target canonical channel / enabled.
Backend compiles:

```
Channel Registry vN + Customer RuleSet vM + SQL template vK → channel_grouping_vM
```

## Production rules

- Routine: `prem3_modeling.channel_grouping_vN`
- All outputs ∈ pinned Channel Registry
- Historical vN immutable after first recorded use
- New mapping → new version
- Historical MTA runs pin exact routine/version/fingerprint
- Optional `channel_grouping_current` advances only after verified provision
- Historical replay never resolves `current`
- Mapping impact preview required before approval
- Changing grouping never silently mutates prior MTA run receipts
