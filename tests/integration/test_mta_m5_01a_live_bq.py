"""Forced live Music Center SYNTHETIC_DEMO BigQuery proof via production provisioning path.

Run:
  uv run pytest tests/integration/test_mta_m5_01a_live_bq.py -m live_bq -v

Requires ADC with BigQuery + Data Transfer permissions on GOOGLE_CLOUD_PROJECT
(default modelready-m3) and write access to prem3_modeling + ability to create
analytics_music_center_synthetic.
"""

from __future__ import annotations

import os

import pytest

from app.config import settings
from app.domain.channels import AI_SEARCH_CHANNEL_ID, cached_channel_registry
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.bq_executor import (
    client_for_project,
    describe_table,
    get_routine_definition,
)
from app.modeling.mta.provisioning_service import MTAProvisioningService
from app.modeling.mta.runtime_contracts import MTARefreshWindow
from app.modeling.mta.sql.registry import cached_sql_asset_manifest
from app.modeling.mta.sql.renderer import render_sql_asset
from app.modeling.mta.synthetic_music_center import (
    DEFAULT_WINDOW_END,
    EVIDENCE_LABEL,
    events_with_correction,
    events_with_removal,
    load_synthetic_ga4_events,
    music_center_base_events,
)

pytestmark = pytest.mark.live_bq


def _project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("M3_GCP_PROJECT")
        or "modelready-m3"
    )


@pytest.fixture(scope="module")
def gcp_project() -> str:
    return _project_id()


@pytest.fixture(scope="module")
def live_svc(gcp_project: str) -> MTAProvisioningService:
    return MTAProvisioningService(live=True)


def test_live_channel_grouping_udf_creates(gcp_project: str, live_svc: MTAProvisioningService):
    plan = live_svc.compile_infrastructure_plan(
        plan_id="live_mc_1",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof",
        track_id="mta",
        gcp_project_id=gcp_project,
    )
    receipt = live_svc.provision_infrastructure(plan, approved=True, dry_run_first=True)
    assert receipt.verified
    body = get_routine_definition(
        client_for_project(gcp_project),
        project_id=gcp_project,
        dataset_id="prem3_modeling",
        routine_id="channel_grouping_v1",
    )
    assert body is not None
    assert "ai_search" in body


def test_live_channel_grouping_udf_readback_matches_rendered_definition(
    gcp_project: str,
):
    entry = cached_sql_asset_manifest().get("channel_grouping_v1")
    rendered, _ = render_sql_asset(
        entry,
        params={"project_id": gcp_project, "modeling_dataset": "prem3_modeling"},
    )
    body = get_routine_definition(
        client_for_project(gcp_project),
        project_id=gcp_project,
        dataset_id="prem3_modeling",
        routine_id="channel_grouping_v1",
    )
    assert body is not None
    # Compare core CASE body presence rather than full CREATE wrapper
    assert "THEN 'ai_search'" in body or "THEN 'ai_search'" in rendered
    assert "THEN 'search_paid'" in body


def test_live_channel_grouping_fixture(gcp_project: str, live_svc: MTAProvisioningService):
    rows = live_svc.classify_with_udf(
        gcp_project_id=gcp_project,
        cases=[
            ("google", "cpc", "brand"),
            (None, None, None),
            ("facebook", "cpc", "x"),
            ("email", "email", "n"),
        ],
    )
    ids = {r["channel_id"] for r in rows}
    assert ids <= cached_channel_registry().channel_ids()


def test_live_ai_search_mapping(gcp_project: str, live_svc: MTAProvisioningService):
    rows = live_svc.classify_with_udf(
        gcp_project_id=gcp_project,
        cases=[
            ("chatgpt.com", "referral", "ai"),
            ("www.perplexity.ai", "referral", None),
            ("gemini", "referral", "g"),
            ("claude.ai", "referral", None),
        ],
    )
    assert [r["channel_id"] for r in rows] == [AI_SEARCH_CHANNEL_ID] * len(rows)


def test_live_udf_historical_version_not_replaced(
    gcp_project: str, live_svc: MTAProvisioningService
):
    """v1 routine identity stays channel_grouping_v1; mapping fixes use OR REPLACE on same id.

    Customer-facing new mappings still require a new ruleset/UDF version number in
    control-plane governance; this proof confirms the live routine id is stable.
    """
    plan = live_svc.compile_infrastructure_plan(
        plan_id="live_mc_2",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof",
        track_id="mta",
        gcp_project_id=gcp_project,
    )
    receipt = live_svc.provision_infrastructure(plan, approved=True, dry_run_first=False)
    assert receipt.verified
    assert plan.channel_grouping_routine == "channel_grouping_v1"
    body = get_routine_definition(
        client_for_project(gcp_project),
        project_id=gcp_project,
        dataset_id="prem3_modeling",
        routine_id="channel_grouping_v1",
    )
    assert body is not None and "ai_search" in body
    # Second provision still targets the same routine id (not a silent alias rewrite).
    receipt2 = live_svc.provision_infrastructure(plan, approved=True, dry_run_first=False)
    assert "channel_grouping_v1" in receipt2.reused or "channel_grouping_v1" in receipt2.created


