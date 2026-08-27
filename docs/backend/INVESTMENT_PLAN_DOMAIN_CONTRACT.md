# Investment Plan domain contract

Package: `app/investment_planning/`.

Metadata (Firestore-safe): `InvestmentPlan`, `BudgetDriveSourceVersion`, `BudgetColumnMapping`, `InvestmentPlanValidationReceipt`.

Statuses: `DRAFT`, `VALIDATED`, `APPROVED`, `SUPERSEDED`, `SOURCE_STALE`, `SOURCE_UNAVAILABLE`.

`INVESTMENT_PLAN_READY` is a capability-specific receipt. Deterministic code owns it. It does not broaden `BUSINESS_CONTEXT_READY`, `DATA_FOUNDATION_READY`, `MODEL_READY`, or `MODEL_ACCEPTED`.

`INVESTMENT_PLAN_READY` requires every market reference to resolve to an Identity Graph `CanonicalMarket.market_id` (`CANONICAL_MARKET_CONTRACT_INTEGRATED`). Display names, ISO codes, and historical Business IQ market strings are non-authoritative. Planning does not own or mint market identity.

Canonical field is `project_id`. `workspace_id` is the storage/compat alias and must equal `project_id`.

Campaign/initiative rows, when present, roll up to market × channel × quarter. They do not define the MVP grain. Campaign Ledger and `campaign_id` are optional execution detail, not a prerequisite for `INVESTMENT_PLAN_READY`.

Canonical Market source commit: `53b606a3b3bc529254816b8376d57c181b44a7ec` (Identity Graph path-checkout; not an IG-01 branch merge).
