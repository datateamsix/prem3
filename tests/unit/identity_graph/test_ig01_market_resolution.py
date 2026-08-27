from __future__ import annotations

from app.identity_graph.enums import (
    GA4TopologyKind,
    MarketResolutionMethod,
    ResolutionAuthority,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_property_bound_resolution(graph) -> None:
    market = make_canonical_market(graph)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="ga4:analytics_us",
        method=MarketResolutionMethod.PROPERTY_BOUND,
        market_id=market.market_id,
        policy_id=policy.policy_id,
    )
    assert evidence.method == MarketResolutionMethod.PROPERTY_BOUND
    assert evidence.authority == ResolutionAuthority.RESOLVED
    assert evidence.market_id == market.market_id


def test_stream_bound_resolution(graph) -> None:
    market = make_canonical_market(graph, name="Canada")
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.STREAM_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="stream:s-ca",
        method=MarketResolutionMethod.STREAM_BOUND,
        market_id=market.market_id,
        policy_id=policy.policy_id,
        rule_ref="stream-ca",
    )
    assert evidence.method == MarketResolutionMethod.STREAM_BOUND
    assert evidence.rule_ref == "stream-ca"


def test_custom_dimension_resolution_contract(graph) -> None:
    market = make_canonical_market(graph, name="United Kingdom")
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.CUSTOM_DIMENSION,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="cd:market_code",
        method=MarketResolutionMethod.CUSTOM_DIMENSION,
        market_id=market.market_id,
        policy_id=policy.policy_id,
        rule_ref="cd.market_code=UK",
    )
    assert evidence.method == MarketResolutionMethod.CUSTOM_DIMENSION
    assert evidence.authority == ResolutionAuthority.RESOLVED


def test_hostname_resolution_contract(graph) -> None:
    market = make_canonical_market(graph)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.HOSTNAME_MAPPING,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="hostname:us.example",
        method=MarketResolutionMethod.HOSTNAME_MAPPING,
        market_id=market.market_id,
        policy_id=policy.policy_id,
        rule_ref="us.example",
    )
    assert evidence.method == MarketResolutionMethod.HOSTNAME_MAPPING
    assert evidence.authority == ResolutionAuthority.RESOLVED


def test_geo_mapping_requires_explicit_policy(graph) -> None:
    market = make_canonical_market(graph)
    implicit = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="geo.country",
        method=MarketResolutionMethod.GEO_MAPPING,
        market_id=market.market_id,
    )
    assert implicit.authority == ResolutionAuthority.UNRESOLVED
    assert "GEO_MAPPING_NOT_IMPLICIT_DEFAULT" in implicit.issues
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.GEO_MAPPING,),
    )
    explicit = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="geo.country",
        method=MarketResolutionMethod.GEO_MAPPING,
        market_id=market.market_id,
        policy_id=policy.policy_id,
        rule_ref="US→canonical",
    )
    assert explicit.authority == ResolutionAuthority.RESOLVED
    assert explicit.method == MarketResolutionMethod.GEO_MAPPING


def test_unresolved_market_fails_closed(graph) -> None:
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="ga4:unknown",
        method=MarketResolutionMethod.UNRESOLVED,
        market_id=None,
        policy_id=policy.policy_id,
    )
    assert evidence.authority == ResolutionAuthority.UNRESOLVED
    assert evidence.market_id is None
    master = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="master",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_master",
        bq_location="US",
    )
    make_canonical_market(graph, name="United States")
    make_canonical_market(graph, name="Canada")
    topology = graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.SINGLE_MASTER_PROPERTY,
        source_binding_ids=(master.ga4_source_binding_id,),
        overlap_policy=None,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert "MARKET_RESOLUTION_REQUIRED" in topology.issues or (
        "MARKET_RESOLUTION_REQUIRED" in receipt.issues
    )
    assert receipt.state.value != "GA4_TOPOLOGY_READY"
