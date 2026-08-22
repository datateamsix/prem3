from app.data_foundation.bigquery.discovery import discover_tables, shortlist_and_compile
from app.data_foundation.contracts import QueryBudgetPolicy
from tests.unit.data_foundation.conftest import seed_clean_source


def test_discovery_is_metadata_first_and_scoped(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    tables = discover_tables(service.warehouse, context=df_context)
    assert tables
    assert all(item.dataset_id != "prem3_modeling" for item in tables)
    compiled = shortlist_and_compile(
        tables[0],
        context=df_context,
        policy=QueryBudgetPolicy(require_partition_predicate=False),
    )
    assert "SELECT *" not in compiled.sql
    assert compiled.operation == "bounded_profile"


def test_discover_service_builds_inventory(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    from tests.unit.data_foundation.conftest import acme_snapshot

    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    assert inventory.candidates
    assert "SELECT *" not in " ".join(service.warehouse.queries)
