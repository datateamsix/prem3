# Advanced optimization constraints (P6-07)

Hard constraints are explicit, attributed, and fail-closed. LLM-proposed text is not authority.

## Families

`TOTAL_FIXED_BUDGET`, `TOTAL_FLEXIBLE_BUDGET`, `LINE_MIN`, `LINE_MAX`, `LOCKED_ALLOCATION`, `MAX_ABSOLUTE_MOVE`, `MAX_PERCENT_MOVE`, `MARKET_FLOOR` / `MARKET_CEILING`, `QUARTER_FLOOR` / `QUARTER_CEILING`, `FUNNEL_FLOOR` / `FUNNEL_CEILING`, `EXPERIMENT_RESERVE`, `CONTINGENCY_RESERVE`, `AVAILABILITY_WINDOW`.

Line identity is `period × market_id × channel_id` or a stable line id (mapped model variable id). Display labels are never keys.

## Authority

Every hard constraint carries `ConstraintAuthorityRecord`: source, authority (`HUMAN_CONFIRMED` | `BUSINESS_IQ_GOVERNED` | `CONTRACTUAL` | `SYSTEM_DERIVED`), scope, period, reason, fingerprint.

## Amounts vs metadata

`OptimizationConstraintSet` is amount-bearing and lives on GCS. Firestore stores `ConstraintSetRef` only. HTTP GET returns refs. POST bodies are private (`Cache-Control: private, no-store`).

`exposure_guardrails` is typed as an unused placeholder and rejected if non-empty (P6-08).

## Unsupported channels

Missing optimizer evidence is never treated as zero value. Policies:

- `HOLD_BASELINE` (maps prior `FIXED_BASELINE`)
- `RESERVE_EXPERIMENT_AMOUNT`
- `EXCLUDE_FROM_OPTIMIZER_BUT_KEEP_PORTFOLIO` (maps prior `EXCLUDED`)
- `APPROVED_PROXY_WITH_REVIEW` (requires explicit approval)

Unmodeled channels remain on the portfolio result as fixed/held rows.

Missing funnel member weights → `FUNNEL_MAPPING_REQUIRED`, not weight zero.

Percent movement at zero baseline sets `percent_unavailable` / `percent_change_unavailable`. Code never divides by zero or invents infinity.

## Native compilation

Channel min/max, locked lines, and movement compile to per-channel `spend_constraint_lower` / `spend_constraint_upper` versus the native spend-box center. Experiment reserve is subtracted from the native-optimizable total conceptually by holding reserve lines fixed on the portfolio.

`B_min` / `B_max` are not native kwargs. Native 1.8.0 `_validate_budget` rejects `budget` on the flexible path. Total bounds are feasibility + post-result checks. Line bounds compile to `spend_constraint_*` versus the approved mix; if `L_i` would fall outside `[0, 1]`, dispatch fails `FLEXIBLE_BUDGET_API_UNSUPPORTED`.

Market / quarter / funnel group sums that cannot be expressed as `selected_geos` or a date window are feasibility-checked and post-validated. PreM3 does not write a group-sum solver.
