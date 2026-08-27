# Investment Plan revision from proposal

Proposal approval does **not** mutate the existing approved plan and does **not** create `APPROVED_PLAN`.

`POST .../proposals/{proposal_id}/create-plan-revision` revalidates the approved proposal, calls P6-01 `revise_plan` (new `plan_id`, `predecessor_plan_id`, `revision+1`), compiles an xlsx from the source `PortfolioView` overlaid with `MODEL_RECOMMENDED` amounts, and `ingest_bytes` onto the **draft** only.

The new draft pins `source_proposal_id`, `source_decision_receipt_id`, and `source_scenario_id`. Caller still runs existing validate → save-version → approve.
