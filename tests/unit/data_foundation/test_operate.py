from app.data_foundation.contracts import SourceContract
from app.data_foundation.enums import SourceFoundationStatus
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


def _bind_media(service, df_context):
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    media = next(
        item for item in inventory.candidates if "google_ads" in (item.resource.table_id or "")
    )
    return service.bind_source(
        df_context,
        candidate_id=media.candidate_id,
        contract=_contract(),
        governance_import_ready=True,
    )


def test_quality_overview_is_deterministic_aggregate(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    binding = _bind_media(service, df_context)
    service.assess_source(df_context, binding.source_id)
    overview = service.get_quality_overview(df_context, binding.source_id)
    again = service.get_quality_overview(df_context, binding.source_id)
    assert overview.source_id == binding.source_id
    assert overview.blocker_count + overview.review_count + overview.advisory_count + overview.pass_count > 0
    assert overview.blocker_count == again.blocker_count
    assert overview.pass_count == again.pass_count


def test_retire_degrades_source_readiness(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    binding = _bind_media(service, df_context)
    service.assess_source(df_context, binding.source_id)
    ready = service.evaluate_source_ready(df_context, binding.source_id)
    assert ready.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY
    retired = service.retire_source(df_context, binding.source_id)
    assert retired.lifecycle_state == "RETIRED"
    degraded = service.store.get_current_source_receipt(binding.source_id)
    assert degraded.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY


def test_replace_source_retires_prior_and_binds_replacement(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    seed_clean_source(service)
    seed_kpi_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    media = next(
        item for item in inventory.candidates if "google_ads" in (item.resource.table_id or "")
    )
    kpi = next(item for item in inventory.candidates if "shopify" in (item.resource.table_id or ""))
    first = service.bind_source(
        df_context, candidate_id=media.candidate_id, contract=_contract(), governance_import_ready=True
    )
    service.assess_source(df_context, first.source_id)
    replacement = service.replace_source(
        df_context,
        source_id=first.source_id,
        candidate_id=kpi.candidate_id,
        contract=SourceContract(
            grain="daily",
            date_field="date",
            date_format="YYYY-MM-DD",
            unique_keys=("date",),
            required_fields=("date", "revenue"),
            currency="USD",
            timezone="America/New_York",
        ),
        governance_import_ready=True,
    )
    assert replacement.source_id != first.source_id
    assert service.store.get_binding(first.source_id).lifecycle_state == "RETIRED"
    assert replacement.lifecycle_state == "BOUND"
    transitions = service.store.list_transitions(workspace_id=df_context.workspace_id)
    assert transitions[0].historical_source_id == first.source_id


def test_reauthorize_and_health_retrieval(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    binding = _bind_media(service, df_context)
    service.assess_source(df_context, binding.source_id)
    health = service.get_source_health(df_context, binding.source_id)
    assert health["assessment"].source_id == binding.source_id
    assert health["quality_overview"].source_id == binding.source_id
    reauth = service.reauthorize_source(df_context, binding.source_id)
    assert reauth.source_id == binding.source_id


def test_add_source_and_drive_bq_alignment(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    seed_kpi_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    media = next(
        item for item in inventory.candidates if "google_ads" in (item.resource.table_id or "")
    )
    kpi = next(item for item in inventory.candidates if "shopify" in (item.resource.table_id or ""))
    service.bind_source(
        df_context, candidate_id=media.candidate_id, contract=_contract(), governance_import_ready=True
    )
    service.bind_source(
        df_context,
        candidate_id=kpi.candidate_id,
        contract=SourceContract(
            grain="daily",
            date_field="date",
            date_format="YYYY-MM-DD",
            unique_keys=("date",),
            required_fields=("date", "revenue"),
            currency="USD",
            timezone="America/New_York",
        ),
        governance_import_ready=True,
    )
    alignment = service.get_cross_source_alignment(df_context)
    assert alignment.rows
    assert {row.dimension for row in alignment.rows} >= {"Currency", "Time zone"}
