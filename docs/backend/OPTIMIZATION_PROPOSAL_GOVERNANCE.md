# Optimization proposal governance

`OptimizationProposal` is the investment-committee record. It is distinct from `OptimizationRun` and from the unused P6-00 `OptimizationProposalRef`.

States: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `REVISION_REQUESTED`, `WITHDRAWN`, `STALE`.

Only `SUBMITTED` / `UNDER_REVIEW` may be approved by an authenticated human (`require_human_approver`). After submission, core scenario/plan/run pins are immutable.

`ProposalReadinessReceipt` is separate from P6-04 optimizer readiness. Default policy: `requires_distinct_plan_approval=true`, rejection comment required, no expiry.
