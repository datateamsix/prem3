# Tracking verification and coverage

## TrackingVerificationReceipt

Statuses: `VERIFIED` · `OBSERVED_UNVERIFIED` · `NOT_OBSERVED` · `REVIEW_REQUIRED`.

`VERIFIED` requires a governed observation and a unique resolution to the expected canonical campaign. No observation → not `OBSERVED` and not `VERIFIED`. No unique match → not `VERIFIED`. Expected identifier mismatch → `REVIEW_REQUIRED`. A later conflicting observation can move a previously verified campaign to `REVIEW_REQUIRED`.

Instruction status `OBSERVED` / `VERIFIED` is allowed on read only when that evidence exists (`TRACKING_STATUS_UNEVIDENCED` otherwise).

## IdentityCoverageReadModel

Count-based with explicit denominators:

- `resolved_identifier_count` / `observed_identifier_count`
- `campaigns_verified` / `campaigns_total`

No invented tracking score, size, match rate, or reach. Status uses existing capability vocabulary (`NOT_CONFIGURED` · `PARTIAL` · `READY` · `REVIEW_REQUIRED`).

## AudienceBindingCoverage

Provider binding counts and `providers[]` only.
