# Channel Governance + UI

## Canonical rule

The UI never creates an isolated MTA taxonomy.

Business IQ and all Measurement Tracks consume the same Channel Registry.

## Channel management UI

Recommended project-level surface:

```text
Foundation / Business IQ
→ Channels
→ Canonical Channels
→ Source Mapping
```

Each row can show:
- canonical channel
- family
- enabled for business
- providers / sources observed
- MMM availability
- MTA mapping coverage
- mapping status

### Edit MTA mapping

User edits structured rules:
- priority
- source match
- medium match
- campaign match
- target canonical channel

PreM3 shows:
- discovered values affected
- share of sessions affected
- newly mapped / unmapped values
- conflict warnings
- downstream impact

On approval:
- backend creates a new ruleset version;
- compiles new immutable UDF version;
- validates it;
- provisions it to the bound BigQuery dataset;
- records fingerprint/receipt.

Do not expose raw SQL as the default editor. An advanced read-only SQL preview is useful for transparency.

## Adding a new channel

If the user needs a channel not in the canonical registry:
1. create a proposed registry addition;
2. define stable ID, display name, family and method applicability;
3. approve/publish a new registry version;
4. make it available to BIQ/MMM/MTA simultaneously.

## AI Search

`ai_search` is part of V1. It should be selectable in Business IQ and usable in MMM/MTA when evidence exists.
