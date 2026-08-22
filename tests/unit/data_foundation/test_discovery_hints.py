import pandas as pd

from app.data_foundation.contracts import DiscoveryHints, SourceContract
from app.data_foundation.enums import RowCountKind, ScopeProvenance
from app.data_foundation.warehouse import WarehouseTable
from tests.unit.data_foundation.conftest import acme_snapshot


def test_strict_bq_dataset_boundary(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="ads",
            frame=pd.DataFrame({"date": ["2026-01-01"], "spend": [1.0]}),
        )
    )
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="finance",
            table_id="ledger",
            frame=pd.DataFrame({"date": ["2026-01-01"], "amount": [1.0]}),
        )
    )
    service.load_business_snapshot(df_context, acme_snapshot())
    service.set_discovery_hints(
        df_context,
        DiscoveryHints(
            tenant_id=df_context.tenant_id,
            workspace_id=df_context.workspace_id,
            datasets_to_prioritize=("marketing",),
            only_inspect_prioritized_datasets=True,
        ),
    )
    inventory = service.discover(df_context)
    tables = {item.resource.dataset_id for item in inventory.candidates if item.resource.dataset_id}
    assert tables == {"marketing"}


def test_drive_hints_stay_in_root(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    service.load_business_snapshot(df_context, acme_snapshot())
    service.register_drive_file(
        df_context,
        drive_file_id="file_keep",
        original_name="meta_ads.csv",
        parent_folder_id="root_prem3",
        payload=b"date,spend\n2026-01-01,1\n",
        mime_type="text/csv",
    )
    service.register_drive_file(
        df_context,
        drive_file_id="file_other",
        original_name="notes.csv",
        parent_folder_id="root_prem3",
        payload=b"a,b\n1,2\n",
        mime_type="text/csv",
    )
    service.set_discovery_hints(
        df_context,
        DiscoveryHints(
            tenant_id=df_context.tenant_id,
            workspace_id=df_context.workspace_id,
            drive_sources_or_paths_to_prioritize=("meta",),
        ),
    )
    inventory = service.discover(df_context)
    names = [item.resource.drive_file_id for item in inventory.candidates if item.resource.drive_file_id]
    assert "file_keep" in names
    assert "file_other" not in names


def test_physical_and_scope(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google_ads_campaign_daily",
            frame=pd.DataFrame(
                {"date": ["2026-01-01"], "country": ["US"], "spend": [1.0]}
            ),
            object_type="TABLE",
            num_rows=3,
            row_count_kind="EXACT",
            partition_field="date",
            partitioning_type="DAY",
            clustering_fields=("country",),
        )
    )
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="kpi_view",
            frame=pd.DataFrame({"date": ["2026-01-01"], "revenue": [1.0]}),
            object_type="VIEW",
            row_count_kind="SAMPLED",
            partition_field="date",
            partitioning_type="DAY",
        )
    )
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    table = next(item for item in inventory.candidates if item.resource.table_id == "google_ads_campaign_daily")
    view = next(item for item in inventory.candidates if item.resource.table_id == "kpi_view")
    bound = service.bind_source(
        df_context,
        candidate_id=table.candidate_id,
        contract=SourceContract(date_field="date", geo_field="country"),
    )
    view_bound = service.bind_source(
        df_context,
        candidate_id=view.candidate_id,
        contract=SourceContract(date_field="date"),
    )
    service.assess_source(df_context, bound.source_id)
    service.assess_source(df_context, view_bound.source_id)
    physical = service.get_physical_metadata(df_context, bound.source_id)
    assert physical.row_count_kind is RowCountKind.EXACT
    assert physical.partitioning_field == "date"
    view_physical = service.get_physical_metadata(df_context, view_bound.source_id)
    assert view_physical.object_type == "VIEW"
    assert view_physical.partitioning_type is None
    scope = service.get_source_scope(df_context, bound.source_id)
    assert scope.provenance in {ScopeProvenance.SCHEMA_DETECTED, ScopeProvenance.PROFILE_DETECTED}
