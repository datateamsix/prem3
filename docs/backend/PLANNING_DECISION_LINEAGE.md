# Planning decision lineage

Auditor path:

approved plan vN → P6-04 readiness receipt → P6-05 optimization run → optimizer result → scenario → proposal → human `ProposalDecisionReceipt` → plan revision vN+1 → P6-01 plan approval → new `APPROVED_PLAN`.

All durable records carry fingerprints. Optimizer evidence is never rewritten by approval.
