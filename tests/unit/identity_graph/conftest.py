from __future__ import annotations

import pytest

from app.business_iq.service import BusinessIqService
from app.business_iq.store import InMemoryBusinessIqStore
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.identity_graph.enums import MarketKind
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
