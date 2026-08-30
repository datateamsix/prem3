"""P6-06 plan revision from approved proposal. Does not auto-approve."""

from __future__ import annotations

import pytest

from app.investment_optimization.enums import (
    OptimizationProposalLifecycleStatus,
    ProposalDecision,
)
from app.investment_optimization.errors import ProposalNotApprovedError
from app.investment_planning.enums import InvestmentPlanStatus
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import bound
from tests.unit.investment_optimization.p6_06_support import (
    complete_run,
    create_proposal,
    create_scenario,
    governance_stack,
)


def _approved_stack():
    gov, run_svc, receipt, store, planning, plan, models, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    submitted = bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    return gov, decided, receipt, scenario, run, planning, plan, store


def test_approved_proposal_can_create_plan_revision() -> None:
    gov, decided, *_ = _approved_stack()
    draft = bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert draft.status is InvestmentPlanStatus.DRAFT
    assert draft.predecessor_plan_id == decided.source_plan_id


def test_unapproved_proposal_cannot_create_plan_revision() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    with pytest.raises(ProposalNotApprovedError):
        bound(
            lambda: gov.create_plan_revision_from_proposal(
                proposal_id=proposal.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
            )
        )


def test_new_revision_has_parent_version() -> None:
    gov, decided, _receipt, _s, _r, _pl, plan, *_ = _approved_stack()
    draft = bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert draft.predecessor_plan_id == plan.plan_id
    assert draft.revision == plan.revision + 1
    assert draft.plan_id != plan.plan_id


def test_new_revision_pins_proposal() -> None:
    gov, decided, receipt, scenario, *_ = _approved_stack()
    draft = bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert draft.source_proposal_id == decided.proposal_id
    assert draft.source_decision_receipt_id == receipt.decision_receipt_id
    assert draft.source_scenario_id == scenario.scenario_id


def test_prior_approved_plan_not_mutated() -> None:
    gov, decided, _rec, _s, _r, planning, plan, *_ = _approved_stack()
    original = planning.drive_payloads[plan.plan_id]
    bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert planning.drive_payloads[plan.plan_id] == original
    assert plan.status is InvestmentPlanStatus.APPROVED
    assert planning.plans[plan.plan_id].status is InvestmentPlanStatus.APPROVED


def test_plan_revision_requires_validation_and_approval() -> None:
    gov, decided, *_rest = _approved_stack()
    draft = bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert draft.status is not InvestmentPlanStatus.APPROVED
    assert draft.status is InvestmentPlanStatus.DRAFT


def test_optimizer_complete_does_not_create_plan_revision() -> None:
    _gov, run_svc, receipt, _store, planning, *_ = governance_stack()
    complete_run(run_svc, receipt)
    assert planning.plan_revisions == []


def test_scenario_creation_does_not_approve_plan() -> None:
    gov, run_svc, receipt, _st, planning, plan, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    create_scenario(gov, run.optimization_run_id)
    assert planning.plans[plan.plan_id].status is InvestmentPlanStatus.APPROVED
    assert planning.approve_calls == []


def test_proposal_approval_does_not_mutate_existing_plan() -> None:
    gov, decided, _rec, _s, _r, planning, plan, *_ = _approved_stack()
    assert planning.plans[plan.plan_id].status is InvestmentPlanStatus.APPROVED
    assert decided.status is OptimizationProposalLifecycleStatus.APPROVED
    assert plan.plan_id not in planning.plan_revisions


def test_provider_writes_not_invoked() -> None:
    gov, decided, _rec, _s, _r, planning, *_ = _approved_stack()
    bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert planning.provider_writes == []
