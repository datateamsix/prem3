"""P6-06 human decision, transitions, and lineage tests."""

from __future__ import annotations

import pytest

from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.investment_optimization.enums import (
    OptimizationProposalLifecycleStatus,
    ProposalDecision,
)
from app.investment_optimization.errors import (
    CrossProjectProposalAccessError,
    CrossTenantProposalAccessError,
    InvalidProposalTransitionError,
)
from app.investment_planning.errors import PersistenceBarrierError, PlanningAuthorityError
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import bound
from tests.unit.investment_optimization.p6_06_support import (
    complete_run,
    create_proposal,
    create_scenario,
    governance_stack,
)


def _submitted():
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
    return gov, submitted, scenario, run, store, planning, plan, models


def test_only_authorized_human_can_approve() -> None:
    gov, submitted, *_ = _submitted()
    decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    assert decided.status is OptimizationProposalLifecycleStatus.APPROVED
    assert receipt.decided_by_user_id == "user_music_center"


def test_service_account_cannot_approve() -> None:
    gov, submitted, *_ = _submitted()
    with pytest.raises(PlanningAuthorityError):
        bound(
            lambda: gov.decide(
                proposal_id=submitted.proposal_id,
                project_id=PROJECT,
                actor_id="worker@prem3.iam.gserviceaccount.com",
                decision=ProposalDecision.APPROVE,
            )
        )


def test_optimizer_cannot_approve() -> None:
    gov, submitted, *_ = _submitted()
    with pytest.raises(PlanningAuthorityError):
        bound(
            lambda: gov.decide(
                proposal_id=submitted.proposal_id,
                project_id=PROJECT,
                actor_id="service-account:meridian-optimizer",
                decision=ProposalDecision.APPROVE,
            )
        )


def test_decision_receipt_created() -> None:
    gov, submitted, _s, _r, store, *_ = _submitted()
    decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    loaded = store.get_decision_receipt(receipt.decision_receipt_id)
    assert loaded is not None
    assert loaded.proposal_id == decided.proposal_id
    assert loaded.decision is ProposalDecision.APPROVE


def test_decision_receipt_immutable() -> None:
    gov, submitted, _s, _r, store, *_ = _submitted()
    _decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    with pytest.raises(PersistenceBarrierError):
        store.put(receipt.model_copy(update={"comment": "tamper"}))


def test_approve_transition() -> None:
    gov, submitted, *_ = _submitted()
    decided, _receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    assert decided.status is OptimizationProposalLifecycleStatus.APPROVED


def test_reject_transition() -> None:
    gov, submitted, *_ = _submitted()
    decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.REJECT,
            comment="Not this cycle",
        )
    )
    assert decided.status is OptimizationProposalLifecycleStatus.REJECTED
    assert receipt.comment == "Not this cycle"


def test_revision_requested_transition() -> None:
    gov, submitted, *_ = _submitted()
    decided, _receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.REQUEST_REVISION,
        )
    )
    assert decided.status is OptimizationProposalLifecycleStatus.REVISION_REQUESTED


def test_withdraw_transition() -> None:
    gov, submitted, *_ = _submitted()
    decided, _receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.WITHDRAW,
        )
    )
    assert decided.status is OptimizationProposalLifecycleStatus.WITHDRAWN


def test_invalid_transition_rejected() -> None:
    gov, submitted, *_ = _submitted()
    bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    with pytest.raises(InvalidProposalTransitionError):
        bound(
            lambda: gov.decide(
                proposal_id=submitted.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
                decision=ProposalDecision.REJECT,
                comment="too late",
            )
        )


def test_plan_to_run_to_scenario_to_proposal_lineage() -> None:
    gov, submitted, scenario, run, *_ = _submitted()
    assert submitted.source_plan_id == scenario.source_plan_id
    assert submitted.optimization_run_id == run.optimization_run_id
    assert submitted.scenario_id == scenario.scenario_id
    assert scenario.optimization_result_ref == run.result_id


def test_decision_to_plan_revision_lineage() -> None:
    gov, submitted, scenario, _run, store, *_ = _submitted()
    decided, receipt = bound(
        lambda: gov.decide(
            proposal_id=submitted.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    draft = bound(
        lambda: gov.create_plan_revision_from_proposal(
            proposal_id=decided.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    assert draft.predecessor_plan_id == submitted.source_plan_id
    assert draft.source_proposal_id == decided.proposal_id
    assert draft.source_decision_receipt_id == receipt.decision_receipt_id
    assert draft.source_scenario_id == scenario.scenario_id
    record = store.get_decision_record(
        next(iter(store._decision_records))  # noqa: SLF001
    )
    assert record is not None
    assert decided.proposal_id in record.evidence_refs or record.proposal_id == decided.proposal_id


def test_cross_project_proposal_access_fails() -> None:
    gov, submitted, *_ = _submitted()
    with pytest.raises(CrossProjectProposalAccessError):
        bound(
            lambda: gov.get_proposal(
                proposal_id=submitted.proposal_id,
                project_id="wsp_otherotherotheroth",
            )
        )


def test_cross_tenant_proposal_access_fails() -> None:
    gov, submitted, *_ = _submitted()
    other = TenantContext(
        tenant_id="ten_otherotherotherother",
        user_id="user_music_center",
        auth_state=AuthState.AUTHENTICATED,
    )
    with bind_tenant(other):
        with pytest.raises(CrossTenantProposalAccessError):
            gov.get_proposal(proposal_id=submitted.proposal_id, project_id=PROJECT)
