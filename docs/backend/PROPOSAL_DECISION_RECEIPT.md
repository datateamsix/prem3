# Proposal decision receipt

`ProposalDecisionReceipt` (`odrc_`) is immutable. It records `APPROVE`, `REJECT`, `REQUEST_REVISION`, or `WITHDRAW` with `decided_by_user_id`, fingerprints for proposal/scenario/source plan/optimizer result, and an optional comment.

A thin `PlanningDecisionRecord` (`odec_`) is the P6-10 Decision Ledger seam: decision type `OPTIMIZATION_PROPOSAL`, owner, evidence refs, no amounts.
