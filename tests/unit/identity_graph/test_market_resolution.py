from __future__ import annotations

from app.identity_graph.enums import MarketResolutionMethod, ResolutionAuthority
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_property_bound_market_resolution(graph) -> None:
    market = make_canonical_market(graph)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="ga4:123456",
        method=MarketResolutionMethod.PROPERTY_BOUND,
        market_id=market.market_id,
        policy_id=policy.policy_id,
    )
    assert evidence.authority == ResolutionAuthority.RESOLVED
    assert evidence.market_id == market.market_id
    assert evidence.method == MarketResolutionMethod.PROPERTY_BOUND


def test_stream_bound_market_resolution(graph) -> None:
    market = make_canonical_market(graph)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.STREAM_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="stream:s1",
        method=MarketResolutionMethod.STREAM_BOUND,
        market_id=market.market_id,
        policy_id=policy.policy_id,
        rule_ref="stream-us",
    )
    assert evidence.authority == ResolutionAuthority.RESOLVED
    assert evidence.method == MarketResolutionMethod.STREAM_BOUND
    assert evidence.rule_ref == "stream-us"


def test_geo_mapping_not_implicit_default(graph) -> None:
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="geo.country",
        method=MarketResolutionMethod.GEO_MAPPING,
        market_id="mkt_us",
    )
    assert evidence.authority == ResolutionAuthority.UNRESOLVED
    assert "GEO_MAPPING_NOT_IMPLICIT_DEFAULT" in evidence.issues


def test_unresolved_market_stays_unresolved(graph) -> None:
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="ga4:unknown",
        method=MarketResolutionMethod.PROPERTY_BOUND,
        market_id=None,
        policy_id=policy.policy_id,
    )
    assert evidence.authority == ResolutionAuthority.UNRESOLVED
    assert evidence.market_id is None


def test_market_resolution_method_is_provenance(graph) -> None:
    market = make_canonical_market(graph)
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(
            MarketResolutionMethod.PROPERTY_BOUND,
            MarketResolutionMethod.HOSTNAME_MAPPING,
        ),
    )
    evidence = graph.resolve_market(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        source_ref="hostname:us.example",
        method=MarketResolutionMethod.HOSTNAME_MAPPING,
        market_id=market.market_id,
        policy_id=policy.policy_id,
    )
    assert evidence.method == MarketResolutionMethod.HOSTNAME_MAPPING
    assert evidence.source_ref == "hostname:us.example"
