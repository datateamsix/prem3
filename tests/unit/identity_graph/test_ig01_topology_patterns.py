from __future__ import annotations

from app.identity_graph.enums import GA4TopologyKind, SourceOverlapPolicy, TopologyStatus
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_single_master_property(graph) -> None:
    source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
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


def test_property_per_market(graph) -> None:
    us_market = make_canonical_market(graph, name="United States")
    ca_market = make_canonical_market(graph, name="Canada")
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="prop_us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=(us_market.market_id,),
        overlap_policy=SourceOverlapPolicy.PARTITIONED_BY_MARKET,
    )
    ca = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="prop_ca",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_ca",
        bq_location="US",
        declared_market_ids=(ca_market.market_id,),
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
    assert {us.bq_project_id, ca.bq_project_id} == {"modelready-m3"}
    assert topology.status == TopologyStatus.READY


def test_multiple_properties_one_bq_project(graph) -> None:
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="111",
        bq_project_id="shared-bq",
        bq_dataset_id="analytics_111",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    uk = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="222",
        bq_project_id="shared-bq",
        bq_dataset_id="analytics_222",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MULTI_PROPERTY_SHARED_MARKETS,
        source_binding_ids=(us.ga4_source_binding_id, uk.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    assert us.bq_project_id == uk.bq_project_id == "shared-bq"
    assert topology.topology_kind == GA4TopologyKind.MULTI_PROPERTY_SHARED_MARKETS
    assert topology.location_class.value == "SAME_LOCATION"


def test_multiple_bq_projects(graph) -> None:
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="us-prop",
        bq_project_id="bq-us",
        bq_dataset_id="analytics_us",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    uk = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="uk-prop",
        bq_project_id="bq-uk",
        bq_dataset_id="analytics_uk",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.CUSTOM,
        source_binding_ids=(us.ga4_source_binding_id, uk.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    assert {us.bq_project_id, uk.bq_project_id} == {"bq-us", "bq-uk"}
    assert topology.location_class.value == "SAME_LOCATION"


def test_master_plus_regional(graph) -> None:
    master = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    regional = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="regional",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_regional",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(master.ga4_source_binding_id, regional.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
    )
    assert topology.topology_kind == GA4TopologyKind.MASTER_PLUS_REGIONAL
    assert topology.overlap_policy == SourceOverlapPolicy.MASTER_AUTHORITATIVE
    assert topology.direct_union_ready is True


def test_cross_location(graph) -> None:
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="us",
        bq_project_id="bq-us",
        bq_dataset_id="analytics_us",
        bq_location="US",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    eu = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="eu",
        bq_project_id="bq-eu",
        bq_dataset_id="analytics_eu",
        bq_location="EU",
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.CUSTOM,
        source_binding_ids=(us.ga4_source_binding_id, eu.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    assert topology.location_class.value == "CROSS_LOCATION"
    assert topology.direct_union_ready is False
    assert "CROSS_LOCATION_REVIEW_REQUIRED" in topology.issues
