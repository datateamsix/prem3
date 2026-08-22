"""Execute an approved Foundation Plan inside the bound customer project."""

from __future__ import annotations

import pandas as pd

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import (
    FoundationApproval,
    FoundationPlan,
    ProvisioningRun,
    ProvisioningStep,
)
from app.data_foundation.enums import ExecutionStatus, PlanActionKind
from app.data_foundation.ids import new_run_id
from app.data_foundation.warehouse import FoundationWarehouse, WarehouseTable


def execute_foundation_plan(
    *,
    context: DataFoundationContext,
    warehouse: FoundationWarehouse,
    plan: FoundationPlan,
    approval: FoundationApproval,
) -> ProvisioningRun:
    context.require_provisioning_ready()
    if approval.superseded:
        raise PermissionError("Stale foundation approval cannot execute.")
    if approval.plan_fingerprint != plan.fingerprint or approval.plan_id != plan.plan_id:
        raise PermissionError("Approval is not bound to this immutable plan.")
    if approval.tenant_id != context.tenant_id or approval.workspace_id != context.workspace_id:
        raise PermissionError("Approval cannot be reused across workspace or tenant.")
    steps: list[ProvisioningStep] = []
    approved_sections = set(approval.approved_sections)
    completed_targets: set[str] = set()
    for action in plan.actions:
        if action.section not in approved_sections:
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.PREVIEWED,
                    detail="Section not approved.",
                )
            )
            continue
        unmet = [
            dep
            for dep in action.dependencies
            if dep not in completed_targets
            and dep not in warehouse.datasets
            and warehouse.get_table(dep) is None
        ]
        if unmet:
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.PREVIEWED,
                    detail=f"Waiting on dependencies: {', '.join(unmet)}",
                )
            )
            continue
        if action.action_kind is PlanActionKind.CUSTOMER_MANAGED:
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.PREVIEWED,
                    detail="Customer-managed prerequisite remains outside PreM3.",
                )
            )
            continue
        if action.resource_type == "gcp_project":
            if action.action_kind is not PlanActionKind.REUSE:
                raise PermissionError("PreM3 must not create a GCP project.")
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.APPLIED,
                    detail="Reused customer project",
                )
            )
            completed_targets.add(action.target)
            continue
        if action.resource_type == "dataset":
            project_id, dataset_id = action.target.split(".", 1)
            context.authorize_project(project_id)
            warehouse.create_dataset(project_id=project_id, dataset_id=dataset_id)
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.APPLIED,
                    detail="Dataset verified",
                )
            )
            completed_targets.add(action.target)
            continue
        if action.resource_type == "table":
            project_id, dataset_id, table_id = action.target.split(".", 2)
            context.authorize_project(project_id)
            existing = warehouse.get_table(action.target)
            if existing is None:
                warehouse.write_foundation_table(
                    WarehouseTable(
                        project_id=project_id,
                        dataset_id=dataset_id,
                        table_id=table_id,
                        frame=pd.DataFrame(),
                        labels={"prem3": "foundation"},
                    )
                )
            steps.append(
                ProvisioningStep(
                    name=action.target,
                    status=ExecutionStatus.APPLIED,
                    detail="Table verified",
                )
            )
            completed_targets.add(action.target)
    return ProvisioningRun(
        run_id=new_run_id(),
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        steps=tuple(steps),
        status=ExecutionStatus.APPLIED,
    )
