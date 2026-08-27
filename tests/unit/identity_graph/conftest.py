from __future__ import annotations

import pytest

from app.business_iq.service import BusinessIqService
from app.business_iq.store import InMemoryBusinessIqStore
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.identity_graph.enums import (
    GA4TopologyKind,
    GA4TopologyReadinessState,
    MarketKind,
    MarketResolutionMethod,
    SourceOverlapPolicy,
)
from app.identity_graph.service import CampaignIdentityService
from app.identity_graph.store import InMemoryIdentityGraphStore
from tests.unit.business_iq.conftest import ready_payload

TENANT_ID = "tenant-a"
PROJECT_ID = "wsp_projecta000000001"
REGISTRY_CHANNEL_ID = "search_paid"


@pytest.fixture
def tenant_ctx():
    ctx = TenantContext(
        tenant_id=TENANT_ID,
        user_id="user-a",
        auth_state=AuthState.AUTHENTICATED,
        entitlement_snapshot_id=None,
    )
    with bind_tenant(ctx) as bound:
        yield bound


@pytest.fixture
def biq_store(tenant_ctx) -> InMemoryBusinessIqStore:
    del tenant_ctx
    store = InMemoryBusinessIqStore()
    service = BusinessIqService(store=store)
    service.create_profile(
        tenant_id=TENANT_ID,
        workspace_id=PROJECT_ID,
        actor_id="user-a",
        payload=ready_payload(),
    )
    return store


@pytest.fixture
def graph(tenant_ctx, biq_store) -> CampaignIdentityService:
    del tenant_ctx
    service = CampaignIdentityService(
        store=InMemoryIdentityGraphStore(),
        business_iq_store=biq_store,
    )
    original = service.create_campaign
    default_market_ids: tuple[str, ...] | None = None

    def create_campaign_with_scope(**kwargs):
        nonlocal default_market_ids
        if "market_ids" not in kwargs:
            if default_market_ids is None:
                market = service.create_market(
                    tenant_id=TENANT_ID,
                    project_id=PROJECT_ID,
                    name="Default test market",
                    actor_id="user-a",
                )
                default_market_ids = (market.market_id,)
            kwargs["market_ids"] = default_market_ids
        kwargs.setdefault("channel_ids", (REGISTRY_CHANNEL_ID,))
        return original(**kwargs)

    service.create_campaign = create_campaign_with_scope  # type: ignore[method-assign]
    return service


def make_canonical_market(
    graph: CampaignIdentityService,
    *,
    name: str = "United States",
    market_kind: MarketKind = MarketKind.COUNTRY,
    project_id: str = PROJECT_ID,
    description: str | None = None,
    country_codes: tuple[str, ...] = (),
    region_codes: tuple[str, ...] = (),
):
    return graph.create_market(
        tenant_id=TENANT_ID,
        project_id=project_id,
        name=name,
        actor_id="user-a",
        description=description,
        market_kind=market_kind,
        country_codes=country_codes,
        region_codes=region_codes,
    )


def seed_ready_property_per_market(graph):
    us_market = make_canonical_market(graph, name="United States")
    ca_market = make_canonical_market(graph, name="Canada")
    policy = graph.upsert_market_policy(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        allowed_methods=(MarketResolutionMethod.PROPERTY_BOUND,),
    )
    us_source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="analytics_us",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_us",
        bq_location="US",
        declared_market_ids=(us_market.market_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    ca_source = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="analytics_ca",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_ca",
        bq_location="US",
        declared_market_ids=(ca_market.market_id,),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
    )
    graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=GA4TopologyKind.PROPERTY_PER_MARKET,
        source_binding_ids=(us_source.ga4_source_binding_id, ca_source.ga4_source_binding_id),
        overlap_policy=SourceOverlapPolicy.DISJOINT,
        market_resolution_policy_id=policy.policy_id,
    )
    receipt = graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.state == GA4TopologyReadinessState.GA4_TOPOLOGY_READY
    return {
        "us_market": us_market,
        "ca_market": ca_market,
        "us_source": us_source,
        "ca_source": ca_source,
        "policy": policy,
    }
