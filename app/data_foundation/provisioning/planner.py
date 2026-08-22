"""Compile an immutable Foundation Plan."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import FoundationPlan, FoundationPlanAction
from app.data_foundation.enums import FoundationPlanSection, PlanActionKind
from app.data_foundation.ids import new_plan_id
from app.data_foundation.plan_fingerprint import fingerprint_payload
from app.data_foundation.warehouse import FoundationWarehouse


def compile_foundation_plan(
    *,
    context: DataFoundationContext,
    warehouse: FoundationWarehouse,
    source_count: int,
    include_drive: bool,
    dv360_prerequisite: bool = False,
) -> FoundationPlan:
    if context.destination_project_id is None:
        raise PermissionError("An approved customer project is required.")
    project = context.destination_project_id
    dataset = f"{project}.prem3_modeling"
    existing = warehouse.datasets.get(dataset)
    dataset_kind = PlanActionKind.REUSE if existing else PlanActionKind.CREATE
    actions = [
        FoundationPlanAction(
            action_kind=dataset_kind,
            section=FoundationPlanSection.INFRASTRUCTURE,
            resource_type="dataset",
            target=dataset,
            reason="Governed measurement home",
            permission_requirements=("bigquery.datasets.create",),
            validation_method="read_back_dataset",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.REUSE,
            section=FoundationPlanSection.INFRASTRUCTURE,
            resource_type="gcp_project",
            target=project,
            reason="Customer project is never created by PreM3",
            validation_method="identity",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.CREATE,
            section=FoundationPlanSection.CANONICAL_ASSETS,
            resource_type="table",
            target=f"{dataset}.canonical_kpi",
            reason="Canonical KPI layer",
            dependencies=(dataset,),
            validation_method="read_back_table",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.CREATE,
            section=FoundationPlanSection.CANONICAL_ASSETS,
            resource_type="table",
            target=f"{dataset}.canonical_media",
            reason="Canonical media layer",
            dependencies=(dataset,),
            validation_method="read_back_table",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.CREATE,
            section=FoundationPlanSection.GOVERNANCE_AND_OBSERVABILITY,
            resource_type="table",
            target=f"{dataset}.source_registry",
            reason="Source contract registry",
            dependencies=(dataset,),
            validation_method="read_back_table",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.CREATE,
            section=FoundationPlanSection.GOVERNANCE_AND_OBSERVABILITY,
            resource_type="table",
            target=f"{dataset}.quality_findings",
            reason="Durable quality findings",
            dependencies=(dataset,),
            validation_method="read_back_table",
        ),
        FoundationPlanAction(
            action_kind=PlanActionKind.CREATE,
            section=FoundationPlanSection.QUALITY_AND_TRANSFORMATIONS,
            resource_type="table",
            target=f"{dataset}.transformation_receipts",
            reason="Transform proof",
            dependencies=(dataset,),
            validation_method="read_back_table",
        ),
    ]
    if include_drive:
        actions.append(
            FoundationPlanAction(
                action_kind=PlanActionKind.CREATE,
                section=FoundationPlanSection.SOURCES_AND_TRANSFERS,
                resource_type="table",
                target=f"{dataset}.stg_drive_imports",
                reason="Drive file materialization",
                dependencies=(dataset,),
                validation_method="read_back_table",
            )
        )
    if dv360_prerequisite:
        actions.append(
            FoundationPlanAction(
                action_kind=PlanActionKind.CUSTOMER_MANAGED,
                section=FoundationPlanSection.SOURCES_AND_TRANSFERS,
                resource_type="dtv2_bucket",
                target="dv360.dtv2",
                reason="DTV2 must be provisioned outside PreM3",
                validation_method="prerequisite",
            )
        )
    del source_count
    will_not_modify = (
        "customer GCP project identity",
        "customer source tables",
        "raw Drive files",
        "BigQuery datasets outside prem3_modeling",
    )
    permission_preview = (
        "bigquery.datasets.create for prem3_modeling when missing",
        "bigquery.tables.create on prem3_modeling",
        "bigquery.tables.updateData on prem3_modeling only",
    )
    if include_drive:
        permission_preview = permission_preview + ("drive.files.readonly inside the bound root",)
    payload = [item.model_dump(mode="json") for item in actions]
    payload.append({"will_not_modify": list(will_not_modify), "permission_preview": list(permission_preview)})
    return FoundationPlan(
        plan_id=new_plan_id(),
        version=1,
        tenant_id=context.tenant_id,
        workspace_id=context.workspace_id,
        fingerprint=fingerprint_payload(payload),
        actions=tuple(actions),
        created_at=datetime.now(UTC),
        will_not_modify=will_not_modify,
        permission_preview=permission_preview,
        domains=tuple(FoundationPlanSection),
    )
