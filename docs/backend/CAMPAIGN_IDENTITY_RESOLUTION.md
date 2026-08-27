# Campaign identity resolution

`CampaignIdentityResolver` is the only deterministic matcher. HTTP routers must not fork this logic.

## Precedence

1. Exact active `PREM3_UTM_ID` tracking binding (`utm_id=<campaign_id>`)
2. Exact confirmed/active `CampaignExternalBinding` (provider + account + external id)
3. Exact approved `CustomCampaignIdentifierRule` plus tracking mapping
4. Explicit user-confirmed `MANUAL_MAPPING`
5. Unresolved

Preferred customer implementation remains `utm_id=<campaign_id>`. `utm_campaign`, provider names, and fuzzy names never resolve.

## Dates

Resolution respects observation time vs binding `effective_start` / `effective_end`. Inactive-for-that-period bindings do not hit.

## Conflicts

Multiple distinct canonical IDs → `REVIEW_REQUIRED` with `CONFLICTING_EXACT_BINDINGS` / `BINDING_CONFLICT`. Same campaign via several exact methods → `RESOLVED` and all `matched_binding_ids` are kept.

## Persistence

`CampaignIdentityResolution` includes `resolution_id`, tenant/project, `observation_id`, `resolution_method`, matched/conflicting binding ids, issues, fingerprint. Stored under `identity_resolutions`.

## IG-04 handoff

`CampaignIdentityHandoff` is additive: `campaign_id`, optional `parent_campaign_id`, source, binding/tracking ids, resolution status/fingerprint, optional provider/utm/custom provenance, `audience_id` only when a binding proves it.

IG-04 calls this resolver during unified compile. It does not fork matching. Unresolved campaign does not globally block analytical `READY` unless `campaign_slice_required`. See [CANONICAL_ANALYTICAL_IDENTITY_RESOLUTION.md](CANONICAL_ANALYTICAL_IDENTITY_RESOLUTION.md).
