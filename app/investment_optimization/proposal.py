"""Committee OptimizationProposal service. Distinct from OptimizationRun."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.control_plane.models import Feature
from app.control_plane.repository import ControlPlaneRepository
from app.core.tenancy import require_tenant
from app.investment_optimization.accepted_model import AcceptedModelDirectory
from app.investment_optimization.budget_resolve import reject_client_budget_authority
from app.investment_optimization.comparison import build_change_summary, build_comparison
from app.investment_optimization.contracts import (
    DEFAULT_PROPOSAL_APPROVAL_POLICY,
    OptimizationProposal,
    OptimizationResultPayload,
    ProposalChangeSummary,
    ProposalDecisionReceipt,
    ScenarioArtifact,
    ScenarioComparison,
)
from app.investment_optimization.decision import apply_decision, transition_status
from app.investment_optimization.enums import (
    GOVERNANCE_POLICY_VERSION,
    OptimizationProposalLifecycleStatus,
    OptimizationRunStatus,
    ProposalDecision,
    ProposalReadinessStatus,
)
from app.investment_optimization.errors import (
    CrossProjectProposalAccessError,
    CrossTenantProposalAccessError,
    ProposalNotApprovedError,
    ProposalNotFoundError,
    ProposalNotReadyError,
    ProposalStaleError,
    ScenarioNotFoundError,
    ScenarioRequiresCompletedOptimizationError,
)
from app.investment_optimization.ids import new_proposal_id
from app.investment_optimization.plan_revision import (
    PlanningRevisionHost,
    create_plan_revision,
)
from app.investment_optimization.proposal_readiness import evaluate_proposal_readiness
from app.investment_optimization.run_service import OptimizationRunService
from app.investment_optimization.scenario import (
    build_scenario_artifact,
    read_scenario_artifact,
)
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.authority import require_human_approver, require_server_owned_scope
from app.investment_planning.contracts import InvestmentPlan
from app.investment_planning.enums import InvestmentPlanStatus
from app.investment_planning.errors import PlanningAuthorityError
from app.investment_planning.fingerprint import (
    investment_plan_fingerprint,
    metadata_fingerprint,
)
from app.service.entitlements import require_feature
from app.service.object_store import ObjectStore

_LOG = logging.getLogger("prem3.investment_optimization")


def _log(event: str, **fields: str) -> None:
    _LOG.info("%s %s", event, " ".join(f"{key}={value}" for key, value in sorted(fields.items())))


class ProposalGovernanceService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        store: OptimizationMetadataStore,
        runs: OptimizationRunService,
        object_store: ObjectStore,
        artifact_bucket: str,
        planning: PlanningRevisionHost | None = None,
        models: AcceptedModelDirectory | None = None,
        source_plan: InvestmentPlan | None = None,
    ) -> None:
        self._repo = repo
        self._store = store
        self._runs = runs
        self._object_store = object_store
        self._artifact_bucket = artifact_bucket
        self._planning = planning
        self._models = models
        self._source_plan = source_plan

    def create_scenario(
        self,
        *,
        project_id: str,
        actor_id: str,
        optimization_run_id: str,
        tenant_id: str | None = None,
        budget_array: object | None = None,
        model_path: str | None = None,
        drive_path: str | None = None,
        variable_map: object | None = None,
    ) -> ScenarioArtifact:
        reject_client_budget_authority(
            tenant_id=tenant_id,
            budget_array=budget_array,
            model_path=model_path,
            drive_path=drive_path,
            variable_map=variable_map,
        )
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        require_human_approver(actor_id)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        run = self._runs.get_run(optimization_run_id=optimization_run_id, project_id=project_id)
        if run.status is not OptimizationRunStatus.COMPLETE:
            raise ScenarioRequiresCompletedOptimizationError(
                "Scenario requires a completed optimization result."
            )
        payload = self._runs.get_result(
            optimization_run_id=optimization_run_id, project_id=project_id
        )
        plan = self._resolve_source_plan(project_id=project_id, actor_id=actor_id)
        scenario = build_scenario_artifact(
            run=run,
            payload=payload,
            source_plan_id=plan.plan_id,
            source_plan_revision=plan.revision,
            source_plan_fingerprint=investment_plan_fingerprint(
                plan_id=plan.plan_id,
                project_id=plan.project_id,
                revision=plan.revision,
                status=plan.status.value,
            ),
            period=str(getattr(plan, "fiscal_year", "")),
            actor_id=actor_id,
            object_store=self._object_store,
            artifact_bucket=self._artifact_bucket,
        )
        stored = self._store.put(scenario)
        assert isinstance(stored, ScenarioArtifact)
        _log("scenario_created", scenario_id=stored.scenario_id, run_id=run.optimization_run_id)
        return stored

    def list_scenarios(self, *, project_id: str) -> tuple[ScenarioArtifact, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_scenarios(tenant_id=tenant.tenant_id, project_id=project_id)

    def get_scenario(self, *, scenario_id: str, project_id: str) -> ScenarioArtifact:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        scenario = self._store.get_scenario(scenario_id)
        if scenario is None:
            raise ScenarioNotFoundError("Scenario artifact was not found.")
        self._assert_scope(scenario.tenant_id, scenario.project_id, project_id)
        return scenario

    def get_comparison(self, *, scenario_id: str, project_id: str) -> ScenarioComparison:
        scenario = self.get_scenario(scenario_id=scenario_id, project_id=project_id)
        payload = self._payload_for_scenario(scenario, project_id=project_id)
        return build_comparison(scenario_id=scenario.scenario_id, payload=payload)

    def create_proposal(
        self,
        *,
        project_id: str,
        actor_id: str,
        scenario_id: str,
        title: str | None = None,
        summary: str | None = None,
        decision_owner_user_id: str | None = None,
        supersedes_proposal_id: str | None = None,
        tenant_id: str | None = None,
        budget_array: object | None = None,
        model_path: str | None = None,
        drive_path: str | None = None,
        variable_map: object | None = None,
    ) -> OptimizationProposal:
        reject_client_budget_authority(
            tenant_id=tenant_id,
            budget_array=budget_array,
            model_path=model_path,
            drive_path=drive_path,
            variable_map=variable_map,
        )
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        require_human_approver(actor_id)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        scenario = self.get_scenario(scenario_id=scenario_id, project_id=project_id)
        run = self._runs.get_run(
            optimization_run_id=scenario.optimization_run_id, project_id=project_id
        )
        now = datetime.now(UTC)
        proposal_id = new_proposal_id()
        body = {
            "proposal_id": proposal_id,
            "scenario_id": scenario.scenario_id,
            "source_plan_id": scenario.source_plan_id,
            "optimization_run_id": scenario.optimization_run_id,
            "model_version_id": run.model_version_id,
        }
        proposal = OptimizationProposal(
            proposal_id=proposal_id,
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            scenario_id=scenario.scenario_id,
            source_plan_id=scenario.source_plan_id,
            source_plan_revision=scenario.source_plan_revision,
            source_plan_fingerprint=scenario.source_plan_fingerprint,
            optimization_run_id=scenario.optimization_run_id,
            optimization_readiness_receipt_id=run.readiness_receipt_id,
            model_version_id=run.model_version_id or "",
            status=OptimizationProposalLifecycleStatus.DRAFT,
            title=title,
            summary=summary,
            decision_owner_user_id=decision_owner_user_id,
            policy_version=GOVERNANCE_POLICY_VERSION,
            supersedes_proposal_id=supersedes_proposal_id,
            created_at=now,
            created_by=actor_id,
            fingerprint=metadata_fingerprint(body),
        )
        receipt = self._evaluate(proposal)
        proposal = proposal.model_copy(update={"readiness_receipt_id": receipt.receipt_id})
        stored = self._store.put(proposal)
        assert isinstance(stored, OptimizationProposal)
        _log("proposal_created", proposal_id=stored.proposal_id, scenario_id=scenario.scenario_id)
        return stored

    def list_proposals(self, *, project_id: str) -> tuple[OptimizationProposal, ...]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        return self._store.list_proposals(tenant_id=tenant.tenant_id, project_id=project_id)

    def get_proposal(self, *, proposal_id: str, project_id: str) -> OptimizationProposal:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        tenant = require_tenant()
        require_server_owned_scope(tenant_id=tenant.tenant_id, project_id=project_id)
        proposal = self._store.get_proposal(proposal_id)
        if proposal is None:
            raise ProposalNotFoundError("Optimization proposal was not found.")
        self._assert_scope(proposal.tenant_id, proposal.project_id, project_id)
        return proposal

    def submit_proposal(
        self, *, proposal_id: str, project_id: str, actor_id: str
    ) -> OptimizationProposal:
        require_human_approver(actor_id)
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        receipt = self._evaluate(proposal)
        if receipt.status is ProposalReadinessStatus.STALE:
            return self._mark_stale(proposal)
        if receipt.status is not ProposalReadinessStatus.PROPOSAL_READY:
            raise ProposalNotReadyError("Only ready proposals may be submitted.")
        transition_status(
            current=proposal.status, target=OptimizationProposalLifecycleStatus.SUBMITTED
        )
        now = datetime.now(UTC)
        updated = proposal.model_copy(
            update={
                "status": OptimizationProposalLifecycleStatus.SUBMITTED,
                "submitted_at": now,
                "readiness_receipt_id": receipt.receipt_id,
            }
        )
        stored = self._store.put(updated)
        assert isinstance(stored, OptimizationProposal)
        _log("proposal_submitted", proposal_id=stored.proposal_id)
        return stored

    def review_proposal(
        self, *, proposal_id: str, project_id: str, actor_id: str
    ) -> OptimizationProposal:
        require_human_approver(actor_id)
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        self._refresh_staleness(proposal)
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        if proposal.status is OptimizationProposalLifecycleStatus.STALE:
            return proposal
        transition_status(
            current=proposal.status, target=OptimizationProposalLifecycleStatus.UNDER_REVIEW
        )
        stored = self._store.put(
            proposal.model_copy(update={"status": OptimizationProposalLifecycleStatus.UNDER_REVIEW})
        )
        assert isinstance(stored, OptimizationProposal)
        return stored

    def decide(
        self,
        *,
        proposal_id: str,
        project_id: str,
        actor_id: str,
        decision: ProposalDecision,
        comment: str | None = None,
    ) -> tuple[OptimizationProposal, ProposalDecisionReceipt]:
        require_feature(self._repo, Feature.BUDGET_OPTIMIZATION)
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        self._refresh_staleness(proposal)
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        if proposal.status is OptimizationProposalLifecycleStatus.STALE:
            raise ProposalStaleError("Stale proposals cannot be approved or decided.")
        if (
            decision is ProposalDecision.REJECT
            and DEFAULT_PROPOSAL_APPROVAL_POLICY.requires_comment_on_rejection
            and not (comment or "").strip()
        ):
            raise PlanningAuthorityError("Rejection requires a comment.")
        scenario = self.get_scenario(scenario_id=proposal.scenario_id, project_id=project_id)
        payload = self._payload_for_scenario(scenario, project_id=project_id)
        updated, receipt, record = apply_decision(
            proposal=proposal,
            scenario=scenario,
            result_fingerprint=payload.fingerprint,
            decision=decision,
            actor_id=actor_id,
            comment=comment,
        )
        self._store.put(updated)
        self._store.put(receipt)
        self._store.put(record)
        _log("proposal_decided", proposal_id=updated.proposal_id, decision=decision.value)
        return updated, receipt

    def create_plan_revision_from_proposal(
        self, *, proposal_id: str, project_id: str, actor_id: str
    ) -> InvestmentPlan:
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        if proposal.status is not OptimizationProposalLifecycleStatus.APPROVED:
            raise ProposalNotApprovedError(
                "Unapproved proposals cannot create a plan revision."
            )
        if self._planning is None:
            raise PlanningAuthorityError("Planning revision host is not configured.")
        scenario = self.get_scenario(scenario_id=proposal.scenario_id, project_id=project_id)
        read_scenario_artifact(
            store=self._object_store,
            bucket=scenario.artifact_bucket,
            object_name=scenario.artifact_object_name,
            expected_fingerprint=scenario.artifact_fingerprint,
        )
        payload = self._payload_for_scenario(scenario, project_id=project_id)
        draft = create_plan_revision(
            planning=self._planning,
            proposal=proposal,
            scenario=scenario,
            payload=payload,
            actor_id=actor_id,
        )
        self._store.put(
            proposal.model_copy(update={"plan_revision_plan_id": draft.plan_id})
        )
        _log(
            "plan_revision_created",
            proposal_id=proposal.proposal_id,
            plan_id=draft.plan_id,
        )
        return draft

    def change_summary(
        self, *, proposal_id: str, project_id: str
    ) -> ProposalChangeSummary:
        proposal = self.get_proposal(proposal_id=proposal_id, project_id=project_id)
        scenario = self.get_scenario(scenario_id=proposal.scenario_id, project_id=project_id)
        payload = self._payload_for_scenario(scenario, project_id=project_id)
        comparison = build_comparison(scenario_id=scenario.scenario_id, payload=payload)
        return build_change_summary(
            proposal_id=proposal.proposal_id, payload=payload, comparison=comparison
        )

    def _payload_for_scenario(
        self, scenario: ScenarioArtifact, *, project_id: str
    ) -> OptimizationResultPayload:
        return self._runs.get_result(
            optimization_run_id=scenario.optimization_run_id, project_id=project_id
        )

    def _evaluate(self, proposal: OptimizationProposal):
        scenario = self._store.get_scenario(proposal.scenario_id)
        run = self._store.get_run(proposal.optimization_run_id)
        version = None
        if self._models is not None and proposal.model_version_id:
            version = self._models.get_version(
                tenant_id=proposal.tenant_id,
                project_id=proposal.project_id,
                model_version_id=proposal.model_version_id,
            )
        plan = self._source_plan
        if self._planning is not None:
            try:
                plan = self._planning.get_plan(
                    plan_id=proposal.source_plan_id, project_id=proposal.project_id
                )
            except Exception:
                plan = self._source_plan
        readback_ok = False
        if scenario is not None:
            try:
                read_scenario_artifact(
                    store=self._object_store,
                    bucket=scenario.artifact_bucket,
                    object_name=scenario.artifact_object_name,
                    expected_fingerprint=scenario.artifact_fingerprint,
                )
                readback_ok = True
            except Exception:
                readback_ok = False
        receipt = evaluate_proposal_readiness(
            proposal=proposal,
            scenario=scenario,
            run=run,
            version=version,
            source_plan_id=None if plan is None else plan.plan_id,
            source_plan_revision=None if plan is None else plan.revision,
            source_plan_status=None if plan is None else plan.status.value,
            result_readback_ok=readback_ok,
        )
        self._store.put(receipt)
        return receipt

    def _refresh_staleness(self, proposal: OptimizationProposal) -> None:
        if proposal.status in {
            OptimizationProposalLifecycleStatus.APPROVED,
            OptimizationProposalLifecycleStatus.REJECTED,
            OptimizationProposalLifecycleStatus.REVISION_REQUESTED,
            OptimizationProposalLifecycleStatus.WITHDRAWN,
            OptimizationProposalLifecycleStatus.STALE,
        }:
            return
        receipt = self._evaluate(proposal)
        if receipt.status in {
            ProposalReadinessStatus.STALE,
            ProposalReadinessStatus.REVIEW_REQUIRED,
        }:
            self._mark_stale(proposal)

    def _mark_stale(self, proposal: OptimizationProposal) -> OptimizationProposal:
        if proposal.status is OptimizationProposalLifecycleStatus.STALE:
            return proposal
        updated = proposal.model_copy(
            update={"status": OptimizationProposalLifecycleStatus.STALE}
        )
        stored = self._store.put(updated)
        assert isinstance(stored, OptimizationProposal)
        return stored

    def _resolve_source_plan(self, *, project_id: str, actor_id: str) -> InvestmentPlan:
        if self._source_plan is not None:
            if self._source_plan.status is not InvestmentPlanStatus.APPROVED:
                raise ScenarioRequiresCompletedOptimizationError(
                    "Scenario requires an approved source plan."
                )
            return self._source_plan
        if self._planning is None:
            raise PlanningAuthorityError("Source Investment Plan is not configured.")
        coverage, snapshot, view = self._planning.assemble_portfolio(
            project_id=project_id, fiscal_year=None, actor_id=actor_id
        )
        del coverage, view
        plan_id = getattr(snapshot, "investment_plan_id", None)
        if not plan_id:
            raise PlanningAuthorityError("Approved source plan was not found.")
        return self._planning.get_plan(plan_id=str(plan_id), project_id=project_id)

    def _assert_scope(self, tenant_id: str, resource_project_id: str, project_id: str) -> None:
        tenant = require_tenant()
        if tenant_id != tenant.tenant_id:
            raise CrossTenantProposalAccessError(
                "Cross-tenant proposal access is not allowed."
            )
        if resource_project_id != project_id:
            raise CrossProjectProposalAccessError(
                "Cross-project proposal access is not allowed."
            )
