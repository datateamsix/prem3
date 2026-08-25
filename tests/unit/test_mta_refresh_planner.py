"""MTA refresh planner tests — implementation in M5-01."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_refresh_module_and_scheduled_template_exist() -> None:
    assert (REPO_ROOT / "app" / "modeling" / "mta" / "refresh.py").is_file()
    assert (REPO_ROOT / "sql" / "mta" / "scheduled" / "daily_refresh_v1.sql.j2").is_file()
    assert (REPO_ROOT / "assets" / "mta" / "scheduled_refresh_plan_v1.json").is_file()
