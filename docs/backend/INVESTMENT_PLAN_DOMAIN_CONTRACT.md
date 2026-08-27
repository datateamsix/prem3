# Investment Plan domain contract

Package: `app/investment_planning/`.

Metadata (Firestore-safe): `InvestmentPlan`, `BudgetDriveSourceVersion`, `BudgetColumnMapping`, `InvestmentPlanValidationReceipt`.

Statuses: `DRAFT`, `VALIDATED`, `APPROVED`, `SUPERSEDED`, `SOURCE_STALE`, `SOURCE_UNAVAILABLE`.

`INVESTMENT_PLAN_READY` is a capability-specific receipt. Deterministic code owns it. It does not broaden `BUSINESS_CONTEXT_READY`, `DATA_FOUNDATION_READY`, `MODEL_READY`, or `MODEL_ACCEPTED`.

A market-bearing plan cannot receive full `INVESTMENT_PLAN_READY` until the IG-01 canonical-market contract is integrated (`CANONICAL_MARKET_CONTRACT_INTEGRATED`). Market display strings are non-authoritative. Planning does not own market identity and does not resolve markets by name, fuzzy match, or ISO code.

Canonical field is `project_id`. `workspace_id` is the storage/compat alias and must equal `project_id`.

Campaign/initiative rows, when present, roll up to market × channel × quarter. They do not define the MVP grain.
