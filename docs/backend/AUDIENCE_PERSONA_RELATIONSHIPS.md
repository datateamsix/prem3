# Audience–Persona relationships

Persona is a durable business archetype (`per_`). Audience is an operational segment definition (`aud_`). Campaigns may reference either, both, or neither.

## Typed edges (IG-02A)

| Edge | Meaning |
|---|---|
| `AUDIENCE_REPRESENTS_PERSONA` | Audience definition is scoped to a persona archetype |
| `AUDIENCE_AVAILABLE_IN_MARKET` | Audience definition is available in a canonical market |
| `CAMPAIGN_TARGETS_PERSONA` | Campaign intended scope includes a persona |
| `CAMPAIGN_TARGETS_AUDIENCE` | Campaign intended scope includes an audience |

Reserved, not implemented:

- `AUDIENCE_DERIVED_FROM` — derivation graphs are later work
- `AUDIENCE_BOUND_TO_EXTERNAL` — IG-03 provider bindings

## Cardinality

An audience may represent zero or more personas. Persona is **not** required on audience create. A persona may be represented by many audiences. Child audiences do not inherit membership.

## Campaign refs

`CanonicalCampaign.persona_ids[]` / `audience_ids[]` are resolvable intended-scope refs, not observed delivery. Empty lists remain valid. Unknown or cross-project IDs fail closed (`UNKNOWN_PERSONA` / `UNKNOWN_AUDIENCE`). Archived targets fail closed on new/active campaigns (`ARCHIVED_TARGET`) unless the campaign itself is already `ARCHIVED`.

## Reads

- `persona_audiences` / `persona_campaigns`
- `audience_personas` / `audience_campaigns` / `audience_children` / `audience_lineage`

Lineage is cycle-safe. Child does not imply membership subset.

## Downstream grain

MTA and Planning must not add audience or persona as DP6 states or expand P6 grain beyond `market_id × channel_id × period`. Exposure evidence later consumes `audience_id × campaign_id × market_id × channel_id` as intended scope vs observed delivery.
