from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AnalyticalCompilationStatus,
    CampaignIdentitySource,
    RowResolutionStatus,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_utm_id_resolves_via_ig03_and_utm_campaign_does_not(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Summer",
        actor_id="user-a",
        market_ids=(fixture["us_market"].market_id,),
        planned_start_date="2026-04-01",
        planned_end_date="2026-06-30",
        utm_campaign="summer-sale",
    )
    campaign_id = created.campaign.campaign_id
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
                utm_id=campaign_id,
                campaign_name="summer-sale",
            ),
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="2",
                subject_key="sub-b",
                session_start_ts="2026-04-01T01:00:00+00:00",
                source="(direct)",
                medium="(none)",
                campaign_name="summer-sale",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    rows = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)
    resolved = next(row for row in rows if row.campaign_id == campaign_id)
    unresolved = next(row for row in rows if row.campaign_id is None)
    assert resolved.campaign_identity_source == CampaignIdentitySource.PREM3_UTM_ID
    assert resolved.parent_campaign_id is None
    assert unresolved.campaign_status == RowResolutionStatus.UNRESOLVED
    assert compiled.status == AnalyticalCompilationStatus.READY


def test_unresolved_campaign_does_not_block_unless_slice_required(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
                campaign_name="not-an-id",
            ),
        ),
    )
    ready = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert ready.status == AnalyticalCompilationStatus.READY
    blocked = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
        campaign_slice_required=True,
    )
    assert blocked.status == AnalyticalCompilationStatus.BLOCKED
    assert "CAMPAIGN_SLICE_REQUIRED" in blocked.issues
    assert blocked.compilation_id != ready.compilation_id
