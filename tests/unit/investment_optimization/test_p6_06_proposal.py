"""P6-06 proposal creation, readiness, and staleness tests."""

from __future__ import annotations

import pytest

from app.investment_optimization.enums import (
    OptimizationProposalLifecycleStatus,
    ProposalDecision,
    ProposalReadinessStatus,
)
from app.investment_optimization.errors import (
    ClientBudgetArrayRejectedError,
    ProposalStaleError,
    ScenarioNotFoundError,
)
from app.modeling.mmm.states import MMMModelingStage
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import bound
from tests.unit.investment_optimization.p6_06_support import (
    complete_run,
    create_proposal,
    create_scenario,
    governance_stack,
)


def _ready_proposal():
    gov, run_svc, receipt, store, planning, plan, models, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    return gov, proposal, scenario, run, planning, plan, models, store


def test_proposal_requires_scenario() -> None:
    gov, *_ = governance_stack()
    with pytest.raises(ScenarioNotFoundError):
        create_proposal(gov, "oscn_missingmissingmiss")


def test_proposal_pins_source_plan() -> None:
    gov, proposal, scenario, *_ = _ready_proposal()
    assert proposal.source_plan_id == scenario.source_plan_id
    assert proposal.source_plan_revision == scenario.source_plan_revision
    assert proposal.source_plan_fingerprint == scenario.source_plan_fingerprint


def test_proposal_pins_model_and_run() -> None:
    _, proposal, scenario, run, *_ = _ready_proposal()
    assert proposal.optimization_run_id == run.optimization_run_id
    assert proposal.model_version_id == run.model_version_id
    assert proposal.optimization_readiness_receipt_id == run.readiness_receipt_id
    assert proposal.scenario_id == scenario.scenario_id


def test_submitted_proposal_immutable() -> None:
    gov, proposal, scenario, *_ = _ready_proposal()
    submitted = bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert submitted.status is OptimizationProposalLifecycleStatus.SUBMITTED
    assert submitted.scenario_id == scenario.scenario_id
    assert submitted.source_plan_id == proposal.source_plan_id
    loaded = bound(
        lambda: gov.get_proposal(proposal_id=proposal.proposal_id, project_id=PROJECT)
    )
    assert loaded.scenario_id == scenario.scenario_id
    assert loaded.optimization_run_id == proposal.optimization_run_id


def test_client_cannot_submit_budget_array() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    with pytest.raises(ClientBudgetArrayRejectedError):
        bound(
            lambda: gov.create_scenario(
                project_id=PROJECT,
                actor_id="user_music_center",
                optimization_run_id=run.optimization_run_id,
                budget_array=[{"channel": "search_paid", "amount": "10"}],
            )
        )
    scenario = create_scenario(gov, run.optimization_run_id)
    with pytest.raises(ClientBudgetArrayRejectedError):
        bound(
            lambda: gov.create_proposal(
                project_id=PROJECT,
                actor_id="user_music_center",
                scenario_id=scenario.scenario_id,
                budget_array=[{"channel": "search_paid"}],
            )
        )


def test_source_plan_change_stales_proposal() -> None:
    gov, proposal, _scenario, _run, planning, plan, *_ = _ready_proposal()
    bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    planning.plans[plan.plan_id] = plan.model_copy(update={"revision": 99})
    gov._source_plan = planning.plans[plan.plan_id]
    with pytest.raises(ProposalStaleError):
        bound(
            lambda: gov.decide(
                proposal_id=proposal.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
                decision=ProposalDecision.APPROVE,
            )
        )


def test_scenario_change_impossible() -> None:
    from app.investment_planning.errors import PersistenceBarrierError

    gov, _p, scenario, _run, _pl, _plan, _m, store = _ready_proposal()
    with pytest.raises(PersistenceBarrierError):
        store.put(scenario.model_copy(update={"artifact_fingerprint": "changed"}))


def test_model_acceptance_change_requires_review() -> None:
    gov, proposal, _s, _r, _pl, _plan, models, store = _ready_proposal()
    bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    version = models._versions[0]
    models._versions[0] = version.model_copy(
        update={"accepted": False, "state": MMMModelingStage.ITERATION_REQUIRED}
    )
    with pytest.raises(ProposalStaleError):
        bound(
            lambda: gov.decide(
                proposal_id=proposal.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
                decision=ProposalDecision.APPROVE,
            )
        )
    receipt = store.get_proposal_readiness_for_proposal(proposal.proposal_id)
    loaded = bound(
        lambda: gov.get_proposal(proposal_id=proposal.proposal_id, project_id=PROJECT)
    )
    assert receipt is not None
    assert receipt.status is ProposalReadinessStatus.REVIEW_REQUIRED
    assert loaded.status is OptimizationProposalLifecycleStatus.STALE


def test_stale_proposal_cannot_approve() -> None:
    gov, proposal, _s, _r, planning, plan, *_ = _ready_proposal()
    bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    planning.plans[plan.plan_id] = plan.model_copy(update={"revision": 2})
    gov._source_plan = planning.plans[plan.plan_id]
    from app.investment_optimization.enums import ProposalDecision

    with pytest.raises(ProposalStaleError):
        bound(
            lambda: gov.decide(
                proposal_id=proposal.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
                decision=ProposalDecision.APPROVE,
            )
        )
