"""P6-04 optimization readiness service. Does not run Meridian BudgetOptimizer."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.investment_optimization.accepted_model import (
    AcceptedModelDirectory,
    select_accepted_model,
)
from app.investment_optimization.consumption import (
    ModelConsumptionSource,
    bind_projection_to_accepted_model,
)
from app.investment_optimization.contracts import (
    MappingOverride,
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationInputContract,
    OptimizationIssue,
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
)
from app.investment_optimization.coverage import assemble_optimization_evidence_coverage
from app.investment_optimization.enums import (
    OptimizationIssueCode,
    OptimizationReadinessStatus,
    PortfolioModelMappingStatus,
)
from app.investment_optimization.errors import (
    CrossProjectMappingError,
    CrossTenantMappingError,
)
from app.investment_optimization.execution import home_overlay_status
from app.investment_optimization.mapping import build_portfolio_model_mapping
from app.investment_optimization.readiness import (
    build_optimization_input_contract,
    evaluate_readiness,
    receipt_is_stale,
)
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.authority import require_human_approver, require_server_owned_scope
from app.investment_planning.enums import PortfolioBaselineKind
from app.investment_planning.errors import PlanningAuthorityError
from app.investment_planning.service import InvestmentPlanService
from app.service.entitlements import require_feature


def _issue(
    code: OptimizationIssueCode, *, blocking: bool, review: bool = False
) -> OptimizationIssue:
    return OptimizationIssue(
        code=code,
        blocking=blocking,
        review_required=review,
        message_key=code.value,
    )


class OptimizationReadinessService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        store: OptimizationMetadataStore,
        planning: InvestmentPlanService,
        models: AcceptedModelDirectory | None = None,
        consumption: ModelConsumptionSource | None = None,
    ) -> None:
        self._repo = repo
        self._store = store
        self._planning = planning
        self._models = models
        self._consumption = consumption

    def create_mapping(
        self,
        *,
        project_id: str,
        portfolio_snapshot_id: str,
        actor_id: str,
        model_version_id: str | None = None,
        mapping_overrides: tuple[MappingOverride, ...] = (),
        tenant_id: str | None = None,
        model_artifact_location: str | None = None,
        require_market_level_optimization: bool = False,
    ) -> PortfolioModelMapping:
        if tenant_id is not None:
            raise PlanningAuthorityError("Client cannot supply tenant_id.")
        if model_artifact_location is not None:
            raise PlanningAuthorityError("Client cannot supply model artifact location.")
        mapping, _receipt = self._evaluate(
            project_id=project_id,
            actor_id=actor_id,
            portfolio_snapshot_id=portfolio_snapshot_id,
            model_version_id=model_version_id,
            mapping_overrides=mapping_overrides,
            require_market_level_optimization=require_market_level_optimization,
            persist_mapping=True,
            persist_receipt=False,
        )
        return mapping

    def get_mapping(self, *, mapping_id: str, project_id: str) -> PortfolioModelMapping:
        require_feature(self._repo, Feature.PORTFOLIO_VIEW)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        mapping = self._store.get_mapping(mapping_id)
        if mapping is None:
            raise PlanningAuthorityError("Portfolio model mapping was not found.")
        if mapping.tenant_id != tenant.tenant_id:
            raise CrossTenantMappingError("Cross-tenant model mapping is not allowed.")
        if mapping.project_id != project_id:
            raise CrossProjectMappingError("Cross-project model mapping is not allowed.")
        return mapping

    def list_mappings(self, *, project_id: str) -> tuple[PortfolioModelMapping, ...]:
        require_feature(self._repo, Feature.PORTFOLIO_VIEW)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_mappings(tenant_id=tenant.tenant_id, project_id=project_id)

    def evaluate(
        self,
        *,
        project_id: str,
        actor_id: str,
        portfolio_snapshot_id: str | None = None,
        model_version_id: str | None = None,
        mapping_overrides: tuple[MappingOverride, ...] = (),
        tenant_id: str | None = None,
        model_artifact_location: str | None = None,
        require_market_level_optimization: bool = False,
    ) -> OptimizationReadinessReceipt:
        if tenant_id is not None:
            raise PlanningAuthorityError("Client cannot supply tenant_id.")
        if model_artifact_location is not None:
            raise PlanningAuthorityError("Client cannot supply model artifact location.")
        _mapping, receipt = self._evaluate(
            project_id=project_id,
            actor_id=actor_id,
            portfolio_snapshot_id=portfolio_snapshot_id,
            model_version_id=model_version_id,
            mapping_overrides=mapping_overrides,
            require_market_level_optimization=require_market_level_optimization,
            persist_mapping=True,
            persist_receipt=True,
        )
        return receipt

    def get_readiness(self, *, project_id: str) -> OptimizationReadinessReceipt:
        require_feature(self._repo, Feature.PORTFOLIO_VIEW)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        receipt = self._store.latest_receipt(tenant_id=tenant.tenant_id, project_id=project_id)
        if receipt is None:
            return self.evaluate(project_id=project_id, actor_id=tenant.user_id or "unknown")
        snapshot = None
        if receipt.portfolio_snapshot_id:
            snapshot = self._planning._store.get_snapshot(receipt.portfolio_snapshot_id)
        mapping = None
        if receipt.mapping_id:
            mapping = self._store.get_mapping(receipt.mapping_id)
        if receipt_is_stale(
            receipt,
            portfolio_fingerprint=None if snapshot is None else snapshot.fingerprint,
            model_fingerprint=receipt.model_fingerprint,
            mapping_fingerprint=None if mapping is None else mapping.fingerprint,
        ):
            return receipt.model_copy(update={"status": OptimizationReadinessStatus.STALE})
        return receipt

    def latest_status(self, *, tenant_id: str, project_id: str) -> str | None:
        return home_overlay_status(self._store, tenant_id=tenant_id, project_id=project_id)

    def _evaluate(
        self,
        *,
        project_id: str,
        actor_id: str,
        portfolio_snapshot_id: str | None,
        model_version_id: str | None,
        mapping_overrides: tuple[MappingOverride, ...],
        require_market_level_optimization: bool,
        persist_mapping: bool,
        persist_receipt: bool,
    ) -> tuple[PortfolioModelMapping, OptimizationReadinessReceipt]:
        require_feature(self._repo, Feature.PORTFOLIO_VIEW)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        require_human_approver(actor_id)
        now = datetime.now(UTC)
        extra: list[OptimizationIssue] = []
        state, snapshot, view = self._planning.assemble_portfolio(
            project_id=project_id,
            fiscal_year=None,
            actor_id=actor_id,
        )
        if portfolio_snapshot_id and snapshot is not None:
            if snapshot.snapshot_id != portfolio_snapshot_id:
                loaded = self._planning._store.get_snapshot(portfolio_snapshot_id)
                if loaded is None:
                    raise PlanningAuthorityError("Portfolio snapshot was not found.")
                if loaded.tenant_id != tenant.tenant_id:
                    raise CrossTenantMappingError("Cross-tenant model mapping is not allowed.")
                if loaded.project_id != project_id:
                    raise CrossProjectMappingError("Cross-project model mapping is not allowed.")
                snapshot = loaded
        contract: ModelConsumptionContract | None = None
        mapping: PortfolioModelMapping | None = None
        coverage: OptimizationEvidenceCoverage | None = None
        input_contract: OptimizationInputContract | None = None
        if self._models is not None:
            versions = self._models.list_versions(
                tenant_id=tenant.tenant_id, project_id=project_id
            )
            selection = select_accepted_model(
                versions,
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                requested_model_version_id=model_version_id,
            )
            if selection.issue_code is not None:
                extra.append(
                    _issue(
                        selection.issue_code,
                        blocking=(
                            selection.issue_code
                            is not OptimizationIssueCode.MULTIPLE_ACCEPTED_MODELS
                        ),
                        review=(
                            selection.issue_code
                            is OptimizationIssueCode.MULTIPLE_ACCEPTED_MODELS
                        ),
                    )
                )
            elif selection.version is not None and self._consumption is not None:
                loaded = self._consumption.get_contract(
                    tenant_id=tenant.tenant_id,
                    project_id=project_id,
                    model_version_id=selection.version.model_version_id,
                )
                if loaded is None:
                    extra.append(
                        _issue(
                            OptimizationIssueCode.MODEL_CONSUMPTION_CONTRACT_INCOMPLETE,
                            blocking=True,
                        )
                    )
                else:
                    if loaded.tenant_id != tenant.tenant_id:
                        raise CrossTenantMappingError(
                            "Cross-tenant model mapping is not allowed."
                        )
                    if loaded.project_id != project_id:
                        raise CrossProjectMappingError(
                            "Cross-project model mapping is not allowed."
                        )
                    contract = bind_projection_to_accepted_model(
                        loaded, selection.version
                    )
        elif model_version_id:
            extra.append(_issue(OptimizationIssueCode.NO_ACCEPTED_MODEL, blocking=True))
        else:
            extra.append(_issue(OptimizationIssueCode.NO_ACCEPTED_MODEL, blocking=True))

        if snapshot is not None and view is not None and contract is not None:
            mapping = build_portfolio_model_mapping(
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                snapshot_id=snapshot.snapshot_id,
                baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
                view=view,
                contract=contract,
                created_at=now,
                created_by=actor_id,
                overrides=mapping_overrides,
                require_market_level_optimization=require_market_level_optimization,
            )
            coverage = assemble_optimization_evidence_coverage(
                mapping=mapping,
                contract=contract,
                mta_evidence_ref=snapshot.mta_result_ref,
            )
            input_contract = build_optimization_input_contract(
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                snapshot=snapshot,
                view=view,
                mapping=mapping,
                contract=contract,
                created_at=now,
                issues=(),
            )
            if persist_mapping:
                stored_mapping = self._store.put(mapping)
                assert isinstance(stored_mapping, PortfolioModelMapping)
                mapping = stored_mapping
                self._store.put(coverage)
                self._store.put(input_contract)
                self._store.put(contract)

        if mapping is None:
            mapping = PortfolioModelMapping(
                mapping_id="pmap_pendingpendingpendin",
                tenant_id=tenant.tenant_id,
                project_id=project_id,
                portfolio_snapshot_id=portfolio_snapshot_id or "psnap_none",
                model_version_id=model_version_id or "mver_none",
                mapping_status=PortfolioModelMappingStatus.NOT_READY,
                created_at=now,
                created_by=actor_id,
                fingerprint="pending",
            )

        receipt = evaluate_readiness(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            coverage_state=state,
            snapshot=snapshot,
            view=view,
            contract=contract,
            mapping=None if mapping.fingerprint == "pending" else mapping,
            coverage=coverage,
            input_contract=input_contract,
            created_at=now,
            extra_issues=tuple(extra),
        )
        existing = self._store.latest_receipt(tenant_id=tenant.tenant_id, project_id=project_id)
        if (
            persist_receipt
            and existing is not None
            and existing.fingerprint == receipt.fingerprint
        ):
            return mapping, existing
        if persist_receipt:
            stored = self._store.put(receipt)
            assert isinstance(stored, OptimizationReadinessReceipt)
            receipt = stored
        return mapping, receipt
