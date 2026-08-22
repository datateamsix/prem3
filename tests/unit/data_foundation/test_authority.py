import pytest

from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.data_foundation.context import context_from_tenant
from app.data_foundation.contracts import SourceContract
from app.data_foundation.enums import ConnectionLifecycle, TransformId
from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source


def test_cross_tenant_bind_denied(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    inventory = service.discover(df_context)
    other = TenantContext(
        tenant_id="tenant-b",
        user_id="user-b",
        auth_state=AuthState.AUTHENTICATED,
    )
    with bind_tenant(other):
        foreign = context_from_tenant(
            workspace_id="wsp_other000000000001",
            destination_project_id="other_proj",
            source_project_ids=("other_proj",),
            bq_lifecycle=ConnectionLifecycle.AUTHORIZED,
            read_verified=True,
            write_verified=True,
        )
        with pytest.raises(PermissionError, match="Cross-tenant"):
            service.bind_source(
                foreign,
                candidate_id=inventory.candidates[0].candidate_id,
                contract=SourceContract(currency="USD", timezone="UTC"),
            )


def test_unapproved_lossy_plan_cannot_execute(service, df_context, tenant_ctx) -> None:
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
            date_format="YYYY-MM-DD",
            unique_keys=("date", "channel"),
            required_fields=("date", "spend"),
            currency="USD",
            timezone="America/New_York",
        ),
        governance_import_ready=True,
    )
    plan = service.compile_transformation_plan(
        df_context,
        source_id=binding.source_id,
        action_ids=[TransformId.DF_T011],
        parameters={"DF-T011": {}},
    )
    with pytest.raises(PermissionError, match="Unapproved"):
        service.execute_transformation(df_context, transformation_plan_id=plan.plan_id)


def test_changed_fingerprint_invalidates_plan(service, df_context, tenant_ctx) -> None:
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
            unique_keys=("date", "channel"),
            required_fields=("date", "spend"),
            currency="USD",
            timezone="UTC",
        ),
        governance_import_ready=True,
    )
    plan = service.compile_transformation_plan(
        df_context, source_id=binding.source_id, action_ids=[TransformId.DF_T006]
    )
    service.frames[binding.source_id] = service.frames[binding.source_id].iloc[:1]
    with pytest.raises(PermissionError, match="fingerprint"):
        service.execute_transformation(df_context, transformation_plan_id=plan.plan_id)
