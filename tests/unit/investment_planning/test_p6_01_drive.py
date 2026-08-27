"""P6-01 Drive budget-folder provisioning."""

from __future__ import annotations

from tests.unit.api_support import auth_header
from tests.unit.google_support import connect_google, google_harness
from tests.unit.test_prem3_drive_governance import _setup_drive


def test_drive_setup_provisions_budget_folder_tree() -> None:
    harness = google_harness()
    _connection_id, binding = _setup_drive(harness)
    assert binding["budgets_folder_id"]
    assert binding["budget_templates_folder_id"]
    assert binding["budget_plans_folder_id"]
    assert binding["budget_scenarios_folder_id"]
    assert binding["budget_proposals_folder_id"]
    budgets = harness["drive"].files[binding["budgets_folder_id"]]
    assert budgets.name == "budgets"
    assert binding["root_folder_id"] in budgets.parents
    templates = harness["drive"].files[binding["budget_templates_folder_id"]]
    assert templates.name == "templates"
    assert binding["budgets_folder_id"] in templates.parents


def test_budget_folder_provisioning_is_idempotent() -> None:
    harness = google_harness()
    connection_id, first = _setup_drive(harness)
    created = list(harness["drive"].created)
    second = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/drive/setup",
        headers=auth_header(),
        json={"connection_id": connection_id, "import_enabled": True, "export_enabled": True},
    )
    assert second.status_code == 200
    assert second.json()["budgets_folder_id"] == first["budgets_folder_id"]
    assert harness["drive"].created == created


def test_deleted_budget_folder_is_not_rebound_by_name() -> None:
    harness = google_harness()
    connection_id, binding = _setup_drive(harness)
    harness["drive"].trash(binding["budgets_folder_id"])
    created_before = list(harness["drive"].created)
    repaired = harness["client"].post(
        f"/v1/workspaces/{harness['workspace']['workspace_id']}/integrations/drive/setup",
        headers=auth_header(),
        json={"connection_id": connection_id},
    )
    assert repaired.status_code == 200
    assert repaired.json()["status"] == "DEGRADED"
    assert repaired.json()["budgets_folder_id"] == binding["budgets_folder_id"]
    assert harness["drive"].created == created_before
