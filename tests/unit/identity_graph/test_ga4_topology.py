from __future__ import annotations

from app.identity_graph.enums import GA4TopologyKind, SourceOverlapPolicy, TopologyStatus
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_single_master_property_topology(graph) -> None:
    source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="123456",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_123456",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.SINGLE_MASTER_PROPERTY,
        source_binding_ids=(source.ga4_source_binding_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    assert topology.topology_kind == GA4TopologyKind.SINGLE_MASTER_PROPERTY
    assert topology.status == TopologyStatus.READY
    assert topology.direct_union_ready is True


def test_property_per_market_topology(graph) -> None:
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="prop_us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=("mkt_us",),
        overlap_policy=SourceOverlapPolicy.PARTITIONED_BY_MARKET,
    )
    ca = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="prop_ca",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_ca",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.PARTITIONED_BY_MARKET,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.PROPERTY_PER_MARKET,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.PARTITIONED_BY_MARKET,
    )
    assert topology.topology_kind == GA4TopologyKind.PROPERTY_PER_MARKET
    assert topology.status == TopologyStatus.READY


def test_master_plus_regional_requires_overlap_policy(graph) -> None:
    master = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
        bq_location="US",
    )
    regional = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="regional",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_regional",
        bq_location="US",
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
    )
    assert "OVERLAP_POLICY_REQUIRED" in topology.issues
    assert topology.status == TopologyStatus.REVIEW_REQUIRED
    assert topology.direct_union_ready is False


def test_bq_location_recorded(graph) -> None:
    source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="123456",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_123456",
        bq_location="europe-west2",
    )
    assert source.bq_location == "europe-west2"


def test_cross_location_not_declared_direct_union_ready(graph) -> None:
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    eu = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="eu",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_eu",
        bq_location="EU",
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(us.ga4_source_binding_id, eu.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    assert topology.direct_union_ready is False
    assert "CROSS_LOCATION_REVIEW_REQUIRED" in topology.issues
