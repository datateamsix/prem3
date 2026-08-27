# Cross-Method Channel Bindings

Methods join on stable `channel_id`, never fuzzy display labels.

## ChannelBinding

Typed binder in `app/domain/channels/bindings.py`:

- `channel_id`, `channel_registry_version`, `fingerprint`
- optional refs: BIQ profile channel, DF sources, MMM variables, MTA grouping rules, planning allocations

## MMM

Meridian variable names are not renamed. Dataset A example:

| MMM variable | canonical_channel_id |
|---|---|
| `paid_search` / `paid_search_impressions` | `search_paid` |
| `paid_social` | `social_paid` |
| `shopping` | `shopping_paid` |
| `ai_search` | `ai_search` |

## Business IQ

`MarketingChannel.channel_id` remains profile-local. Additive:

- `registry_channel_id`
- `channel_registry_version` on the channel and/or new `BusinessProfileSnapshot`

Historical snapshots stay immutable without forced migration.

## Planning

`PlanningChannelAllocation` stores `channel_id` + registry version. No optimizer in M5-01A.

`PlanningChannelAllocation.amount: float | None` is a **pre-P6 compatibility field**. It is not Planning value authority. P6 Investment Plan / Portfolio amounts are Drive-owned `Decimal` values on transient `PortfolioView`. P6-00 does not modify this class.

Canonical Planning join remains Channel Registry `channel_id`. See `docs/backend/P6_SOURCE_AUTHORITY.md`.

## Join rule

```python
biq ∩ mmm ∩ mta ∩ planning  # on channel_id sets only
```
