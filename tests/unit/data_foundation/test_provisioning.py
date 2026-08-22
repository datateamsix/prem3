import pytest

from app.data_foundation.contracts import FoundationApproval
from app.data_foundation.enums import FoundationPlanSection, PlanActionKind
from app.data_foundation.provisioning.executor import execute_foundation_plan
from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source


def test_dataset_create_is_idempotent_and_never_creates_project(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    first = service.compile_foundation_plan(df_context)
    service.approve_plan(df_context, plan_id=first.plan_id)
    service.execute_plan(df_context, plan_id=first.plan_id)
    second = service.compile_foundation_plan(df_context)
    dataset_actions = [item for item in second.actions if item.resource_type == "dataset"]
    assert dataset_actions[0].action_kind is PlanActionKind.REUSE
    project_actions = [item for item in second.actions if item.resource_type == "gcp_project"]
    assert all(item.action_kind is PlanActionKind.REUSE for item in project_actions)


def test_stale_approval_fails_closed(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    plan = service.compile_foundation_plan(df_context, include_drive=True)
    stale = FoundationApproval(
        approval_id="dfapr_stale000000000001",
        plan_id=plan.plan_id,
        plan_fingerprint="not-the-plan",
        tenant_id=df_context.tenant_id,
        workspace_id=df_context.workspace_id,
        approved_sections=tuple(FoundationPlanSection),
        approved_by="user-a",
        approved_at=plan.created_at,
    )
    with pytest.raises(PermissionError, match="not bound"):
        execute_foundation_plan(
            context=df_context,
            warehouse=service.warehouse,
            plan=plan,
            approval=stale,
        )


def test_approval_not_reusable_across_workspace(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    plan = service.compile_foundation_plan(df_context)
    approval = FoundationApproval(
        approval_id="dfapr_other00000000001",
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        tenant_id=df_context.tenant_id,
        workspace_id="wsp_other000000000001",
        approved_sections=tuple(FoundationPlanSection),
        approved_by="user-a",
        approved_at=plan.created_at,
    )
    with pytest.raises(PermissionError, match="across workspace"):
        execute_foundation_plan(
            context=df_context,
            warehouse=service.warehouse,
            plan=plan,
            approval=approval,
        )


def test_foundation_plan_covers_five_domains_and_will_not_modify(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    plan = service.compile_foundation_plan(df_context, include_drive=True)
    assert set(plan.domains) == set(FoundationPlanSection)
    kinds = {item.action_kind for item in plan.actions}
    assert PlanActionKind.REUSE in kinds
    assert PlanActionKind.CREATE in kinds
    assert "customer GCP project identity" in plan.will_not_modify
    assert "raw Drive files" in plan.will_not_modify
    assert any("bigquery.datasets.create" in item for item in plan.permission_preview)
    assert any(item.dependencies for item in plan.actions)


def test_partial_approval_skips_unapproved_sections_and_dependencies(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    plan = service.compile_foundation_plan(df_context)
    service.approve_plan(
        df_context, plan_id=plan.plan_id, sections=(FoundationPlanSection.INFRASTRUCTURE,)
    )
    run = service.execute_plan(df_context, plan_id=plan.plan_id)
    applied = [step for step in run.steps if step.status.value == "APPLIED"]
    previewed = [step for step in run.steps if "not approved" in step.detail or "dependencies" in step.detail]
    assert applied
    assert previewed
    assert service.warehouse.get_table("acme_analytics.prem3_modeling.canonical_media") is None


def test_material_plan_change_requires_reapproval(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    first = service.compile_foundation_plan(df_context)
    service.approve_plan(df_context, plan_id=first.plan_id)
    service.execute_plan(df_context, plan_id=first.plan_id)
    second = service.compile_foundation_plan(df_context)
    assert second.fingerprint != first.fingerprint
    with pytest.raises(PermissionError, match="reapproval"):
        service.execute_plan(df_context, plan_id=second.plan_id)
