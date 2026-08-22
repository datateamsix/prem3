"""Workspace-scoped Data Foundation service. Deterministic owners first."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from app.core.tenancy import require_tenant
from app.data_foundation.alignment import assess_alignment
from app.data_foundation.bigquery.discovery import candidates_for_tables, discover_tables
from app.data_foundation.context import DataFoundationContext
from app.business_iq.contracts import BusinessProfileSnapshot as IqSnapshot
from app.data_foundation.contracts import (
    REGISTRY_CONTRACT_VERSION,
    BusinessProfileSnapshot,
    CanonicalPreview,
    ConnectionView,
    DataFoundationOverview,
    DataQualityReceipt,
    DiscoveryHints,
    DriveImportReceipt,
    EvidenceRequirementSet,
    FoundationApproval,
    FoundationPlanSection,
    FoundationProvisioningReceipt,
    MeasurementCycle,
    QueryBudgetPolicy,
    SourceAssessmentReceipt,
    SourceBinding,
    SourceContinuityPlan,
    SourceContract,
    SourceFoundationReceipt,
    TransformationReceipt,
    UserDecision,
)
from app.data_foundation.coverage.engine import assess_coverage
from app.data_foundation.drive.grouping import group_file_series
from app.data_foundation.intelligence_brief import compile_data_intelligence_brief
from app.data_foundation.discovery.candidates import build_inventory, candidate_from_drive_file
from app.data_foundation.discovery.physical import physical_from_drive_files, physical_from_table
from app.data_foundation.discovery.requirements import compile_evidence_requirements
from app.data_foundation.discovery.scope import infer_source_scope
from app.data_foundation.discovery.snapshot_adapter import (
    channel_effective_dates,
    snapshot_from_business_iq,
)
from app.data_foundation.drive.files import register_file
from app.data_foundation.drive.ingestion import parse_drive_payload
from app.data_foundation.drive.root import ensure_layout
from app.data_foundation.enums import (
    CoverageView,
    CutoffOrigin,
    CycleCadence,
    DataFoundationReadyStatus,
    ExecutionStatus,
    LocationType,
    PreviewMode,
    SourceFoundationStatus,
    TargetWindowStatus,
    TransformId,
)
from app.data_foundation.ids import new_approval_id, new_cycle_id, new_receipt_id, new_source_id
from app.data_foundation.preview.safe import compile_source_preview, preview_from_output
from app.data_foundation.provisioning.executor import execute_foundation_plan
from app.data_foundation.provisioning.planner import compile_foundation_plan
from app.data_foundation.quality.engine import assess_frame, overview_from_assessment
from app.data_foundation.readiness import evaluate_data_foundation_ready, evaluate_source_foundation
from app.data_foundation.store import DataFoundationStore
from app.data_foundation.transformation.executor import apply_actions
from app.data_foundation.transformation.planner import compile_transformation_plan
from app.data_foundation.transformation.preview import preview_plan
from app.data_foundation.transformation.validator import validate_transform_output
from app.data_foundation.warehouse import FoundationWarehouse, WarehouseTable
from app.registry.loader import load_registry
from app.tools.fingerprints import content_fingerprint, schema_signature


class DataFoundationService:
    def __init__(
        self,
        *,
        store: DataFoundationStore,
        warehouse: FoundationWarehouse,
        live_cloud_proof: str = "LIVE_CLOUD_PROOF_NOT_RUN",
        bigquery_client: object | None = None,
        drive_client: object | None = None,
    ) -> None:
        self.store = store
        self.warehouse = warehouse
        self.live_cloud_proof = live_cloud_proof
        self.bigquery_client = bigquery_client
        self.drive_client = drive_client
        self.frames: dict[str, pd.DataFrame] = {}
        self.drive_payloads: dict[str, bytes] = {}
        self.allowed_exceptions: set[str] = set()
        self.governance_ready: dict[str, bool] = {}

    def get_overview(self, context: DataFoundationContext) -> DataFoundationOverview:
        reqs = self.store.get_requirements(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        inventory = self.store.get_inventory(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        ready = 0
        for binding in self.store.list_bindings(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        ):
            receipt = self.store.get_current_source_receipt(binding.source_id)
            if receipt and receipt.status_code is SourceFoundationStatus.FOUNDATION_SOURCE_READY:
                ready += 1
        env = self.store.get_current_foundation_receipt(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        return DataFoundationOverview(
            workspace_id=context.workspace_id,
            phase=self._phase(context, reqs, inventory, env),
            connections=(
                ConnectionView(
                    plane="BigQuery",
                    required=True,
                    lifecycle=context.bq_lifecycle,
                    connection_id=context.google_connection_id,
                    binding_summary=context.destination_project_id,
                ),
                ConnectionView(
                    plane="Google Drive",
                    required=False,
                    lifecycle=context.drive_lifecycle,
                    binding_summary=context.drive_root_folder_id,
                ),
            ),
            requirement_count=len(reqs.requirements) if reqs else 0,
            candidate_count=len(inventory.candidates) if inventory else 0,
            source_ready_count=ready,
            foundation_ready=bool(
                env and env.status_code is DataFoundationReadyStatus.DATA_FOUNDATION_READY
            ),
            live_cloud_proof=self.live_cloud_proof,
        )

    def load_business_snapshot(
        self, context: DataFoundationContext, snapshot: BusinessProfileSnapshot
    ) -> EvidenceRequirementSet:
        self._authorize(context)
        if snapshot.tenant_id != context.tenant_id or snapshot.workspace_id != context.workspace_id:
            raise PermissionError("Business snapshot tenant/workspace mismatch.")
        compiled = compile_evidence_requirements(snapshot)
        return self.store.put_requirements(compiled)

    def load_business_iq_snapshot(
        self,
        context: DataFoundationContext,
        snapshot: IqSnapshot,
        *,
        ready: bool,
    ) -> EvidenceRequirementSet:
        if not ready:
            raise ValueError("BUSINESS_CONTEXT_READY is required before Data Foundation discovery.")
        return self.load_business_snapshot(
            context, snapshot_from_business_iq(snapshot, business_context_ready=ready)
        )

    def get_evidence_requirements(self, context: DataFoundationContext) -> EvidenceRequirementSet:
        self._authorize(context)
        found = self.store.get_requirements(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        if found is None:
            raise KeyError("Evidence requirements have not been compiled.")
        return found

    def set_discovery_hints(
        self, context: DataFoundationContext, hints: DiscoveryHints
    ) -> DiscoveryHints:
        self._authorize(context)
        if hints.tenant_id != context.tenant_id or hints.workspace_id != context.workspace_id:
            raise PermissionError("Discovery hints tenant/workspace mismatch.")
        return self.store.put_hints(hints)

    def discover(
        self, context: DataFoundationContext, policy: QueryBudgetPolicy | None = None
    ) -> object:
        self._authorize(context)
        context.require_discovery_ready()
        reqs = self.get_evidence_requirements(context)
        discovery_hints = self.store.get_hints(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        tables = discover_tables(
            self.warehouse,
            context=context,
            policy=policy or QueryBudgetPolicy(),
            hints=discovery_hints,
        )
        requirement_hints = {item.concept: item for item in reqs.requirements}
        candidates = list(
            candidates_for_tables(
                tables,
                requirement_hints,
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
            )
        )
        for record in self.store.list_files(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        ):
            if (
                context.drive_root_folder_id
                and record.parent_folder_id != context.drive_root_folder_id
            ):
                continue
            if discovery_hints and discovery_hints.drive_sources_or_paths_to_prioritize:
                needle = record.original_name.lower()
                if not any(
                    token.lower() in needle
                    for token in discovery_hints.drive_sources_or_paths_to_prioritize
                ):
                    continue
            hint = next(
                (
                    item
                    for item in reqs.requirements
                    if item.concept.lower() in record.original_name.lower()
                ),
                None,
            )
            candidates.append(
                candidate_from_drive_file(
                    tenant_id=context.tenant_id,
                    workspace_id=context.workspace_id,
                    file_id=record.drive_file_id,
                    name=record.original_name,
                    parent_folder_id=record.parent_folder_id,
                    requirement=hint,
                )
            )
        for candidate in candidates:
            self.store.put_candidate(candidate)
        inventory = build_inventory(
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            requirements=reqs.requirements,
            candidates=tuple(candidates),
        )
        return self.store.put_inventory(inventory)

    def list_source_candidates(self, context: DataFoundationContext) -> object:
        inventory = self.store.get_inventory(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        if inventory is None:
            raise KeyError("Discovery has not run.")
        return inventory

    def bind_source(
        self,
        context: DataFoundationContext,
        *,
        candidate_id: str,
        contract: SourceContract,
        requirement_id: str | None = None,
        governance_import_ready: bool = False,
    ) -> SourceBinding:
        self._authorize(context)
        candidate = self.store.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError("Unknown candidate.")
        if (
            candidate.tenant_id != context.tenant_id
            or candidate.workspace_id != context.workspace_id
        ):
            raise PermissionError("Cross-tenant source access is denied.")
        if candidate.resource.project_id:
            context.authorize_project(candidate.resource.project_id)
        if candidate.resource.drive_folder_id and context.drive_root_folder_id:
            if candidate.resource.drive_folder_id != context.drive_root_folder_id:
                raise PermissionError("Drive folder is outside the bound root.")
        source_id = new_source_id()
        now = datetime.now(UTC)
        binding = SourceBinding(
            source_id=source_id,
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            requirement_id=requirement_id or candidate.evidence_requirement_id,
            provider_id=candidate.provider_candidate,
            location_type=candidate.location_type,
            resource=candidate.resource,
            contract=contract,
            lifecycle_state="BOUND",
            governance_import_ready=governance_import_ready,
            created_at=now,
            updated_at=now,
        )
        self.governance_ready[source_id] = governance_import_ready
        fqdn = candidate.resource.logical_path
        if fqdn and self.warehouse.get_table(fqdn):
            self.frames[source_id] = self.warehouse.read_table(fqdn)
        return self.store.put_binding(binding)

    def register_drive_file(
        self,
        context: DataFoundationContext,
        *,
        drive_file_id: str,
        original_name: str,
        parent_folder_id: str,
        payload: bytes,
        mime_type: str,
        source_slug: str | None = None,
    ) -> object:
        self._authorize(context)
        if context.drive_root_folder_id != parent_folder_id:
            raise PermissionError("Drive access outside the bound root is rejected.")
        existing = self.store.get_file(drive_file_id)
        record = register_file(
            context=context,
            drive_file_id=drive_file_id,
            original_name=original_name,
            parent_folder_id=parent_folder_id,
            payload=payload,
            mime_type=mime_type,
            source_slug=source_slug,
        )
        if existing and existing.file_fingerprint == record.file_fingerprint:
            return existing
        self.drive_payloads[drive_file_id] = payload
        return self.store.put_file(record)

    def ensure_drive_layout(self, context: DataFoundationContext) -> object:
        existing = self.store.get_layout(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        return self.store.put_layout(ensure_layout(context=context, existing=existing))

    def get_drive_layout(self, context: DataFoundationContext) -> object:
        self._authorize(context)
        found = self.store.get_layout(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        if found is None:
            raise KeyError("Drive layout has not been created.")
        return found

    def assess_source(self, context: DataFoundationContext, source_id: str) -> object:
        binding = self._binding(context, source_id)
        frame = self._frame(binding)
        assessment = assess_frame(
            frame,
            source_id=source_id,
            contract=binding.contract,
            access_works=True,
            authorization=context.bq_lifecycle
            if binding.location_type is LocationType.BIGQUERY
            else context.drive_lifecycle,
            freshness_known=True,
            latest_expected=None,
            latest_observed=self._latest_date(frame, binding.contract.date_field),
            registry_version=load_registry().version,
        )
        self.store.put_assessment(assessment)
        path = binding.resource.logical_path
        table = self.warehouse.get_table(path) if path else None
        if table is not None:
            self.store.put_physical(source_id, physical_from_table(table))
        elif binding.location_type is LocationType.GOOGLE_DRIVE:
            files = [
                item
                for item in self.store.list_files(
                    tenant_id=context.tenant_id, workspace_id=context.workspace_id
                )
                if item.drive_file_id == binding.resource.drive_file_id
            ]
            self.store.put_physical(
                source_id, physical_from_drive_files(files, row_count=len(frame))
            )
        reqs = self.store.get_requirements(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        markets = ()
        if reqs:
            markets = next((item.market_scope for item in reqs.requirements if item.market_scope), ())
        self.store.put_scope(
            source_id,
            infer_source_scope(
                field_names=tuple(str(column) for column in frame.columns),
                geo_field=binding.contract.geo_field,
                markets=markets,
                filename=binding.resource.table_id or binding.resource.drive_file_id,
            ),
        )
        self.store.put_assessment_receipt(
            SourceAssessmentReceipt(
                receipt_id=new_receipt_id(),
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
                source_ids=(source_id,),
                executed_at=datetime.now(UTC),
                executed_by=context.actor_id,
                status=assessment.overall_status.value,
                assessment_status=assessment.overall_status,
            )
        )
        return assessment

    def get_source_assessment(self, context: DataFoundationContext, source_id: str) -> object:
        self._binding(context, source_id)
        found = self.store.get_assessment(source_id)
        if found is None:
            raise KeyError("Source has not been assessed.")
        return found

    def get_quality_overview(self, context: DataFoundationContext, source_id: str) -> object:
        return overview_from_assessment(self.get_source_assessment(context, source_id))

    def get_cross_source_alignment(self, context: DataFoundationContext) -> object:
        self._authorize(context)
        bindings = self.store.list_bindings(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        alignment = assess_alignment(workspace_id=context.workspace_id, bindings=bindings)
        return self.store.put_alignment(alignment)

    def compile_transformation_plan(
        self,
        context: DataFoundationContext,
        *,
        source_id: str,
        action_ids: list[TransformId],
        parameters: dict[str, dict] | None = None,
    ) -> object:
        binding = self._binding(context, source_id)
        frame = self._frame(binding)
        fingerprint = self._content_fingerprint(frame, binding)
        target = f"{context.destination_project_id}.prem3_modeling.stg_{binding.source_id}"
        plan = compile_transformation_plan(
            source_id=source_id,
            source_fingerprint=fingerprint,
            registry_version=REGISTRY_CONTRACT_VERSION,
            action_ids=action_ids,
            output_target=target,
            source_grain=binding.contract.grain,
            target_grain=binding.contract.grain,
            parameters=parameters,
        )
        return self.store.put_transformation_plan(plan)

    def get_transformation_preview(self, context: DataFoundationContext, plan_id: str) -> object:
        plan = self.store.get_transformation_plan(plan_id)
        if plan is None:
            raise KeyError("Unknown transformation plan.")
        binding = self._binding(context, plan.source_id)
        preview = preview_plan(self._frame(binding), plan)
        return self.store.put_preview(preview)

    def resolve_user_decision(
        self,
        context: DataFoundationContext,
        *,
        source_id: str,
        kind: str,
        value: str,
    ) -> UserDecision:
        self._binding(context, source_id)
        decision = UserDecision(
            decision_id=new_receipt_id(),
            source_id=source_id,
            kind=kind,
            value=value,
            recorded_at=datetime.now(UTC),
        )
        return self.store.put_decision(decision)

    def execute_transformation(
        self,
        context: DataFoundationContext,
        *,
        transformation_plan_id: str,
        action_ids: list[TransformId] | None = None,
    ) -> TransformationReceipt:
        self._authorize(context)
        context.require_provisioning_ready()
        plan = self.store.get_transformation_plan(transformation_plan_id)
        if plan is None:
            raise KeyError("Unknown transformation plan.")
        if action_ids and tuple(item.value for item in action_ids) != tuple(
            item.action_id.value for item in plan.actions
        ):
            raise PermissionError("Executor accepts the pinned action set only.")
        binding = self._binding(context, plan.source_id)
        frame = self._frame(binding)
        current = self._content_fingerprint(frame, binding)
        if current != plan.source_fingerprint:
            raise PermissionError("Source fingerprint no longer matches the approved plan.")
        prior = self.store.get_transform_receipt(
            source_id=plan.source_id,
            plan_id=plan.plan_id,
            source_fingerprint=plan.source_fingerprint,
        )
        if prior is not None:
            return prior
        if plan.requires_approval:
            approval = self.store.get_approval_for_plan(plan.plan_id)
            if approval is None or approval.plan_fingerprint != plan.fingerprint:
                raise PermissionError("Unapproved plan cannot execute.")
        decisions = {item.kind: item.value for item in self.store.list_decisions(plan.source_id)}
        output = apply_actions(frame, plan, preview=False, user_decisions=decisions)
        proof = validate_transform_output(source=frame, output=output, plan=plan)
        dest = plan.output_target
        project_id, dataset_id, table_id = dest.split(".", 2)
        context.authorize_project(project_id)
        if dataset_id != "prem3_modeling":
            raise PermissionError("Transform destination must be prem3_modeling.")
        source_path = binding.resource.logical_path or ""
        if dest == source_path:
            raise PermissionError("Destination cannot equal the raw source.")
        self.warehouse.refuse_overwrite_source(dest)
        self.warehouse.write_foundation_table(
            WarehouseTable(
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
                frame=output,
            )
        )
        self.frames[f"{plan.source_id}:output"] = output
        receipt = TransformationReceipt(
            receipt_id=new_receipt_id(),
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            source_ids=(plan.source_id,),
            plan_id=plan.plan_id,
            plan_version=plan.version,
            input_fingerprints={"source": plan.source_fingerprint},
            output_fingerprints={"output": str(proof["content"])},
            executed_at=datetime.now(UTC),
            executed_by=context.actor_id,
            status="APPLIED",
            applied_actions=tuple(item.action_id.value for item in plan.actions),
            input_rows=int(len(frame)),
            output_rows=int(len(output)),
            source_mutated=False,
        )
        self.store.put_quality_receipt = getattr(self.store, "put_quality_receipt", None)
        return self.store.put_transform_receipt(receipt)

    def materialize_drive_source(
        self,
        context: DataFoundationContext,
        *,
        source_id: str,
        drive_file_id: str,
        sheet_name: str | None = None,
    ) -> DriveImportReceipt:
        binding = self._binding(context, source_id)
        record = self.store.get_file(drive_file_id)
        if record is None:
            raise KeyError("Drive file is not registered.")
        payload = self.drive_payloads[drive_file_id]
        frame = parse_drive_payload(record=record, payload=payload, sheet_name=sheet_name)
        self.frames[source_id] = frame
        dest = f"{context.destination_project_id}.prem3_modeling.stg_{source_id}"
        project_id, dataset_id, table_id = dest.split(".", 2)
        self.warehouse.write_foundation_table(
            WarehouseTable(
                project_id=project_id, dataset_id=dataset_id, table_id=table_id, frame=frame
            )
        )
        receipt = DriveImportReceipt(
            receipt_id=new_receipt_id(),
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            source_ids=(source_id,),
            executed_at=datetime.now(UTC),
            executed_by=context.actor_id,
            status="APPLIED",
            files_evaluated=1,
            files_accepted=1,
            files_rejected=0,
            destination=dest,
            raw_files_modified=False,
            input_fingerprints={"file": record.file_fingerprint},
        )
        del binding
        return self.store.put_drive_import_receipt(receipt)

    def compile_foundation_plan(
        self, context: DataFoundationContext, *, include_drive: bool = False, dv360: bool = False
    ) -> object:
        self._authorize(context)
        bindings = self.store.list_bindings(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        plan = compile_foundation_plan(
            context=context,
            warehouse=self.warehouse,
            source_count=len(bindings),
            include_drive=include_drive,
            dv360_prerequisite=dv360,
        )
        return self.store.put_foundation_plan(plan)

    def approve_plan(
        self,
        context: DataFoundationContext,
        *,
        plan_id: str,
        sections: tuple[FoundationPlanSection, ...] | None = None,
    ) -> FoundationApproval:
        self._authorize(context)
        plan = self.store.get_foundation_plan(plan_id) or self.store.get_transformation_plan(
            plan_id
        )
        if plan is None:
            raise KeyError("Unknown plan.")
        fingerprint = plan.fingerprint
        if getattr(plan, "tenant_id", context.tenant_id) != context.tenant_id:
            raise PermissionError("Plan tenant mismatch.")
        approval = FoundationApproval(
            approval_id=new_approval_id(),
            plan_id=plan_id,
            plan_fingerprint=fingerprint,
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            approved_sections=sections or tuple(FoundationPlanSection),
            approved_by=context.actor_id,
            approved_at=datetime.now(UTC),
        )
        return self.store.put_approval(approval)

    def execute_plan(self, context: DataFoundationContext, *, plan_id: str) -> object:
        foundation = self.store.get_foundation_plan(plan_id)
        if foundation is not None:
            self.require_material_reapproval(context, plan_id)
            approval = self.store.get_approval_for_plan(plan_id)
            if approval is None:
                raise PermissionError("Unapproved plan cannot execute.")
            run = execute_foundation_plan(
                context=context,
                warehouse=self.warehouse,
                plan=foundation,
                approval=approval,
            )
            self.store.put_provisioning_run(run)
            self.store.put_provisioning_receipt(
                FoundationProvisioningReceipt(
                    receipt_id=new_receipt_id(),
                    tenant_id=context.tenant_id,
                    workspace_id=context.workspace_id,
                    source_ids=tuple(
                        item.source_id
                        for item in self.store.list_bindings(
                            tenant_id=context.tenant_id, workspace_id=context.workspace_id
                        )
                    ),
                    plan_id=plan_id,
                    executed_at=datetime.now(UTC),
                    executed_by=context.actor_id,
                    status=run.status.value,
                    created=tuple(
                        step.name for step in run.steps if step.status is ExecutionStatus.APPLIED
                    ),
                    reused=tuple(
                        action.target
                        for action in foundation.actions
                        if action.action_kind.value == "REUSE"
                    ),
                    untouched=("customer source tables",),
                    remaining=tuple(
                        action.target
                        for action in foundation.actions
                        if action.action_kind.value == "CUSTOMER_MANAGED"
                    ),
                )
            )
            return run
        return self.execute_transformation(context, transformation_plan_id=plan_id)

    def evaluate_source_ready(
        self, context: DataFoundationContext, source_id: str
    ) -> SourceFoundationReceipt:
        binding = self._binding(context, source_id)
        assessment = self.get_source_assessment(context, source_id)
        receipt = evaluate_source_foundation(
            context=context,
            binding=binding,
            assessment=assessment,
            governance_import_ready=self.governance_ready.get(source_id, False),
            transform_receipt=next(
                (
                    item
                    for item in self.store.list_receipts(
                        tenant_id=context.tenant_id, workspace_id=context.workspace_id
                    )
                    if isinstance(item, TransformationReceipt) and source_id in item.source_ids
                ),
                None,
            ),
            currency_known=bool(binding.contract.currency),
            timezone_known=bool(binding.contract.timezone),
        )
        return self.store.put_source_receipt(receipt)

    def evaluate_data_foundation_ready(self, context: DataFoundationContext) -> object:
        self._authorize(context)
        bindings = [
            item
            for item in self.store.list_bindings(
                tenant_id=context.tenant_id, workspace_id=context.workspace_id
            )
            if item.lifecycle_state != "RETIRED"
        ]
        receipts = [
            self.store.get_current_source_receipt(item.source_id)
            for item in bindings
            if self.store.get_current_source_receipt(item.source_id) is not None
        ]
        provisioning = [
            item
            for item in self.store.list_receipts(
                tenant_id=context.tenant_id, workspace_id=context.workspace_id
            )
            if isinstance(item, FoundationProvisioningReceipt)
        ]
        approval = None
        for plan in getattr(self.store, "foundation_plans", {}).values():
            if plan.workspace_id == context.workspace_id:
                approval = self.store.get_approval_for_plan(plan.plan_id)
        env = evaluate_data_foundation_ready(
            context=context,
            warehouse=self.warehouse,
            source_receipts=[item for item in receipts if item is not None],
            required_source_ids=[item.source_id for item in bindings],
            allowed_exceptions=self.allowed_exceptions,
            foundation_receipt_exists=bool(provisioning),
            approval_valid=approval is not None and not approval.superseded,
        )
        return self.store.put_foundation_receipt(env)

    def reevaluate_health(self, context: DataFoundationContext, source_id: str) -> object:
        assessment = self.assess_source(context, source_id)
        prior = self.store.get_current_source_receipt(source_id)
        current = self.evaluate_source_ready(context, source_id)
        if prior is not None and prior.receipt_id != current.receipt_id:
            # Historical receipts remain in the store list.
            pass
        self.evaluate_data_foundation_ready(context)
        return assessment

    def get_receipts(self, context: DataFoundationContext) -> list[object]:
        self._authorize(context)
        return self.store.list_receipts(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )

    def list_file_series(self, context: DataFoundationContext) -> list[object]:
        self._authorize(context)
        files = self.store.list_files(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        return group_file_series(files)

    def compile_intelligence_brief(self, context: DataFoundationContext) -> object:
        self._authorize(context)
        assessments = [
            self.store.get_assessment(item.source_id)
            for item in self.store.list_bindings(
                tenant_id=context.tenant_id, workspace_id=context.workspace_id
            )
        ]
        coverage = None
        for cycle in self.store.list_cycles(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        ):
            coverage = self.store.get_coverage(cycle.cycle_id) or coverage
        brief = compile_data_intelligence_brief(
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            assessments=[item for item in assessments if item is not None],
            coverage=coverage,
        )
        return self.store.put_intelligence_brief(brief)

    def get_intelligence_brief(self, context: DataFoundationContext) -> object:
        self._authorize(context)
        found = self.store.get_intelligence_brief(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        if found is None:
            raise KeyError("Data Intelligence Brief has not been generated.")
        return found

    def retire_source(self, context: DataFoundationContext, source_id: str) -> SourceBinding:
        binding = self._binding(context, source_id)
        retired = binding.model_copy(
            update={"lifecycle_state": "RETIRED", "updated_at": datetime.now(UTC)}
        )
        stored = self.store.put_binding(retired)
        if self.store.get_assessment(source_id) is not None:
            self.reevaluate_health(context, source_id)
        return stored

    def replace_source(
        self,
        context: DataFoundationContext,
        *,
        source_id: str,
        candidate_id: str,
        contract: SourceContract,
        governance_import_ready: bool = False,
    ) -> SourceBinding:
        prior = self.retire_source(context, source_id)
        replacement = self.bind_source(
            context,
            candidate_id=candidate_id,
            contract=contract,
            requirement_id=prior.requirement_id,
            governance_import_ready=governance_import_ready,
        )
        self.put_transition(
            context,
            SourceContinuityPlan(
                historical_source_id=prior.source_id,
                ongoing_source_id=replacement.source_id,
                cutoff=datetime.now(UTC).strftime("%Y-%m-%d"),
                overlap_handling="REVIEW",
                reconciliation_required=True,
                canonical_precedence="ongoing_after_cutoff",
            ),
        )
        return replacement

    def reauthorize_source(self, context: DataFoundationContext, source_id: str) -> object:
        return self.reevaluate_health(context, source_id)

    def get_source_health(self, context: DataFoundationContext, source_id: str) -> dict[str, object]:
        assessment = self.get_source_assessment(context, source_id)
        receipt = self.store.get_current_source_receipt(source_id)
        return {
            "assessment": assessment,
            "quality_overview": self.get_quality_overview(context, source_id),
            "source_receipt": receipt,
        }

    def require_material_reapproval(self, context: DataFoundationContext, plan_id: str) -> None:
        self._authorize(context)
        plan = self.store.get_foundation_plan(plan_id) or self.store.get_transformation_plan(plan_id)
        if plan is None:
            raise KeyError("Unknown plan.")
        approval = self.store.get_approval_for_plan(plan_id)
        if approval is None or approval.plan_fingerprint != plan.fingerprint or approval.superseded:
            raise PermissionError("Material plan change requires reapproval.")

    def create_cycle(
        self,
        context: DataFoundationContext,
        *,
        name: str,
        cadence: CycleCadence,
        business_profile_snapshot_id: str,
        data_cutoff: str | None = None,
        cutoff_origin: CutoffOrigin | None = None,
        target_window_start: str | None = None,
        target_window_end: str | None = None,
        target_window_status: TargetWindowStatus = TargetWindowStatus.PROVISIONAL,
    ) -> MeasurementCycle:
        self._authorize(context)
        now = datetime.now(UTC)
        cycle = MeasurementCycle(
            cycle_id=new_cycle_id(),
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            name=name,
            cadence=cadence,
            data_cutoff=data_cutoff,
            cutoff_origin=cutoff_origin,
            target_window_start=target_window_start,
            target_window_end=target_window_end,
            target_window_status=target_window_status,
            business_profile_snapshot_id=business_profile_snapshot_id,
            created_at=now,
            updated_at=now,
            created_by=context.actor_id,
        )
        return self.store.put_cycle(cycle)

    def update_cycle(
        self, context: DataFoundationContext, cycle_id: str, **updates: object
    ) -> MeasurementCycle:
        cycle = self.get_cycle(context, cycle_id)
        always_forbidden = {
            "cycle_id",
            "tenant_id",
            "workspace_id",
            "business_profile_snapshot_id",
            "predecessor_cycle_id",
        }
        confirmed_locked = {
            "business_profile_snapshot_id",
            "data_cutoff",
            "cutoff_origin",
            "target_window_start",
            "target_window_end",
            "target_window_status",
        }
        if any(key in always_forbidden for key in updates):
            raise PermissionError("Pinned cycle identity cannot be replaced in place.")
        if cycle.target_window_status is TargetWindowStatus.CONFIRMED_DOWNSTREAM:
            if any(key in confirmed_locked for key in updates):
                raise PermissionError(
                    "CONFIRMED_DOWNSTREAM cycles are reproducible; revise into a new cycle."
                )
        updated = cycle.model_copy(update={**updates, "updated_at": datetime.now(UTC)})
        return self.store.put_cycle(updated)

    def revise_cycle(
        self,
        context: DataFoundationContext,
        cycle_id: str,
        *,
        name: str | None = None,
        business_profile_snapshot_id: str | None = None,
        data_cutoff: str | None = None,
        cutoff_origin: CutoffOrigin | None = None,
        target_window_start: str | None = None,
        target_window_end: str | None = None,
    ) -> MeasurementCycle:
        prior = self.get_cycle(context, cycle_id)
        now = datetime.now(UTC)
        revised = MeasurementCycle(
            cycle_id=new_cycle_id(),
            tenant_id=prior.tenant_id,
            workspace_id=prior.workspace_id,
            name=name or prior.name,
            cadence=prior.cadence,
            data_cutoff=data_cutoff if data_cutoff is not None else prior.data_cutoff,
            cutoff_origin=cutoff_origin if cutoff_origin is not None else prior.cutoff_origin,
            target_window_start=target_window_start
            if target_window_start is not None
            else prior.target_window_start,
            target_window_end=target_window_end
            if target_window_end is not None
            else prior.target_window_end,
            target_window_status=TargetWindowStatus.PROVISIONAL,
            business_profile_snapshot_id=business_profile_snapshot_id
            or prior.business_profile_snapshot_id,
            created_at=now,
            updated_at=now,
            created_by=context.actor_id,
            predecessor_cycle_id=prior.cycle_id,
            revision=prior.revision + 1,
        )
        return self.store.put_cycle(revised)

    def get_cycle(self, context: DataFoundationContext, cycle_id: str) -> MeasurementCycle:
        self._authorize(context)
        found = self.store.get_cycle(cycle_id)
        if found is None or found.tenant_id != context.tenant_id:
            raise KeyError("Measurement cycle not found.")
        return found

    def list_cycles(self, context: DataFoundationContext) -> list[MeasurementCycle]:
        self._authorize(context)
        return self.store.list_cycles(tenant_id=context.tenant_id, workspace_id=context.workspace_id)

    def compute_coverage(
        self,
        context: DataFoundationContext,
        cycle_id: str,
        *,
        view: CoverageView = CoverageView.REQUIRED_EVIDENCE,
        channel_dates: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> object:
        cycle = self.get_cycle(context, cycle_id)
        reqs = self.get_evidence_requirements(context)
        if reqs.snapshot_id != cycle.business_profile_snapshot_id and not reqs.snapshot_id:
            raise PermissionError("Cycle snapshot does not match compiled requirements.")
        bindings = self.store.list_bindings(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        frames: dict[str, pd.DataFrame] = {}
        for item in bindings:
            try:
                frames[item.source_id] = self._frame(item)
            except KeyError:
                continue
        assessment = assess_coverage(
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            cycle=cycle,
            requirements=reqs.requirements,
            bindings=bindings,
            frames=frames,
            channel_dates=channel_dates or {},
            view=view,
            transitions=self.store.list_transitions(workspace_id=context.workspace_id),
        )
        return self.store.put_coverage(assessment)

    def get_coverage(self, context: DataFoundationContext, cycle_id: str) -> object:
        self.get_cycle(context, cycle_id)
        found = self.store.get_coverage(cycle_id)
        if found is None:
            raise KeyError("Coverage has not been computed.")
        return found

    def get_coverage_gap(self, context: DataFoundationContext, cycle_id: str, gap_id: str) -> object:
        coverage = self.get_coverage(context, cycle_id)
        for gap in coverage.gaps:
            if gap.gap_id == gap_id:
                return gap
        raise KeyError("Coverage gap not found.")

    def get_shared_window(self, context: DataFoundationContext, cycle_id: str) -> object:
        return self.get_coverage(context, cycle_id).summary

    def preview_source(self, context: DataFoundationContext, source_id: str) -> object:
        binding = self._binding(context, source_id)
        frame = self._frame(binding)
        preview = compile_source_preview(
            frame,
            source_id=source_id,
            date_field=binding.contract.date_field,
            project_id=binding.resource.project_id,
            dataset_id=binding.resource.dataset_id,
            table_id=binding.resource.table_id,
            contributing_file=binding.resource.drive_file_id,
            original_filename=binding.resource.logical_path,
        )
        return self.store.put_data_preview(preview)

    def get_source_scope(self, context: DataFoundationContext, source_id: str) -> object:
        self._binding(context, source_id)
        found = self.store.get_scope(source_id)
        if found is None:
            raise KeyError("Source scope has not been assessed.")
        return found

    def get_physical_metadata(self, context: DataFoundationContext, source_id: str) -> object:
        self._binding(context, source_id)
        found = self.store.get_physical(source_id)
        if found is None:
            raise KeyError("Physical metadata has not been assessed.")
        return found

    def put_transition(
        self, context: DataFoundationContext, plan: SourceContinuityPlan
    ) -> SourceContinuityPlan:
        self._authorize(context)
        return self.store.put_transition(
            plan.model_copy(update={"workspace_id": context.workspace_id})
        )

    def canonical_preview(self, context: DataFoundationContext) -> CanonicalPreview:
        self._authorize(context)
        project = context.destination_project_id
        if project is None:
            raise PermissionError("Destination project is required.")
        resource = f"{project}.prem3_modeling.canonical_media"
        table = self.warehouse.get_table(resource)
        if table is None:
            raise KeyError("Canonical output is not available.")
        preview = preview_from_output(
            table.frame,
            source_id="canonical_media",
            mode=PreviewMode.CANONICAL_PREVIEW,
            output_resource=resource,
        )
        receipt = self.store.get_current_foundation_receipt(
            tenant_id=context.tenant_id, workspace_id=context.workspace_id
        )
        return self.store.put_canonical_preview(
            CanonicalPreview(
                preview_id=preview.preview_id,
                output_resource=resource,
                actual_row_count=int(len(table.frame)),
                actual_schema=tuple(str(column) for column in table.frame.columns),
                partitioning=table.partition_field,
                clustering=table.clustering_fields,
                quality_summary="canonical_output",
                reconciliation_summary=None,
                latest_rows=preview.rows,
                receipt_id=receipt.receipt_id if receipt else None,
            )
        )

    def compile_cycle_requirements(
        self,
        context: DataFoundationContext,
        cycle_id: str,
        snapshot: BusinessProfileSnapshot,
    ) -> EvidenceRequirementSet:
        cycle = self.get_cycle(context, cycle_id)
        if snapshot.snapshot_id != cycle.business_profile_snapshot_id:
            raise PermissionError("Requirements must compile from the pinned cycle snapshot.")
        return self.load_business_snapshot(context, snapshot)

    def _authorize(self, context: DataFoundationContext) -> None:
        context.require_same_tenant(require_tenant())

    def _binding(self, context: DataFoundationContext, source_id: str) -> SourceBinding:
        self._authorize(context)
        binding = self.store.get_binding(source_id)
        if binding is None:
            raise KeyError("Unknown source.")
        if binding.tenant_id != context.tenant_id or binding.workspace_id != context.workspace_id:
            raise PermissionError("Cross-tenant source access is denied.")
        return binding

    def _frame(self, binding: SourceBinding) -> pd.DataFrame:
        if binding.source_id in self.frames:
            return self.frames[binding.source_id]
        path = binding.resource.logical_path
        if path and self.warehouse.get_table(path):
            frame = self.warehouse.read_table(path)
            self.frames[binding.source_id] = frame
            return frame
        raise KeyError("Source frame is not loaded.")

    def _content_fingerprint(self, frame: pd.DataFrame, binding: SourceBinding) -> str:
        columns = [str(column) for column in frame.columns]
        keys = (
            list(binding.contract.unique_keys)
            or [column for column in ("date", "time") if column in columns]
            or columns[:1]
        )
        return content_fingerprint(frame, columns=columns, key_columns=keys)

    def _latest_date(self, frame: pd.DataFrame, date_field: str | None) -> str | None:
        if not date_field or date_field not in frame.columns or frame.empty:
            return None
        parsed = pd.to_datetime(frame[date_field], errors="coerce").dropna()
        if parsed.empty:
            return None
        return parsed.max().strftime("%Y-%m-%d")

    def _phase(self, context, reqs, inventory, env) -> str:
        if env and env.status_code is DataFoundationReadyStatus.DATA_FOUNDATION_READY:
            return "OPERATE"
        if self.store.get_approval_for_plan:
            plans = getattr(self.store, "foundation_plans", {})
            if any(self.store.get_approval_for_plan(plan_id) for plan_id in plans):
                return "BUILD & VERIFY"
        if inventory:
            return "DISCOVER & ASSESS"
        if reqs:
            return "CONNECT"
        del context
        return "CONNECT"


# Keep unused import referenced for schema fingerprint stability in tests.
_SCHEMA = schema_signature
_QUALITY_RECEIPT = DataQualityReceipt
