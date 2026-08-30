"""P6-06 fixtures: completed run + approved source plan + governance service."""

from __future__ import annotations

from app.investment_optimization.proposal import ProposalGovernanceService
from app.investment_planning.contracts import InvestmentPlan
from app.investment_planning.enums import BudgetScope, InvestmentPlanStatus
from app.investment_planning.lifecycle import revise_plan
from tests.unit.investment_optimization.p6_04_support import PROJECT, TENANT, now
from tests.unit.investment_optimization.p6_05_support import (
    FakeEntitlementRepo,
    FakePlanning,
    bound,
    run_service,
)


def approved_plan(**overrides: object) -> InvestmentPlan:
    payload = {
        "plan_id": "ipln_aaaaaaaaaaaaaaaaaaaa",
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "workspace_id": PROJECT,
        "name": "FY2027 Marketing Plan",
        "fiscal_year": 2027,
        "fiscal_start_month": 1,
        "currency": "USD",
        "budget_scope": BudgetScope.PAID_MEDIA_ONLY,
        "business_profile_snapshot_id": "bps_dddddddddddddddddddd",
        "business_profile_fingerprint": "fp_biq",
        "status": InvestmentPlanStatus.APPROVED,
        "revision": 1,
        "created_at": now(),
        "updated_at": now(),
        "created_by": "user_music_center",
        "approved_at": now(),
        "approved_by": "user_music_center",
    }
    payload.update(overrides)
    return InvestmentPlan(**payload)


class FakeRevisionHost(FakePlanning):
    def __init__(self, snap, view, plan: InvestmentPlan) -> None:
        super().__init__(snap, view)
        self.plan = plan
        self.plans: dict[str, InvestmentPlan] = {plan.plan_id: plan}
        self.drive_payloads: dict[str, bytes] = {plan.plan_id: b"ORIGINAL_APPROVED_PLAN"}
        self.provider_writes: list[str] = []
        self.approve_calls: list[str] = []
        self.ingest_payloads: list[bytes] = []

    def get_plan(self, *, plan_id: str, project_id: str) -> InvestmentPlan:
        del project_id
        return self.plans[plan_id]

    def revise(
        self,
        *,
        plan_id: str,
        project_id: str,
        actor_id: str,
        source_proposal_id: str | None = None,
        source_decision_receipt_id: str | None = None,
        source_scenario_id: str | None = None,
    ) -> InvestmentPlan:
        del project_id
        source = self.plans[plan_id]
        draft = revise_plan(
            plan=source,
            actor_id=actor_id,
            source_proposal_id=source_proposal_id,
            source_decision_receipt_id=source_decision_receipt_id,
            source_scenario_id=source_scenario_id,
        )
        self.plans[draft.plan_id] = draft
        self.plan_revisions.append(draft.plan_id)
        return draft

    def ingest_bytes(
        self,
        *,
        plan_id: str,
        project_id: str,
        file_name: str,
        mime_type: str,
        data: bytes,
        actor_id: str,
    ) -> object:
        del project_id, file_name, mime_type, actor_id
        self.ingest_payloads.append(data)
        self.drive_writes.append(plan_id)
        self.drive_payloads[plan_id] = data
        return {"plan_id": plan_id}


def governance_stack(*, execute_inline: bool = True):
    run_svc, receipt, store, mapping, input_contract, contract, version, models = run_service(
        execute_inline=execute_inline
    )
    plan = approved_plan()
    planning = FakeRevisionHost(run_svc._planning.snapshot, run_svc._planning.view, plan)
    run_svc._planning = planning
    gov = ProposalGovernanceService(
        repo=FakeEntitlementRepo(),  # type: ignore[arg-type]
        store=store,
        runs=run_svc,
        object_store=run_svc._object_store,
        artifact_bucket="prem3-test-artifacts",
        planning=planning,
        models=models,
        source_plan=plan,
    )
    return gov, run_svc, receipt, store, planning, plan, models, mapping, contract, version


def complete_run(run_svc, receipt):
    return bound(
        lambda: run_svc.create_run(
            project_id=PROJECT,
            actor_id="user_music_center",
            readiness_receipt_id=receipt.receipt_id,
        )
    )


def create_scenario(gov, run_id: str):
    return bound(
        lambda: gov.create_scenario(
            project_id=PROJECT,
            actor_id="user_music_center",
            optimization_run_id=run_id,
        )
    )


def create_proposal(gov, scenario_id: str, **kwargs):
    return bound(
        lambda: gov.create_proposal(
            project_id=PROJECT,
            actor_id="user_music_center",
            scenario_id=scenario_id,
            **kwargs,
        )
    )
