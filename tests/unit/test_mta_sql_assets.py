"""MTA SQL asset library presence and manifest path integrity."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mta_sql_manifest_lists_existing_paths() -> None:
    manifest_path = REPO_ROOT / "sql" / "mta" / "manifest.yaml"
    assert manifest_path.is_file()
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert data["library_id"] == "prem3_mta_sql_asset_library"
    for asset in data["assets"]:
        rel = asset["path"]
        assert (REPO_ROOT / rel).is_file(), f"missing asset path: {rel}"


def test_required_sql_templates_exist() -> None:
    required = [
        "sql/mta/udf/channel_grouping_v1.sql.j2",
        "sql/mta/udf/channel_grouping_current.sql.j2",
        "sql/mta/ddl/create_operational_tables_v1.sql.j2",
        "sql/mta/ddl/create_run_output_tables_v1.sql.j2",
        "sql/mta/source/ga4_sessions_last_click_v1.sql.j2",
        "sql/mta/source/ga4_sessions_collected_fallback_v1.sql.j2",
        "sql/mta/dml/merge_sessions_v1.sql.j2",
        "sql/mta/dml/merge_conversions_v1.sql.j2",
        "sql/mta/dml/merge_touchpoints_v1.sql.j2",
        "sql/mta/dml/rebuild_journeys_v1.sql.j2",
        "sql/mta/dml/rebuild_path_frequencies_v1.sql.j2",
        "sql/mta/dml/update_watermark_v1.sql.j2",
        "sql/mta/scheduled/daily_refresh_v1.sql.j2",
        "sql/mta/validation/channel_grouping_v1.sql.j2",
        "sql/mta/validation/uniqueness_v1.sql.j2",
        "sql/mta/validation/journey_ordering_v1.sql.j2",
        "sql/mta/validation/outputs_v1.sql.j2",
    ]
    for rel in required:
        assert (REPO_ROOT / rel).is_file(), rel
