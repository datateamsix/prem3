# Investment Plan governance

Canonical domain contract: [INVESTMENT_PLAN_DOMAIN_CONTRACT.md](INVESTMENT_PLAN_DOMAIN_CONTRACT.md).

Lifecycle remains P6-01: draft → validate → save-version → approve. `revise_plan` creates a **new** `plan_id` with `predecessor_plan_id`; prior approved Drive files are not overwritten.

P6-06 adds optional lineage pins on the successor draft (`source_proposal_id`, `source_decision_receipt_id`, `source_scenario_id`). See [INVESTMENT_PLAN_REVISION_FROM_PROPOSAL.md](INVESTMENT_PLAN_REVISION_FROM_PROPOSAL.md). Proposal approval and plan approval stay separate.
