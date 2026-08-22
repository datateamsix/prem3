"""Vertical slice: requirements → discover → assess → transform → foundation ready."""

from __future__ import annotations

import pandas as pd

from app.data_foundation.contracts import SourceContract
from app.data_foundation.enums import (
    DataFoundationReadyStatus,
    SourceFoundationStatus,
    TransformId,
)
from app.data_foundation.warehouse import WarehouseTable
from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source, seed_kpi_source


def _contract() -> SourceContract:
    return SourceContract(
        grain="daily",
        date_field="date",
        date_format="YYYY-MM-DD",
        unique_keys=("date", "channel"),
        required_fields=("date", "spend"),
        currency="USD",
        timezone="America/New_York",
    )


def _kpi_contract() -> SourceContract:
    return SourceContract(
        grain="daily",
        date_field="date",
        date_format="YYYY-MM-DD",
        unique_keys=("date",),
        required_fields=("date", "revenue"),
        currency="USD",
        timezone="America/New_York",
    )


def test_happy_path_data_foundation_ready(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    seed_kpi_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    assert inventory.candidates
    media = next(
        item for item in inventory.candidates if "google_ads" in (item.resource.table_id or "")
    )
    kpi = next(item for item in inventory.candidates if "shopify" in (item.resource.table_id or ""))
    media_binding = service.bind_source(
        df_context,
        candidate_id=media.candidate_id,
        contract=_contract(),
        governance_import_ready=True,
    )
    kpi_binding = service.bind_source(
        df_context,
        candidate_id=kpi.candidate_id,
        contract=_kpi_contract(),
        governance_import_ready=True,
    )
    service.assess_source(df_context, media_binding.source_id)
    service.assess_source(df_context, kpi_binding.source_id)
    plan = service.compile_transformation_plan(
        df_context, source_id=media_binding.source_id, action_ids=[TransformId.DF_T006]
    )
    preview = service.get_transformation_preview(df_context, plan.plan_id)
    assert preview.mutated_source is False
    service.approve_plan(df_context, plan_id=plan.plan_id)
    transform = service.execute_transformation(df_context, transformation_plan_id=plan.plan_id)
    assert transform.source_mutated is False
    again = service.execute_transformation(df_context, transformation_plan_id=plan.plan_id)
    assert again.receipt_id == transform.receipt_id
    foundation = service.compile_foundation_plan(df_context)
    service.approve_plan(df_context, plan_id=foundation.plan_id)
    service.execute_plan(df_context, plan_id=foundation.plan_id)
    media_ready = service.evaluate_source_ready(df_context, media_binding.source_id)
    kpi_ready = service.evaluate_source_ready(df_context, kpi_binding.source_id)
    assert media_ready.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY
    assert kpi_ready.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY
    assert media_ready.status != "IMPORT_READY"
    assert "premodel_review_findings" in media_ready.model_dump()
    env = service.evaluate_data_foundation_ready(df_context)
    assert env.status_code is DataFoundationReadyStatus.DATA_FOUNDATION_READY
    assert service.get_overview(df_context).live_cloud_proof == "LIVE_CLOUD_PROOF_NOT_RUN"


def test_missing_periods_block_source_ready(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    stale = pd.DataFrame({"date": ["2026-01-01"], "channel": ["Paid Social"], "spend": [10.0]})
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="meta_ads_campaign_daily",
            frame=stale,
        )
    )
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    candidate = next(
        item for item in inventory.candidates if "meta_ads" in (item.resource.table_id or "")
    )
    binding = service.bind_source(
        df_context,
        candidate_id=candidate.candidate_id,
        contract=SourceContract(
            grain="daily",
            date_field="date",
            date_format="YYYY-MM-DD",
            unique_keys=("date", "channel"),
            required_fields=("date", "spend"),
            currency="USD",
            timezone="UTC",
        ),
        governance_import_ready=True,
    )
    service.frames[binding.source_id] = stale
    # Force temporal gap assessment via engine expected window
    from app.data_foundation.enums import ConnectionLifecycle
    from app.data_foundation.quality.engine import assess_frame
    from app.registry.loader import load_registry

    assessment = assess_frame(
        stale,
        source_id=binding.source_id,
        contract=binding.contract,
        access_works=True,
        authorization=ConnectionLifecycle.DISCOVERY_READY,
        freshness_known=True,
        latest_expected="2026-01-07",
        latest_observed="2026-01-01",
        expected_start="2026-01-01",
        expected_end="2026-01-07",
        registry_version=load_registry().version,
    )
    service.store.put_assessment(assessment)
    receipt = service.evaluate_source_ready(df_context, binding.source_id)
    assert receipt.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY
    assert any("TEMPORAL" in item for item in receipt.unresolved_findings)


def test_governance_import_ready_is_not_sufficient(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    binding = service.bind_source(
        df_context,
        candidate_id=inventory.candidates[0].candidate_id,
        contract=_contract(),
        governance_import_ready=False,
    )
    service.assess_source(df_context, binding.source_id)
    receipt = service.evaluate_source_ready(df_context, binding.source_id)
    assert receipt.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY
    assert receipt.governance_import_ready is False
