"""Shared Data Foundation test helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.data_foundation.context import context_from_tenant
from app.data_foundation.contracts import BusinessChannelFact, BusinessProfileSnapshot
from app.data_foundation.enums import ConnectionLifecycle
from app.data_foundation.service import DataFoundationService
from app.data_foundation.store import InMemoryDataFoundationStore
from app.data_foundation.warehouse import FoundationWarehouse, WarehouseTable


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
def df_context(tenant_ctx):
    del tenant_ctx
    return context_from_tenant(
        workspace_id="wsp_test00000000000001",
        destination_project_id="acme_analytics",
        source_project_ids=("acme_analytics",),
        source_dataset_ids=("marketing",),
        drive_root_folder_id="root_prem3",
        google_connection_id="gconn_test000000000001",
        bq_lifecycle=ConnectionLifecycle.AUTHORIZED,
        drive_lifecycle=ConnectionLifecycle.DISCOVERY_READY,
        read_verified=True,
        write_verified=True,
    )


@pytest.fixture
def service() -> DataFoundationService:
    return DataFoundationService(
        store=InMemoryDataFoundationStore(),
        warehouse=FoundationWarehouse(),
    )


def acme_snapshot(*, tenant_id: str = "tenant-a", workspace_id: str = "wsp_test00000000000001"):
    return BusinessProfileSnapshot(
        snapshot_id="bps_acme00000000000001",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        version="Business Profile v3",
        fingerprint="a" * 64,
        business_context_ready=True,
        kpi="Revenue",
        kpi_definition="Completed ecommerce orders net of refunds.",
        objective="Allocate budget across marketing channels",
        markets=("United States",),
        channels=(
            BusinessChannelFact(channel_name="Paid Search", role="demand capture"),
            BusinessChannelFact(channel_name="Paid Social", role="multiple roles"),
        ),
        promotions_relevant=True,
        inventory_relevant=True,
        competition_relevant=True,
        seasonality_relevant=True,
        events=(),
        prior_evidence=(),
        unknowns=(),
    )


def clean_media_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "channel": ["Paid Search", "Paid Search", "Paid Search"],
            "spend": [100.0, 110.0, 90.0],
            "impressions": [1000, 1100, 900],
        }
    )


def seed_clean_source(service: DataFoundationService) -> None:
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google_ads_campaign_daily",
            frame=clean_media_frame(),
        )
    )


def seed_kpi_source(service: DataFoundationService) -> None:
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="shopify_orders_daily",
            frame=pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                    "revenue": [500.0, 520.0, 480.0],
                    "orders": [20, 22, 19],
                }
            ),
        )
    )


NOW = datetime.now(UTC)
