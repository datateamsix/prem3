from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.business_iq.service import BusinessIqService
from app.business_iq.store import InMemoryBusinessIqStore

import pytest


@pytest.fixture
def tenant_ctx():
    ctx = TenantContext(
        tenant_id="tenant-a",
        user_id="user-a",
        auth_state=AuthState.AUTHENTICATED,
        entitlement_snapshot_id=None,
    )
    with bind_tenant(ctx) as bound:
        yield bound


@pytest.fixture
def biq(tenant_ctx) -> BusinessIqService:
    del tenant_ctx
    return BusinessIqService(store=InMemoryBusinessIqStore())


def ready_payload() -> dict:
    return {
        "business_identity": {"legal_name": "Acme", "brand_name": "Acme Commerce"},
        "measurement_objectives": [
            {"objective_id": "obj_allocate", "statement": "Allocate budget across channels"}
        ],
        "kpi": "Revenue",
        "kpi_definition": "Completed ecommerce orders net of refunds.",
        "kpi_custom_text": "Net revenue after refunds, not Gross Merchandise Value",
        "markets": [{"market_id": "mkt_us", "name": "United States"}],
        "marketing_portfolio": [
            {
                "channel_id": "bch_search",
                "canonical_name": "Paid Search",
                "custom_name": "Brand + Generic Search",
                "business_roles": ["demand capture"],
                "markets": ["United States"],
                "active_from": "2023-01-01",
                "lifecycle_status": "ACTIVE",
            },
            {
                "channel_id": "bch_audio",
                "canonical_name": "Streaming Audio",
                "custom_name": "Streaming Audio",
                "business_roles": ["awareness"],
                "markets": ["United States"],
                "active_from": "2026-04-01",
                "lifecycle_status": "ACTIVE",
            },
        ],
        "facts": [
            {
                "fact_id": "bfact_kpi",
                "concept": "kpi",
                "value": "Revenue",
                "provenance": "PROVIDED_BY_USER",
            }
        ],
        "events": [
            {
                "event_id": "bevt_launch",
                "event_type": "MEDIA_LAUNCH",
                "name": "Streaming Audio launch",
                "start_date": "2026-04-01",
            }
        ],
        "prior_evidence": [
            {
                "evidence_id": "bpe_holdout",
                "evidence_type": "geo_holdout",
                "description": "2024 paid social holdout",
                "channel": "Paid Social",
            }
        ],
        "metadata": {"logo_asset_ref": "drive:logo"},
    }
