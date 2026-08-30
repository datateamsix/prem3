# Planning value authority and privacy

Google Drive is the source of truth for human-governed budget and allocation values.

Firestore stores metadata, references, fingerprints, states, approvals, and receipts only.

Amount-bearing `PortfolioView`, scenario, and optimization payloads are `CUSTOMER_AMOUNT_TRANSIENT`. They are private (`Cache-Control: private, no-store`) and must not be written to Firestore, PreM3 GCS, logs, APM, analytics, or session replay. Durable amount-bearing artifacts are written only to the customer's authorized Drive file.

`declared_annual_budget` stays in Drive.

Validation receipts may store safe row indexes and headers. They must not store cell contents.

## Pre-P6 compatibility

`PlanningChannelAllocation.amount: float | None` on `app/domain/channels/bindings.py` is a pre-P6 compatibility field. It is not Planning value authority. P6 code must not use it to populate portfolio or optimization values. P6-00 does not modify the shared class.

## Drive folder authority (frozen, not provisioned)

Optional fields on `DriveWorkspaceBinding`:

- `budgets_folder_id`
- `budget_templates_folder_id`
- `budget_plans_folder_id`
- `budget_scenarios_folder_id`
- `budget_proposals_folder_id`

Historical bindings load with `None`. P6-01 provisions:

```text
prem3-modeling/budgets/
  templates/
  plans/
  scenarios/
  proposals/
```
