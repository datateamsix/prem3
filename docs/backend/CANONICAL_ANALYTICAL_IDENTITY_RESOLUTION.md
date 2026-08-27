# Canonical analytical identity resolution

**Mission:** IG-04

IG-04 compiles proven identity. Display names never mint IDs.

## Market

Reuse IG-01 `resolve_market`. `geo.country` is not implicit `market_id`. Property-bound sources with exactly one declared market resolve `PROPERTY_BOUND`. Multi-market sources without an explicit allowed method stay `UNRESOLVED`.

## Channel

Channel Registry is authority. Precedence:

1. Exact approved source/medium binding
2. Deterministic `channel_grouping_rules_v1.yaml` predicates (not name-fuzzy)
3. Direct preserved for `(direct)` / `(none)`
4. `UNRESOLVED`

Provider is not channel. `DirectTreatmentPolicy` is compile config, not a global delete of Direct.

## Campaign

Call IG-03 `CampaignIdentityResolver` only. Precedence is unchanged. Conflicts stay `campaign_id=NULL` + `REVIEW_REQUIRED`. `utm_campaign` never resolves. `parent_campaign_id` is compiled as metadata; children are not collapsed.

Unresolved campaign does **not** globally block `READY` unless the compile request sets `campaign_slice_required`.

## Audience

Set `audience_id` only when an `AudienceExternalBinding` matches a proven provider audience identifier. Multi-provider does not imply equivalent membership.

## Journey markets

`MULTI_MARKET_JOURNEY` is explicit. Do not silently assign first, last, or conversion market.
