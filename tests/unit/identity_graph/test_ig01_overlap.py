from __future__ import annotations

from app.identity_graph.enums import (
    GA4TopologyKind,
    GA4TopologyReadinessState,
    MarketResolutionMethod,
    SourceOverlapPolicy,
    TopologyStatus,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def _two_market_sources(graph, overlap: SourceOverlapPolicy):
    us_market = make_canonical_market(graph, name="United States")
    ca_market = make_canonical_market(graph, name="Canada")
    us = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="analytics_us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=(us_market.market_id,),
        overlap_policy=overlap,
    )
    ca = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="analytics_ca",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_ca",
        bq_location="US",
        declared_market_ids=(ca_market.market_id,),
        overlap_policy=overlap,
    )
    return us, ca


def test_disjoint_sources_ready_when_other_requirements_pass(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.DISJOINT)
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.PROPERTY_PER_MARKET,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert topology.status == TopologyStatus.READY
    assert receipt.state == GA4TopologyReadinessState.GA4_TOPOLOGY_READY
    assert all(item.coverage_status.value == "COMPLETE" for item in receipt.coverage)


def test_master_authoritative_policy(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.MASTER_AUTHORITATIVE)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.MASTER_AUTHORITATIVE,
        market_resolution_policy_id=policy.policy_id,
    )
    assert topology.overlap_policy == SourceOverlapPolicy.MASTER_AUTHORITATIVE
    assert topology.status == TopologyStatus.READY


def test_regional_authoritative_policy(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.REGIONAL_AUTHORITATIVE)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.REGIONAL_AUTHORITATIVE,
        market_resolution_policy_id=policy.policy_id,
    )
    assert topology.overlap_policy == SourceOverlapPolicy.REGIONAL_AUTHORITATIVE
    assert topology.status == TopologyStatus.READY


def test_partitioned_by_market_policy(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.PARTITIONED_BY_MARKET)
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.PROPERTY_PER_MARKET,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.PARTITIONED_BY_MARKET,
    )
    assert topology.overlap_policy == SourceOverlapPolicy.PARTITIONED_BY_MARKET
    assert topology.status == TopologyStatus.READY


def test_dedupe_required_not_ready(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.DEDUPE_REQUIRED)
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DEDUPE_REQUIRED,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert topology.direct_union_ready is False
    assert topology.status == TopologyStatus.REVIEW_REQUIRED
    assert receipt.state != GA4TopologyReadinessState.GA4_TOPOLOGY_READY
    assert "DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY" in topology.issues


def test_review_required_not_ready(graph) -> None:
    us, ca = _two_market_sources(graph, SourceOverlapPolicy.REVIEW_REQUIRED)
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.MASTER_PLUS_REGIONAL,
        source_binding_ids=(us.ga4_source_binding_id, ca.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.REVIEW_REQUIRED,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert topology.status == TopologyStatus.REVIEW_REQUIRED
    assert topology.direct_union_ready is False
    assert receipt.state == GA4TopologyReadinessState.GA4_TOPOLOGY_REVIEW_REQUIRED
