"""Frozen Drive budget-folder binding field names. P6-01 provisions folders."""

from __future__ import annotations

BUDGET_DRIVE_FOLDER_FIELDS: tuple[str, ...] = (
    "budgets_folder_id",
    "budget_templates_folder_id",
    "budget_plans_folder_id",
    "budget_scenarios_folder_id",
    "budget_proposals_folder_id",
)

DRIVE_BUDGET_LAYOUT = (
    "prem3-modeling/budgets/",
    "prem3-modeling/budgets/templates/",
    "prem3-modeling/budgets/plans/",
    "prem3-modeling/budgets/scenarios/",
    "prem3-modeling/budgets/proposals/",
)
