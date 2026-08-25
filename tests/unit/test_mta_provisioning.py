"""MTA provisioning asset/docs presence — full approve/execute in M5-01."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_provisioning_docs_and_ddl_exist() -> None:
    assert (REPO_ROOT / "docs" / "backend" / "MTA_PROVISIONING.md").is_file()
    assert (REPO_ROOT / "app" / "modeling" / "mta" / "provisioning.py").is_file()
    assert (REPO_ROOT / "sql" / "mta" / "ddl" / "create_operational_tables_v1.sql.j2").is_file()
    assert (REPO_ROOT / "sql" / "mta" / "ddl" / "create_run_output_tables_v1.sql.j2").is_file()
