"""Idempotent Drive budget-folder provisioning. Folder IDs are authority."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.google.adapters import DriveClient, DriveFile
from app.investment_planning.drive_binding import (
    BUDGET_CHILD_FOLDER_NAMES,
    BUDGETS_FOLDER_NAME,
)
from app.investment_planning.errors import BudgetFolderDegradedError

FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass(frozen=True, slots=True)
class BudgetFolderIds:
    budgets_folder_id: str
    budget_templates_folder_id: str
    budget_plans_folder_id: str
    budget_scenarios_folder_id: str
    budget_proposals_folder_id: str

    def as_update(self) -> dict[str, str]:
        return {
            "budgets_folder_id": self.budgets_folder_id,
            "budget_templates_folder_id": self.budget_templates_folder_id,
            "budget_plans_folder_id": self.budget_plans_folder_id,
            "budget_scenarios_folder_id": self.budget_scenarios_folder_id,
            "budget_proposals_folder_id": self.budget_proposals_folder_id,
        }


def _require_live_child(
    *,
    drive: DriveClient,
    access_token: str,
    file_id: str,
    expected_parent_id: str,
    field: str,
) -> DriveFile:
    found = drive.get_file(access_token=access_token, file_id=file_id)
    if found is None or found.trashed or expected_parent_id not in found.parents:
        raise BudgetFolderDegradedError(
            f"Bound {field} is missing, trashed, or outside the depot root.",
            code="BUDGET_FOLDER_DEGRADED",
        )
    return found


def _ensure_named_child(
    *,
    drive: DriveClient,
    access_token: str,
    parent_id: str,
    name: str,
) -> DriveFile:
    existing = drive.find_child(access_token=access_token, parent_id=parent_id, name=name)
    if existing is not None and not existing.trashed:
        return existing
    return drive.create_folder(access_token=access_token, name=name, parent_id=parent_id)


def provision_budget_folders(
    *,
    drive: DriveClient,
    access_token: str,
    root_folder_id: str,
    bound_ids: dict[str, str | None],
) -> BudgetFolderIds:
    """Create missing budget folders. Never rebind a deleted bound folder by name."""
    bound_budgets = bound_ids.get("budgets_folder_id")
    if bound_budgets:
        budgets = _require_live_child(
            drive=drive,
            access_token=access_token,
            file_id=bound_budgets,
            expected_parent_id=root_folder_id,
            field="budgets_folder_id",
        )
    else:
        budgets = _ensure_named_child(
            drive=drive,
            access_token=access_token,
            parent_id=root_folder_id,
            name=BUDGETS_FOLDER_NAME,
        )

    children: dict[str, str] = {}
    for field, name in BUDGET_CHILD_FOLDER_NAMES:
        bound = bound_ids.get(field)
        if bound:
            child = _require_live_child(
                drive=drive,
                access_token=access_token,
                file_id=bound,
                expected_parent_id=budgets.file_id,
                field=field,
            )
        else:
            child = _ensure_named_child(
                drive=drive,
                access_token=access_token,
                parent_id=budgets.file_id,
                name=name,
            )
        children[field] = child.file_id

    return BudgetFolderIds(
        budgets_folder_id=budgets.file_id,
        budget_templates_folder_id=children["budget_templates_folder_id"],
        budget_plans_folder_id=children["budget_plans_folder_id"],
        budget_scenarios_folder_id=children["budget_scenarios_folder_id"],
        budget_proposals_folder_id=children["budget_proposals_folder_id"],
    )


def file_is_under_folder(file: DriveFile, folder_id: str) -> bool:
    return folder_id in file.parents