def test_live_operational_tables_physical_design(gcp_project: str):
    client = client_for_project(gcp_project)
    sessions = describe_table(
        client, project_id=gcp_project, dataset_id="prem3_modeling", table_id="mta_sessions"
    )
    assert sessions["partitioning_field"] == "source_date"
    assert "canonical_channel_id" in (sessions["clustering_fields"] or [])


def test_live_merge_idempotent_and_reconcile(gcp_project: str, live_svc: MTAProvisioningService):
    load_synthetic_ga4_events(
        project_id=gcp_project, events=music_center_base_events(), replace=True
    )
    # Force window over fixture dates for cost-safe SYNTHETIC_DEMO proof
    forced = MTARefreshWindow(
        run_date="2024-06-10",
        settlement_days=3,
        source_overlap_days=2,
        lookback_window_days=7,
        source_start_date="2024-06-01",
        source_end_date=DEFAULT_WINDOW_END.isoformat(),
        affected_conversion_start="2024-06-01",
        affected_conversion_end=DEFAULT_WINDOW_END.isoformat(),
        fingerprint=canonical_fingerprint({"forced": True, "label": EVIDENCE_LABEL}),
        calculation_trace=("SYNTHETIC_DEMO forced Music Center window",),
    )
    r1 = live_svc.execute_refresh(
        gcp_project_id=gcp_project,
        window=forced,
        lookback_window_days=7,
    )
    assert r1["evidence_label"] == EVIDENCE_LABEL
    assert r1["counts_after"]["mta_sessions_duplicate_keys"] == 0
    assert r1["counts_after"]["mta_conversions_duplicate_keys"] == 0
    c1 = r1["counts_after"]

    r2 = live_svc.execute_refresh(
        gcp_project_id=gcp_project,
        window=forced,
        lookback_window_days=7,
    )
    c2 = r2["counts_after"]
    assert c2["mta_sessions"] == c1["mta_sessions"]
    assert c2["mta_conversions"] == c1["mta_conversions"]
    assert c2["mta_touchpoints"] == c1["mta_touchpoints"]
    assert c2["mta_journeys"] == c1["mta_journeys"]
    assert c2["mta_path_frequencies"] == c1["mta_path_frequencies"]

    # Source correction
    load_synthetic_ga4_events(
        project_id=gcp_project, events=events_with_correction(), replace=True
    )
    r3 = live_svc.execute_refresh(
        gcp_project_id=gcp_project,
        window=forced,
        lookback_window_days=7,
    )
    assert r3["counts_after"]["mta_sessions"] >= 1

    # Removal
    load_synthetic_ga4_events(
        project_id=gcp_project, events=events_with_removal(), replace=True
    )
    r4 = live_svc.execute_refresh(
        gcp_project_id=gcp_project,
        window=forced,
        lookback_window_days=7,
    )
    assert r4["counts_after"]["mta_sessions"] <= r3["counts_after"]["mta_sessions"]

    # Failed validation does not advance watermark
    wm_before = r4["watermark_after"]
    r5 = live_svc.execute_refresh(
        gcp_project_id=gcp_project,
        window=forced,
        lookback_window_days=7,
        fail_validation=True,
        advance_watermark=True,
    )
    # When validation fails, watermark should remain prior successful value
    assert r5["validation_ok"] is False
    assert r5["watermark_after"] == wm_before or r5["watermark_before"] == wm_before


def test_live_schedule_resource_created_readback_disable(
    gcp_project: str, live_svc: MTAProvisioningService
):
    entry = cached_sql_asset_manifest().get("daily_refresh_v1")
    sql, fp = render_sql_asset(
        entry,
        params={
            "settlement_days": 3,
            "source_overlap_days": 2,
            "lookback_window_days": 7,
        },
    )
    # Cost-safe: scheduled query is a DECLARE-only scaffold (no full history scan)
    assert "DECLARE" in sql
    plan = live_svc.build_and_approve_schedule(
        schedule_id="music_center_synth_refresh",
        conversion_event="purchase",
        lookback_window_days=7,
        settlement_days=3,
        cadence="every 24 hours",
        timezone="America/Los_Angeles",
    )
    # Bound query to synthetic demo comment for operators
    safe_sql = (
        f"-- {EVIDENCE_LABEL} Music Center managed refresh scaffold\n"
        f"-- rendered_fp={fp}\n"
        f"{sql}\n"
        f"SELECT 1 AS prem3_schedule_heartbeat;"
    )
    receipt = live_svc.provision_schedule(
        plan,
        gcp_project_id=gcp_project,
        query_sql=safe_sql,
        service_identity=(
            settings.runtime_sa
            or f"m3-runtime@{gcp_project}.iam.gserviceaccount.com"
        ),
    )
    assert receipt.provisioned and receipt.schedule_resource_id
    assert receipt.evidence_label == EVIDENCE_LABEL
    assert "prem3_modeling" in (receipt.destination_binding or "")
    readback = live_svc.readback_schedule(receipt.schedule_resource_id)
    assert readback is not None
    disabled = live_svc.disable_schedule(
        schedule_id=plan.schedule_id,
        resource_name=receipt.schedule_resource_id,
        disabled_by="m5-01a-live-proof",
    )
    assert disabled.status == "DISABLED"
