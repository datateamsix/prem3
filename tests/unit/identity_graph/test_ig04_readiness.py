from __future__ import annotations

from app.identity_graph.enums import (
    BqLocationClass,
    CrossLocationCompileStatus,
    GA4TopologyKind,
    UnifiedAnalyticsReadinessState,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    make_canonical_market,
)


def test_cross_location_blocks_readiness(graph) -> None:
    us = make_canonical_market(graph, name="United States")
    ca = make_canonical_market(graph, name="Canada")
    src_us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=(us.market_id,),
    )
    src_eu = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="eu",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_eu",
        bq_location="EU",
        declared_market_ids=(ca.market_id,),
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.PROPERTY_PER_MARKET,
        source_binding_ids=(src_us.ga4_source_binding_id, src_eu.ga4_source_binding_id),
    )
    assert topology.location_class == BqLocationClass.CROSS_LOCATION
    graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(src_us.ga4_source_binding_id, src_eu.ga4_source_binding_id),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    receipt = graph.analytics_readiness(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.state == UnifiedAnalyticsReadinessState.BLOCKED
    assert (
        receipt.cross_location_status
        == CrossLocationCompileStatus.CROSS_LOCATION_REVIEW_REQUIRED
    )
    assert "BQ_LOCATION_INCOMPATIBLE" in compiled.issues
    assert not compiled.artifact_refs or not any(
        item.current_pointer for item in compiled.artifact_refs
    )


def test_not_configured_readiness_before_compile(graph) -> None:
    receipt = graph.analytics_readiness(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.state == UnifiedAnalyticsReadinessState.NOT_CONFIGURED
    overview = graph.analytics_overview(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert overview.status == UnifiedAnalyticsReadinessState.NOT_CONFIGURED
    handoff = graph.analytics_handoff(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert handoff.mta_result_ready is False
