import pandas as pd

from app.data_foundation.contracts import SourceContract
from app.data_foundation.enums import PreviewMode, TransformId
from app.data_foundation.preview.safe import classify_fields
from app.data_foundation.warehouse import WarehouseTable
from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source


def test_sensitive_masking_and_no_star() -> None:
    keep, masked, omitted = classify_fields(
        ["date", "spend", "email", "phone", "customer_name", "user_id", "password"]
    )
    assert "email" in masked
    assert "user_id" in omitted
    assert "password" in omitted
    assert "date" in keep


def test_recent_requires_verified_time(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    binding = service.bind_source(
        df_context,
        candidate_id=inventory.candidates[0].candidate_id,
        contract=SourceContract(date_field="date", required_fields=("date", "spend")),
    )
    preview = service.preview_source(df_context, binding.source_id)
    assert preview.row_selection == "most_recent_verified_time"
    assert preview.compiled_sql and "SELECT *" not in preview.compiled_sql
    assert "LIMIT 5" in preview.compiled_sql


def test_sample_when_no_time_field(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="no_time",
            frame=pd.DataFrame({"channel": ["A", "B"], "spend": [1.0, 2.0]}),
        )
    )
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    candidate = next(item for item in inventory.candidates if item.resource.table_id == "no_time")
    binding = service.bind_source(
        df_context,
        candidate_id=candidate.candidate_id,
        contract=SourceContract(required_fields=("channel", "spend")),
    )
    preview = service.preview_source(df_context, binding.source_id)
    assert preview.row_selection == "sample_rows"


def test_transformation_and_canonical_preview(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    binding = service.bind_source(
        df_context,
        candidate_id=inventory.candidates[0].candidate_id,
        contract=SourceContract(
            grain="daily",
            date_field="date",
            required_fields=("date", "spend"),
            unique_keys=("date", "channel"),
        ),
    )
    plan = service.compile_transformation_plan(
        df_context, source_id=binding.source_id, action_ids=[TransformId.DF_T006]
    )
    preview = service.get_transformation_preview(df_context, plan.plan_id)
    assert preview.raw_source_unchanged is True
    assert preview.actions
    assert TransformId.DF_T020.value not in preview.actions or preview.requires_user_decision
    service.warehouse.write_foundation_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="prem3_modeling",
            table_id="canonical_media",
            frame=pd.DataFrame({"date": ["2026-01-01"], "spend": [1.0]}),
        )
    )
    canonical = service.canonical_preview(df_context)
    assert canonical.actual_row_count == 1
    assert canonical.latest_rows
    assert PreviewMode.CANONICAL_PREVIEW.value == "CANONICAL_PREVIEW"
