"""Human-only proposal decisions. Never mutate optimizer evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.contracts import (
    OptimizationProposal,
    PlanningDecisionRecord,
    ProposalDecisionReceipt,
    ScenarioArtifact,
)
from app.investment_optimization.enums import (
    DecisionRecordType,
    OptimizationProposalLifecycleStatus,
    ProposalDecision,
)
from app.investment_optimization.errors import (
    InvalidProposalTransitionError,
    ProposalStaleError,
    SubmittedProposalImmutableError,
)
from app.investment_optimization.ids import (
    new_planning_decision_id,
    new_proposal_decision_receipt_id,
)
from app.investment_planning.authority import require_human_approver
from app.investment_planning.fingerprint import metadata_fingerprint

_DECISION_STATUS = {
    ProposalDecision.APPROVE: OptimizationProposalLifecycleStatus.APPROVED,
    ProposalDecision.REJECT: OptimizationProposalLifecycleStatus.REJECTED,
    ProposalDecision.REQUEST_REVISION: OptimizationProposalLifecycleStatus.REVISION_REQUESTED,
    ProposalDecision.WITHDRAW: OptimizationProposalLifecycleStatus.WITHDRAWN,
}

_ALLOWED: dict[
    OptimizationProposalLifecycleStatus, frozenset[OptimizationProposalLifecycleStatus]
] = {
    OptimizationProposalLifecycleStatus.DRAFT: frozenset(
        {
            OptimizationProposalLifecycleStatus.SUBMITTED,
            OptimizationProposalLifecycleStatus.WITHDRAWN,
            OptimizationProposalLifecycleStatus.STALE,
        }
    ),
    OptimizationProposalLifecycleStatus.SUBMITTED: frozenset(
        {
            OptimizationProposalLifecycleStatus.UNDER_REVIEW,
            OptimizationProposalLifecycleStatus.APPROVED,
            OptimizationProposalLifecycleStatus.REJECTED,
            OptimizationProposalLifecycleStatus.REVISION_REQUESTED,
            OptimizationProposalLifecycleStatus.WITHDRAWN,
            OptimizationProposalLifecycleStatus.STALE,
        }
    ),
    OptimizationProposalLifecycleStatus.UNDER_REVIEW: frozenset(
        {
            OptimizationProposalLifecycleStatus.APPROVED,
            OptimizationProposalLifecycleStatus.REJECTED,
            OptimizationProposalLifecycleStatus.REVISION_REQUESTED,
            OptimizationProposalLifecycleStatus.WITHDRAWN,
            OptimizationProposalLifecycleStatus.STALE,
        }
    ),
    OptimizationProposalLifecycleStatus.APPROVED: frozenset(),
    OptimizationProposalLifecycleStatus.REJECTED: frozenset(),
    OptimizationProposalLifecycleStatus.REVISION_REQUESTED: frozenset(),
    OptimizationProposalLifecycleStatus.WITHDRAWN: frozenset(),
    OptimizationProposalLifecycleStatus.STALE: frozenset(),
}

_CORE_FIELDS = (
    "scenario_id",
    "source_plan_id",
    "source_plan_revision",
    "source_plan_fingerprint",
    "optimization_run_id",
    "model_version_id",
)


def assert_core_immutable(
    previous: OptimizationProposal, updated: OptimizationProposal
) -> None:
    if previous.status is OptimizationProposalLifecycleStatus.DRAFT:
        return
    for field in _CORE_FIELDS:
        if getattr(previous, field) != getattr(updated, field):
            raise SubmittedProposalImmutableError(
                "Submitted proposal core authority is immutable."
            )


def transition_status(
    *,
    current: OptimizationProposalLifecycleStatus,
    target: OptimizationProposalLifecycleStatus,
) -> None:
    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise InvalidProposalTransitionError(
            f"Cannot transition proposal from {current.value} to {target.value}."
        )


def apply_decision(
    *,
    proposal: OptimizationProposal,
    scenario: ScenarioArtifact,
    result_fingerprint: str,
    decision: ProposalDecision,
    actor_id: str,
    comment: str | None,
) -> tuple[OptimizationProposal, ProposalDecisionReceipt, PlanningDecisionRecord]:
    approver = require_human_approver(actor_id)
    if proposal.status is OptimizationProposalLifecycleStatus.STALE:
        raise ProposalStaleError("Stale proposals cannot be approved or decided.")
    target = _DECISION_STATUS[decision]
    if decision is ProposalDecision.APPROVE and proposal.status not in {
        OptimizationProposalLifecycleStatus.SUBMITTED,
        OptimizationProposalLifecycleStatus.UNDER_REVIEW,
    }:
        raise InvalidProposalTransitionError(
            "Only SUBMITTED or UNDER_REVIEW proposals may be approved."
        )
    transition_status(current=proposal.status, target=target)
    now = datetime.now(UTC)
    receipt_id = new_proposal_decision_receipt_id()
    receipt_body = {
        "proposal_id": proposal.proposal_id,
        "decision": decision.value,
        "proposal_fingerprint": proposal.fingerprint,
        "scenario_fingerprint": scenario.fingerprint,
        "source_plan_fingerprint": proposal.source_plan_fingerprint,
        "optimization_result_fingerprint": result_fingerprint,
        "decided_by_user_id": approver,
    }
    receipt = ProposalDecisionReceipt(
        decision_receipt_id=receipt_id,
        proposal_id=proposal.proposal_id,
        tenant_id=proposal.tenant_id,
        project_id=proposal.project_id,
        decision=decision,
        decided_by_user_id=approver,
        decided_at=now,
        proposal_fingerprint=proposal.fingerprint,
        scenario_fingerprint=scenario.fingerprint,
        source_plan_fingerprint=proposal.source_plan_fingerprint,
        optimization_result_fingerprint=result_fingerprint,
        comment=comment,
        created_at=now,
        fingerprint=metadata_fingerprint(receipt_body),
    )
    updated = proposal.model_copy(
        update={
            "status": target,
            "decided_at": now,
            "decision_receipt_id": receipt.decision_receipt_id,
        }
    )
    assert_core_immutable(proposal, updated)
    evidence = (
        proposal.optimization_readiness_receipt_id,
        proposal.optimization_run_id,
        scenario.optimization_result_ref,
        scenario.scenario_id,
        proposal.model_version_id,
        proposal.source_plan_id,
    )
    record = PlanningDecisionRecord(
        decision_id=new_planning_decision_id(),
        decision_type=DecisionRecordType.OPTIMIZATION_PROPOSAL,
        proposal_id=proposal.proposal_id,
        tenant_id=proposal.tenant_id,
        project_id=proposal.project_id,
        decision=decision,
        owner=approver,
        evidence_refs=evidence,
        decided_at=now,
        fingerprint=metadata_fingerprint(
            {
                "proposal_id": proposal.proposal_id,
                "decision": decision.value,
                "evidence_refs": evidence,
            }
        ),
    )
    return updated, receipt, record
