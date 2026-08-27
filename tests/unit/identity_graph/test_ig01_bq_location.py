from __future__ import annotations

from app.identity_graph.enums import (
    BqLocationClass,
    GA4TopologyKind,
    GA4TopologyReadinessState,
    SourceOverlapPolicy,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_source_location_recorded(graph) -> None:
    source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="123456",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_123456",
        bq_location="europe-west2",
    )
    assert source.bq_location == "europe-west2"


def test_same_location_classification(graph) -> None:
    first = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="a",
        bq_project_id="p1",
        bq_dataset_id="analytics_a",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    second = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="b",
        bq_project_id="p1",
        bq_dataset_id="analytics_b",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MULTI_PROPERTY_SHARED_MARKETS,
        source_binding_ids=(first.ga4_source_binding_id, second.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    assert topology.location_class == BqLocationClass.SAME_LOCATION


def test_cross_location_requires_review(graph) -> None:
    market = make_canonical_market(graph)
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="us",
        bq_project_id="p-us",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=(market.market_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    eu = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="eu",
        bq_project_id="p-eu",
        bq_dataset_id="analytics_eu",
        bq_location="EU",
        declared_market_ids=(market.market_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.CUSTOM,
        source_binding_ids=(us.ga4_source_binding_id, eu.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert topology.location_class == BqLocationClass.CROSS_LOCATION
    assert "CROSS_LOCATION_REVIEW_REQUIRED" in topology.issues
    assert receipt.state == GA4TopologyReadinessState.GA4_TOPOLOGY_REVIEW_REQUIRED


def test_unknown_location_not_ready_for_unified_compilation(graph) -> None:
    make_canonical_market(graph)
    source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="unknown-loc",
        bq_project_id="p1",
        bq_dataset_id="analytics_x",
        bq_location="",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.SINGLE_MASTER_PROPERTY,
        source_binding_ids=(source.ga4_source_binding_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert topology.location_class == BqLocationClass.UNKNOWN_LOCATION
    assert topology.direct_union_ready is False
    assert "UNKNOWN_LOCATION_NOT_READY_FOR_UNIFIED_COMPILATION" in receipt.issues
    assert receipt.state != GA4TopologyReadinessState.GA4_TOPOLOGY_READY
