from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AnalyticalCompilationStatus,
    GA4TopologyKind,
    MarketResolutionMethod,
    OverlapCompileStatus,
    SourceOverlapPolicy,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    make_canonical_market,
    seed_ready_property_per_market,
)


def test_master_plus_regional_without_policy_blocks(graph) -> None:
    us = make_canonical_market(graph, name="United States")
    ca = make_canonical_market(graph, name="Canada")
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    master = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
        bq_location="US",
        declared_market_ids=(us.market_id, ca.market_id),
    )
    regional = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="regional",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_regional",
        bq_location="US",
        declared_market_ids=(ca.market_id,),
    )
    graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
        market_resolution_policy_id=policy.policy_id,
    )
    graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.status == AnalyticalCompilationStatus.BLOCKED
    assert "OVERLAP_POLICY_REQUIRED" in compiled.issues


def test_dedupe_required_stays_blocked(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(
            fixture["us_source"].ga4_source_binding_id,
            fixture["ca_source"].ga4_source_binding_id,
        ),
        overlap_policy=SourceOverlapPolicy.DEDUPE_REQUIRED,
        market_resolution_policy_id=fixture["policy"].policy_id,
    )
    graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(
            fixture["us_source"].ga4_source_binding_id,
            fixture["ca_source"].ga4_source_binding_id,
        ),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.status == AnalyticalCompilationStatus.BLOCKED
    receipt = graph.analytics_readiness(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.overlap_status == OverlapCompileStatus.DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY
    assert "DEDUPE_POLICY_REQUIRED" in compiled.issues


def test_master_authoritative_excludes_overlapping_regional(graph) -> None:
    us = make_canonical_market(graph, name="United States")
    ca = make_canonical_market(graph, name="Canada")
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    master = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
        bq_location="US",
        declared_market_ids=(us.market_id,),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    regional = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="regional",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_regional",
        bq_location="US",
        declared_market_ids=(ca.market_id,),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
        market_resolution_policy_id=policy.policy_id,
    )
    graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    overlap = AnalyticalSessionSeed(
        ga4_source_binding_id=regional.ga4_source_binding_id,
        ga4_property_id="regional",
        ga_session_id="shared",
        subject_key="same-subject",
        session_start_ts="2026-04-01T00:00:00+00:00",
        source="(direct)",
        medium="(none)",
    )
    master_row = AnalyticalSessionSeed(
        ga4_source_binding_id=master.ga4_source_binding_id,
        ga4_property_id="master",
        ga_session_id="shared",
        subject_key="same-subject",
        session_start_ts="2026-04-01T00:00:00+00:00",
        source="(direct)",
        medium="(none)",
    )
    unique_regional = AnalyticalSessionSeed(
        ga4_source_binding_id=regional.ga4_source_binding_id,
        ga4_property_id="regional",
        ga_session_id="only-regional",
        subject_key="other-subject",
        session_start_ts="2026-04-01T00:00:00+00:00",
        source="(direct)",
        medium="(none)",
    )
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(master_row, overlap, unique_regional),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.status == AnalyticalCompilationStatus.READY
    sessions = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)
    assert len(sessions) == 2
    properties = {row.ga4_property_id for row in sessions}
    assert properties == {"master", "regional"}
