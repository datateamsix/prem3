"""Investment Plan foundation service. Drive owns amounts; Firestore stores metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from app.business_iq.store import BusinessIqStore
from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.domain.channels.bindings import PlanningChannelAllocation
from app.identity_graph.store import InMemoryIdentityGraphStore
from app.integrations.google.adapters import DriveClient
from app.investment_planning.authority import require_human_approver, require_server_owned_scope
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
    PortfolioView,
)
from app.investment_planning.drive import file_is_under_budget_tree
from app.investment_planning.drive_binding import TEMPLATE_SCHEMA_VERSION
from app.investment_planning.enums import BudgetScope, BudgetSourceGrain, InvestmentPlanStatus
from app.investment_planning.errors import (
    BudgetFolderDegradedError,
    PlanningAuthorityError,
    PortfolioAssemblyNotImplementedError,
)
from app.investment_planning.ids import new_mapping_id, new_plan_id, new_source_version_id
from app.investment_planning.legacy_allocation import (
    reject_legacy_planning_allocation_as_value_authority,
)
from app.investment_planning.lifecycle import approve_plan, mark_validated, revise_plan
from app.investment_planning.mapping import MappingProposal, propose_column_mapping
from app.investment_planning.markets import IdentityGraphMarketDirectory, MarketIdentityDirectory
from app.investment_planning.parser import ParsedBudgetTable, parse_budget_bytes
from app.investment_planning.source import require_source_identity
from app.investment_planning.store import InvestmentPlanningMetadataStore
from app.investment_planning.template import compile_budget_template
from app.investment_planning.validator import validate_budget_plan
from app.service.entitlements import require_feature
from app.service.google_drive import DriveBindingService
from app.service.google_oauth import GoogleConnectionService


class PortfolioAssembler:
    """Assembles a transient PortfolioView. Live assembly is P6-02."""

    def assemble(self, *, snapshot_id: str) -> PortfolioView:
        del snapshot_id
        raise PortfolioAssemblyNotImplementedError(
            "Portfolio assembly from Drive/actuals/measurement is not implemented in P6-01."
        )

    def assemble_from_legacy_allocation(
        self, allocation: PlanningChannelAllocation
    ) -> PortfolioView:
        reject_legacy_planning_allocation_as_value_authority(allocation)
        raise PortfolioAssemblyNotImplementedError(
            "Legacy PlanningChannelAllocation cannot populate a PortfolioView."
        )


class InvestmentPlanService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        store: InvestmentPlanningMetadataStore,
        drive: DriveClient,
        connections: GoogleConnectionService,
        drive_bindings: DriveBindingService,
        business_iq: BusinessIqStore,
        markets: MarketIdentityDirectory | None = None,
    ) -> None:
        self._repo = repo
        self._store = store
        self._drive = drive
        self._connections = connections
        self._drive_bindings = drive_bindings
        self._business_iq = business_iq
        self._markets = markets or IdentityGraphMarketDirectory(InMemoryIdentityGraphStore())

    def create_plan(
        self,
        *,
        project_id: str,
        name: str,
        fiscal_year: int,
        currency: str = "USD",
        budget_scope: BudgetScope = BudgetScope.PAID_MEDIA_ONLY,
        actor_id: str,
    ) -> InvestmentPlan:
        require_feature(self._repo, Feature.PLANNING_RUN)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        profile = self._business_iq.get_profile(tenant_id=tenant.tenant_id, workspace_id=project_id)
        if profile is None:
            raise PlanningAuthorityError("A pinned Business IQ profile is required.")
        now = datetime.now(UTC)
        plan = InvestmentPlan(
            plan_id=new_plan_id(),
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            workspace_id=project_id,
            name=name,
            fiscal_year=fiscal_year,
            fiscal_start_month=1,
            currency=currency,
            budget_scope=budget_scope,
            business_profile_snapshot_id=profile.current_snapshot_id,
            business_profile_fingerprint=profile.fingerprint,
            status=InvestmentPlanStatus.DRAFT,
            revision=1,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        stored = self._store.put(plan)
        assert isinstance(stored, InvestmentPlan)
        return stored

    def list_plans(self, *, project_id: str) -> tuple[InvestmentPlan, ...]:
        require_feature(self._repo, Feature.PLANNING_RUN)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_plans(tenant_id=tenant.tenant_id, project_id=project_id)

    def get_plan(self, *, plan_id: str, project_id: str) -> InvestmentPlan:
        require_feature(self._repo, Feature.PLANNING_RUN)
        return self._require_plan(plan_id, project_id=project_id)

    def upload_template(
        self, *, plan_id: str, project_id: str, actor_id: str
    ) -> BudgetDriveSourceVersion:
        require_feature(self._repo, Feature.PLANNING_RUN)
        tenant = require_tenant()
        require_human_approver(actor_id)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        profile = self._business_iq.get_profile(
            tenant_id=tenant.tenant_id, workspace_id=plan.project_id
        )
        if profile is None:
            raise PlanningAuthorityError("A pinned Business IQ profile is required.")
        binding = self._live_binding(plan.project_id)
        token = self._access_token(binding.connection_id)
        compiled = compile_budget_template(profile=profile, fiscal_year=plan.fiscal_year)
        uploaded = self._drive.upload_file(
            access_token=token,
            name=compiled.file_name,
            parent_id=binding.budget_templates_folder_id or "",
            data=compiled.payload,
            mime_type=compiled.mime_type,
        )
        identity = require_source_identity(uploaded)
        source = BudgetDriveSourceVersion(
            source_version_id=new_source_version_id(),
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id,
            project_id=plan.project_id,
            workspace_id=plan.workspace_id,
            drive_connection_id=binding.connection_id,
            budgets_folder_id=binding.budgets_folder_id,
            drive_file_id=identity.drive_file_id,
            file_name=uploaded.name,
            mime_type=uploaded.mime_type,
            drive_version=identity.drive_version,
            head_revision_id=identity.head_revision_id,
            md5_checksum=identity.md5_checksum,
            schema_version=TEMPLATE_SCHEMA_VERSION,
            mapping_version="v1",
            source_grain=BudgetSourceGrain.MARKET_CHANNEL_QUARTER,
            created_at=datetime.now(UTC),
            created_by=actor_id,
        )
        stored = self._store.put(source)
        assert isinstance(stored, BudgetDriveSourceVersion)
        return stored

    def ingest_bytes(
        self,
        *,
        plan_id: str,
        project_id: str,
        file_name: str,
        mime_type: str,
        data: bytes,
        actor_id: str,
    ) -> tuple[BudgetDriveSourceVersion, ParsedBudgetTable, MappingProposal]:
        require_feature(self._repo, Feature.PLANNING_RUN)
        require_human_approver(actor_id)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        binding = self._live_binding(plan.project_id)
        if not binding.budget_plans_folder_id:
            raise BudgetFolderDegradedError("Budget plans folder is not bound.")
        token = self._access_token(binding.connection_id)
        table = parse_budget_bytes(data=data, mime_type=mime_type, file_name=file_name)
        uploaded = self._drive.upload_file(
            access_token=token,
            name=file_name,
            parent_id=binding.budget_plans_folder_id,
            data=data,
            mime_type=mime_type,
        )
        stored, proposal = self._persist_source_and_mapping(
            plan=plan,
            binding=binding,
            file=uploaded,
            table=table,
            actor_id=actor_id,
            schema_version="ingested_v1",
        )
        return stored, table, proposal

    def ingest_drive_file(
        self,
        *,
        plan_id: str,
        project_id: str,
        drive_file_id: str,
        actor_id: str,
    ) -> tuple[BudgetDriveSourceVersion, MappingProposal]:
        require_feature(self._repo, Feature.PLANNING_RUN)
        require_human_approver(actor_id)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        binding = self._live_binding(plan.project_id)
        token = self._access_token(binding.connection_id)
        live = self._drive.get_file(access_token=token, file_id=drive_file_id)
        if live is None or live.trashed:
            raise PlanningAuthorityError("Drive source file was not found.")
        if not file_is_under_budget_tree(live, self._budget_folder_ids(binding)):
            raise PlanningAuthorityError("Drive file is outside the bound budget folder tree.")
        data = self._drive.download_file(access_token=token, file_id=drive_file_id)
        table = parse_budget_bytes(data=data, mime_type=live.mime_type, file_name=live.name)
        stored, proposal = self._persist_source_and_mapping(
            plan=plan,
            binding=binding,
            file=live,
            table=table,
            actor_id=actor_id,
            schema_version="ingested_v1",
        )
        return stored, proposal

    def confirm_mapping(
        self,
        *,
        plan_id: str,
        project_id: str,
        mapping_id: str,
        actor_id: str,
        market_column: str | None = None,
        channel_column: str | None = None,
        quarter_columns: tuple[str, ...] | None = None,
    ) -> BudgetColumnMapping:
        require_feature(self._repo, Feature.PLANNING_RUN)
        require_human_approver(actor_id)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        mapping = self._store.get_mapping(mapping_id)
        if mapping is None or mapping.plan_id != plan.plan_id:
            raise PlanningAuthorityError("Column mapping was not found.")
        updates: dict[str, object] = {"confirmed": True}
        if market_column is not None:
            updates["market_column"] = market_column
        if channel_column is not None:
            updates["channel_column"] = channel_column
        if quarter_columns is not None:
            updates["quarter_columns"] = quarter_columns
        confirmed = mapping.model_copy(update=updates)
        stored = self._store.put(confirmed)
        assert isinstance(stored, BudgetColumnMapping)
        return stored

    def validate(
        self,
        *,
        plan_id: str,
        mapping_id: str | None = None,
        blanks_acknowledged: bool = False,
        project_id: str | None = None,
    ) -> InvestmentPlanValidationReceipt:
        require_feature(self._repo, Feature.PLANNING_RUN)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        mapping = self._resolve_mapping(plan, mapping_id)
        source = self._store.get_source(mapping.source_version_id)
        if source is None:
            raise PlanningAuthorityError("Source version was not found.")
        binding = self._live_binding(plan.project_id)
        token = self._access_token(binding.connection_id)
        live = self._drive.get_file(access_token=token, file_id=source.drive_file_id)
        if live is None:
            raise PlanningAuthorityError("Drive source file was not found.")
        loaded = require_source_identity(live)
        data = self._drive.download_file(access_token=token, file_id=source.drive_file_id)
        table = parse_budget_bytes(data=data, mime_type=live.mime_type, file_name=live.name)
        known = self._markets.known_market_ids(
            tenant_id=plan.tenant_id, project_id=plan.project_id
        )
        receipt = validate_budget_plan(
            plan=plan,
            binding=binding,
            file=live,
            table=table,
            mapping=mapping,
            loaded_identity=loaded,
            known_market_ids=known,
            blanks_acknowledged=blanks_acknowledged,
            directory=self._markets,
        )
        self._store.put(receipt)
        self._store.put(mark_validated(plan, receipt))
        return receipt

    def save_version(self, *, plan_id: str, project_id: str, actor_id: str) -> BudgetDriveSourceVersion:
        require_feature(self._repo, Feature.PLANNING_RUN)
        require_human_approver(actor_id)
        plan = self._require_plan(plan_id, project_id=project_id)
        self._require_mutable(plan)
        if not plan.active_source_version_id:
            raise PlanningAuthorityError("Source version was not found.")
        source = self._store.get_source(plan.active_source_version_id)
        if source is None:
            raise PlanningAuthorityError("Source version was not found.")
        binding = self._live_binding(plan.project_id)
        if not binding.budget_plans_folder_id:
            raise BudgetFolderDegradedError("Budget plans folder is not bound.")
        token = self._access_token(binding.connection_id)
        live = self._drive.get_file(access_token=token, file_id=source.drive_file_id)
        if live is None:
            raise PlanningAuthorityError("Drive source file was not found.")
        data = self._drive.download_file(access_token=token, file_id=source.drive_file_id)
        versioned_name = f"{plan.plan_id}_{source.source_version_id}_{live.name}"
        uploaded = self._drive.upload_file(
            access_token=token,
            name=versioned_name,
            parent_id=binding.budget_plans_folder_id,
            data=data,
            mime_type=live.mime_type,
        )
        identity = require_source_identity(uploaded)
        saved = BudgetDriveSourceVersion(
            source_version_id=new_source_version_id(),
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id,
            project_id=plan.project_id,
            workspace_id=plan.workspace_id,
            drive_connection_id=binding.connection_id,
            budgets_folder_id=binding.budgets_folder_id,
            drive_file_id=identity.drive_file_id,
            file_name=uploaded.name,
            mime_type=uploaded.mime_type,
            drive_version=identity.drive_version,
            head_revision_id=identity.head_revision_id,
            md5_checksum=identity.md5_checksum,
            schema_version=source.schema_version,
            mapping_version=source.mapping_version,
            source_grain=source.source_grain,
            predecessor_source_version_id=source.source_version_id,
            created_at=datetime.now(UTC),
            created_by=actor_id,
        )
        stored = self._store.put(saved)
        assert isinstance(stored, BudgetDriveSourceVersion)
        mapping = self._store.mapping_for_source(source.source_version_id)
        if mapping is not None:
            self._store.put(
                mapping.model_copy(
                    update={
                        "mapping_id": new_mapping_id(),
                        "source_version_id": stored.source_version_id,
                    }
                )
            )
        self._store.put(
            plan.model_copy(
                update={
                    "active_source_version_id": stored.source_version_id,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        return stored

    def get_ready(
        self, *, plan_id: str, project_id: str
    ) -> tuple[InvestmentPlan, InvestmentPlanValidationReceipt | None]:
        require_feature(self._repo, Feature.PLANNING_RUN)
        plan = self._require_plan(plan_id, project_id=project_id)
        return plan, self._store.latest_receipt(plan.plan_id)

    def approve(
        self, *, plan_id: str, project_id: str, receipt_id: str, actor_id: str
    ) -> InvestmentPlan:
        require_feature(self._repo, Feature.PLANNING_RUN)
        plan = self._require_plan(plan_id, project_id=project_id)
        receipt = self._store.get_receipt(receipt_id)
        if receipt is None:
            raise PlanningAuthorityError("Validation receipt was not found.")
        if receipt.source_version_id != plan.active_source_version_id:
            raise PlanningAuthorityError(
                "Validation receipt does not match the active Drive source version."
            )
        approved = approve_plan(plan=plan, receipt=receipt, actor_id=actor_id)
        stored = self._store.put(approved)
        assert isinstance(stored, InvestmentPlan)
        if stored.predecessor_plan_id:
            previous = self._store.get_plan(stored.predecessor_plan_id)
            if (
                previous is not None
                and previous.tenant_id == stored.tenant_id
                and previous.project_id == stored.project_id
                and previous.status is InvestmentPlanStatus.APPROVED
            ):
                self._store.put(
                    previous.model_copy(
                        update={
                            "status": InvestmentPlanStatus.SUPERSEDED,
                            "updated_at": datetime.now(UTC),
                        }
                    )
                )
        return stored

    def revise(self, *, plan_id: str, project_id: str, actor_id: str) -> InvestmentPlan:
        require_feature(self._repo, Feature.PLANNING_RUN)
        plan = self._require_plan(plan_id, project_id=project_id)
        draft = revise_plan(plan=plan, actor_id=actor_id)
        stored = self._store.put(draft)
        assert isinstance(stored, InvestmentPlan)
        return stored

    def _persist_source_and_mapping(
        self,
        *,
        plan: InvestmentPlan,
        binding,
        file,
        table: ParsedBudgetTable,
        actor_id: str,
        schema_version: str,
        predecessor_source_version_id: str | None = None,
    ) -> tuple[BudgetDriveSourceVersion, MappingProposal]:
        identity = require_source_identity(file)
        source = BudgetDriveSourceVersion(
            source_version_id=new_source_version_id(),
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id,
            project_id=plan.project_id,
            workspace_id=plan.workspace_id,
            drive_connection_id=binding.connection_id,
            budgets_folder_id=binding.budgets_folder_id,
            drive_file_id=identity.drive_file_id,
            file_name=file.name,
            mime_type=file.mime_type,
            drive_version=identity.drive_version,
            head_revision_id=identity.head_revision_id,
            md5_checksum=identity.md5_checksum,
            schema_version=schema_version,
            mapping_version="v1",
            source_grain=BudgetSourceGrain.MARKET_CHANNEL_QUARTER,
            predecessor_source_version_id=predecessor_source_version_id,
            created_at=datetime.now(UTC),
            created_by=actor_id,
        )
        stored = self._store.put(source)
        assert isinstance(stored, BudgetDriveSourceVersion)
        proposal = propose_column_mapping(
            table,
            plan_id=plan.plan_id,
            source_version_id=stored.source_version_id,
            confirmed=False,
        )
        if not proposal.ambiguous:
            confirmed = proposal.mapping.model_copy(update={"confirmed": True})
            self._store.put(confirmed)
            proposal = MappingProposal(
                mapping=confirmed,
                ambiguous=proposal.ambiguous,
                market_display_column=proposal.market_display_column,
                row_type_column=proposal.row_type_column,
            )
        else:
            self._store.put(proposal.mapping)
        self._store.put(
            plan.model_copy(
                update={
                    "active_source_version_id": stored.source_version_id,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        return stored, proposal

    def _resolve_mapping(self, plan: InvestmentPlan, mapping_id: str | None) -> BudgetColumnMapping:
        if mapping_id:
            mapping = self._store.get_mapping(mapping_id)
            if mapping is None or mapping.plan_id != plan.plan_id:
                raise PlanningAuthorityError("Column mapping was not found.")
            return mapping
        if not plan.active_source_version_id:
            raise PlanningAuthorityError("Column mapping was not found.")
        mapping = self._store.mapping_for_source(plan.active_source_version_id)
        if mapping is None:
            raise PlanningAuthorityError("Column mapping was not found.")
        return mapping

    def _require_mutable(self, plan: InvestmentPlan) -> None:
        if plan.status is InvestmentPlanStatus.APPROVED:
            raise PlanningAuthorityError(
                "An approved plan cannot be mutated. Revise to create a new version."
            )
        if plan.status is InvestmentPlanStatus.SUPERSEDED:
            raise PlanningAuthorityError("A superseded plan cannot be mutated.")

    def _require_plan(self, plan_id: str, *, project_id: str | None = None) -> InvestmentPlan:
        tenant = require_tenant()
        plan = self._store.get_plan(plan_id)
        if plan is None or plan.tenant_id != tenant.tenant_id:
            raise PlanningAuthorityError("Investment Plan was not found.")
        if project_id is not None and plan.project_id != project_id:
            raise PlanningAuthorityError("Investment Plan was not found.")
        return plan

    def _live_binding(self, project_id: str):
        tenant = require_tenant()
        binding = self._repo.get_drive_binding(tenant_id=tenant.tenant_id, workspace_id=project_id)
        if binding is None or not binding.budgets_folder_id:
            raise BudgetFolderDegradedError("Budget Drive folders are not provisioned.")
        return binding

    def _budget_folder_ids(self, binding) -> tuple[str | None, ...]:
        return (
            binding.budgets_folder_id,
            binding.budget_templates_folder_id,
            binding.budget_plans_folder_id,
            binding.budget_scenarios_folder_id,
            binding.budget_proposals_folder_id,
        )

    def _access_token(self, connection_id: str) -> str:
        connection = self._connections.get_connection(connection_id=connection_id)
        return self._connections.user_access_token(connection=connection)
