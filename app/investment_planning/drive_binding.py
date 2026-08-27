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

BUDGETS_FOLDER_NAME = "budgets"
BUDGET_CHILD_FOLDER_NAMES: tuple[tuple[str, str], ...] = (
    ("budget_templates_folder_id", "templates"),
    ("budget_plans_folder_id", "plans"),
    ("budget_scenarios_folder_id", "scenarios"),
    ("budget_proposals_folder_id", "proposals"),
)

CSV_MIME = "text/csv"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SUPPORTED_BUDGET_MIMES = frozenset({CSV_MIME, XLSX_MIME})
TEMPLATE_SCHEMA_VERSION = "prem3_budget_template_v1"
MAX_BUDGET_BYTES = 5_000_000
MAX_BUDGET_ROWS = 5_000
